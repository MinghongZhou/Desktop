"""Pushes alerts out instead of making someone go read a log.

`LoggingAlerter` is the always-safe fallback (alerts should never be
silently dropped even with no webhook configured). `WebhookAlerter` posts
to any Slack/Discord-compatible incoming webhook. `post_fn` is injectable
so tests never need real network access.
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
