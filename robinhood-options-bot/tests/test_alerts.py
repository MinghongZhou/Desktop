from datetime import datetime, timezone

from robinhood_bot.monitoring.alerts import (
    AlertEvent,
    LoggingAlerter,
    Severity,
    WebhookAlerter,
    alert_on_risk_decision,
)


class RecordingAlerter:
    def __init__(self):
        self.events: list[AlertEvent] = []

    def send(self, event: AlertEvent) -> None:
        self.events.append(event)


def make_event(severity: Severity, title: str, detail: str) -> AlertEvent:
    return AlertEvent(severity, title, detail, datetime.now(timezone.utc))


def test_logging_alerter_does_not_raise():
    LoggingAlerter().send(make_event(Severity.INFO, "test", "detail"))


def test_webhook_alerter_calls_injected_post_fn():
    calls = []
    alerter = WebhookAlerter(
        "https://example.invalid/webhook",
        post_fn=lambda url, body: calls.append((url, body)),
    )
    alerter.send(make_event(Severity.CRITICAL, "Trading halted", "drawdown"))
    assert len(calls) == 1
    url, body = calls[0]
    assert url == "https://example.invalid/webhook"
    assert "CRITICAL" in body["text"]
    assert "Trading halted" in body["text"]


def test_webhook_alerter_swallows_delivery_failures():
    def broken_post(url, body):
        raise ConnectionError("no network")

    alerter = WebhookAlerter("https://example.invalid/webhook", post_fn=broken_post)
    # Must not raise -- a broken alert channel shouldn't crash the trading loop.
    alerter.send(make_event(Severity.CRITICAL, "x", "y"))


def test_alert_on_risk_decision_skips_approved_trades():
    alerter = RecordingAlerter()
    alert_on_risk_decision(alerter, approved=True, reason=None)
    assert alerter.events == []


def test_alert_on_risk_decision_skips_routine_rejections():
    alerter = RecordingAlerter()
    alert_on_risk_decision(
        alerter, approved=False,
        reason="Even 1 contract exceeds the per-trade risk budget.",
    )
    assert alerter.events == []


def test_alert_on_risk_decision_fires_for_halt_conditions():
    alerter = RecordingAlerter()
    alert_on_risk_decision(alerter, approved=False, reason="Drawdown circuit breaker tripped (>= 12%).")
    assert len(alerter.events) == 1
    assert alerter.events[0].severity == Severity.CRITICAL

    alerter2 = RecordingAlerter()
    alert_on_risk_decision(alerter2, approved=False, reason="Kill switch is active.")
    assert len(alerter2.events) == 1

    alerter3 = RecordingAlerter()
    alert_on_risk_decision(alerter3, approved=False, reason="Daily loss limit hit (-5.0%).")
    assert len(alerter3.events) == 1
