"""Pushes alerts out instead of making someone go read a log.

`LoggingAlerter` is the always-safe fallback (alerts should never be
silently dropped even with no webhook configured). `WebhookAlerter` posts
to any Slack/Discord-compatible incoming webhook. `TwilioWhatsAppAlerter`
sends a WhatsApp message via Twilio's API. `post_fn` is injectable on all
of these so tests never need real network access.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Callable

from robinhood_bot.logging_setup import get_logger

log = get_logger(__name__)

_HALT_WORTHY_PREFIXES = ("Kill switch", "Drawdown circuit breaker", "Daily loss limit")


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(frozen=True)
class AlertEvent:
    severity: Severity
    title: str
    detail: str
    at: datetime


class Alerter(ABC):
    @abstractmethod
    def send(self, event: AlertEvent) -> None:
        ...


class LoggingAlerter(Alerter):
    def send(self, event: AlertEvent) -> None:
        log_fn = {
            Severity.INFO: log.info,
            Severity.WARNING: log.warning,
            Severity.CRITICAL: log.error,
        }[event.severity]
        log_fn("alert", title=event.title, detail=event.detail, severity=event.severity.value)


class WebhookAlerter(Alerter):
    def __init__(self, webhook_url: str, post_fn: Callable[[str, dict], None] | None = None):
        self._webhook_url = webhook_url
        self._post_fn = post_fn or self._default_post

    @staticmethod
    def _default_post(url: str, json_body: dict) -> None:
        import requests
        requests.post(url, json=json_body, timeout=10)

    def send(self, event: AlertEvent) -> None:
        text = f"[{event.severity.value.upper()}] {event.title}: {event.detail}"
        try:
            self._post_fn(self._webhook_url, {"text": text})
        except Exception:
            log.error("alert.webhook_delivery_failed", title=event.title)


def alert_on_risk_decision(alerter: Alerter, approved: bool, reason: str | None) -> None:
    """Only pages for halt-worthy conditions -- a routine per-trade
    rejection (e.g. "too small for the risk budget") is normal operation,
    not an alert-worthy event on its own."""
    if approved or reason is None:
        return
    if any(reason.startswith(prefix) for prefix in _HALT_WORTHY_PREFIXES):
        alerter.send(AlertEvent(
            severity=Severity.CRITICAL,
            title="Trading halted",
            detail=reason,
            at=datetime.now(timezone.utc),
        ))


def alert_on_order_fill(alerter: Alerter, order_row: dict) -> None:
    """Notifies on every actually-filled order (opens and closes) --
    rejected/cancelled orders aren't trades and don't page anyone."""
    if order_row["status"] != "filled":
        return
    fill_price = order_row["fill_price"]
    fill_str = f"${fill_price:.2f}" if fill_price is not None else "n/a"
    alerter.send(AlertEvent(
        severity=Severity.INFO,
        title="Trade filled",
        detail=f"{order_row['strategy_tag']} x{order_row['quantity']} @ {fill_str} "
               f"(run_id={order_row['run_id']})",
        at=datetime.now(timezone.utc),
    ))


class TwilioWhatsAppAlerter(Alerter):
    """Sends alerts as a WhatsApp message via Twilio's Programmable
    Messaging API. Requires a Twilio account with WhatsApp enabled (the
    free sandbox works for a single personal number -- join it by sending
    the sandbox's join code to its WhatsApp number from your own phone)
    and TWILIO_ACCOUNT_SID/TWILIO_AUTH_TOKEN in the environment; those
    never pass through this class's constructor as literals in code or
    config, the same credential-handling rule the Alpaca adapter follows.
    """

    def __init__(
        self, account_sid: str, auth_token: str, from_number: str, to_number: str,
        post_fn: Callable[[str, str, dict], None] | None = None,
    ):
        self._account_sid = account_sid
        self._auth_token = auth_token
        self._from_number = from_number  # e.g. "whatsapp:+14155238886" (Twilio's sandbox number)
        self._to_number = to_number      # e.g. "whatsapp:+15551234567"
        self._post_fn = post_fn or self._default_post

    @staticmethod
    def _default_post(account_sid: str, auth_token: str, data: dict) -> None:
        import requests
        url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
        response = requests.post(url, data=data, auth=(account_sid, auth_token), timeout=10)
        response.raise_for_status()

    def send(self, event: AlertEvent) -> None:
        text = f"[{event.severity.value.upper()}] {event.title}: {event.detail}"
        try:
            self._post_fn(self._account_sid, self._auth_token, {
                "From": self._from_number, "To": self._to_number, "Body": text,
            })
        except Exception:
            log.error("alert.whatsapp_delivery_failed", title=event.title)
