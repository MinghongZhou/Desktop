"""Persists broker + risk-engine state to a JSON file across process
restarts, so a long-lived daemon (execution/paper_loop.py) can be resumed
by a fresh process -- e.g. a Claude Code Routine firing on a schedule --
instead of losing the paper account and resetting to starting cash every
time it's re-invoked.

Also persists the last trading day actually processed. Without it, a
fresh process invocation always starts with no memory of "today already
ran," so if a Routine fires twice in one day (a retry, a manual re-run
for testing) it would silently open a second, duplicate set of positions
for that same day -- run_paper_trading_daemon's own same-day skip guard
only protects against *within-process* re-firing, not across separate
invocations.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from robinhood_bot.broker.shadow import ShadowBrokerClient
from robinhood_bot.config import RiskSettings
from robinhood_bot.risk.engine import RiskEngine


def save_state(
    path: Path, broker: ShadowBrokerClient, risk_engine: RiskEngine, last_run_date: date | None = None,
) -> None:
    state = {
        "broker": broker.export_state(),
        "risk_engine": risk_engine.export_state(),
        "last_run_date": last_run_date.isoformat() if last_run_date else None,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(state, indent=2))
    tmp_path.replace(path)


def load_state(
    path: Path, risk_settings: RiskSettings,
) -> tuple[ShadowBrokerClient, RiskEngine, date | None] | None:
    """Returns None (rather than raising) when no state file exists yet, so
    callers can fall back to a fresh broker/risk-engine on first run."""
    if not path.exists():
        return None
    state = json.loads(path.read_text())
    broker = ShadowBrokerClient.from_state(state["broker"])
    risk_engine = RiskEngine(risk_settings)
    risk_engine.import_state(state["risk_engine"])
    last_run_date = date.fromisoformat(state["last_run_date"]) if state.get("last_run_date") else None
    return broker, risk_engine, last_run_date
