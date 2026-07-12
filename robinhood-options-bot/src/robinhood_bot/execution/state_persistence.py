"""Persists broker + risk-engine state to a JSON file across process
restarts, so a long-lived daemon (execution/paper_loop.py) can be resumed
by a fresh process -- e.g. a Claude Code Routine firing on a schedule --
instead of losing the paper account and resetting to starting cash every
time it's re-invoked.
"""
from __future__ import annotations

import json
from pathlib import Path

from robinhood_bot.broker.shadow import ShadowBrokerClient
from robinhood_bot.config import RiskSettings
from robinhood_bot.risk.engine import RiskEngine


def save_state(path: Path, broker: ShadowBrokerClient, risk_engine: RiskEngine) -> None:
    state = {
        "broker": broker.export_state(),
        "risk_engine": risk_engine.export_state(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(state, indent=2))
    tmp_path.replace(path)


def load_state(path: Path, risk_settings: RiskSettings) -> tuple[ShadowBrokerClient, RiskEngine] | None:
    """Returns None (rather than raising) when no state file exists yet, so
    callers can fall back to a fresh broker/risk-engine on first run."""
    if not path.exists():
        return None
    state = json.loads(path.read_text())
    broker = ShadowBrokerClient.from_state(state["broker"])
    risk_engine = RiskEngine(risk_settings)
    risk_engine.import_state(state["risk_engine"])
    return broker, risk_engine
