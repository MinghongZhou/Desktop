"""Loads and validates config/settings.yaml into typed settings objects.

Nothing downstream should read the YAML file directly -- go through
`load_settings()` so validation (e.g. the live-trading gate) always runs.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SETTINGS_PATH = REPO_ROOT / "config" / "settings.yaml"


class BrokerSettings(BaseModel):
    # "alpaca" is a real, connectable adapter used while Robinhood's MCP
    # connection is unavailable. Credentials come from ALPACA_API_KEY /
    # ALPACA_API_SECRET env vars (see broker/alpaca.py), never from this
    # file -- don't add key fields here.
    adapter: Literal["shadow", "mcp_placeholder", "alpaca"] = "shadow"
    alpaca_paper: bool = True


class UniverseSettings(BaseModel):
    tickers: list[str] = Field(default_factory=list)


class RiskSettings(BaseModel):
    max_risk_per_trade_pct: float
    max_concurrent_positions: int
    max_capital_deployed_pct: float
    daily_loss_limit_pct: float
    drawdown_circuit_breaker_pct: float
    max_portfolio_delta: float
    max_portfolio_theta: float
    max_portfolio_vega: float


class DataSettings(BaseModel):
    # "alpaca" is the verified-working source (see broker/alpaca.py's
    # module docstring). "yfinance" is left available but is unreliable --
    # Yahoo Finance appears to fingerprint and block yfinance's client
    # specifically, even with general network access working.
    price_history_source: Literal["alpaca", "yfinance"] = "alpaca"
    price_history_cache_dir: str
    default_lookback_days: int


class LedgerSettings(BaseModel):
    db_path: str


class LoggingSettings(BaseModel):
    level: str = "INFO"
    json_output: bool = False


class AlertingSettings(BaseModel):
    enabled: bool = False
    webhook_url: str | None = None


class Settings(BaseModel):
    mode: Literal["shadow", "live"] = "shadow"
    live_trading_enabled: bool = False
    broker: BrokerSettings
    universe: UniverseSettings
    risk: RiskSettings
    data: DataSettings
    ledger: LedgerSettings
    logging: LoggingSettings
    alerting: AlertingSettings = AlertingSettings()

    @model_validator(mode="after")
    def _enforce_live_gate(self) -> "Settings":
        """`mode: live` alone is never enough to place real orders.

        Both `mode` AND `live_trading_enabled` must agree, and using the
        `mcp_placeholder` adapter in live mode is always rejected since it
        has no real implementation yet.
        """
        if self.mode == "live" and not self.live_trading_enabled:
            raise ValueError(
                "mode is 'live' but live_trading_enabled is false. "
                "Both must be set explicitly to trade with real money."
            )
        if self.mode == "live" and self.broker.adapter == "mcp_placeholder":
            raise ValueError(
                "Cannot run in live mode against the mcp_placeholder adapter -- "
                "it has no real implementation. Wire in the real Robinhood MCP "
                "adapter first."
            )
        return self

    @property
    def resolved_price_history_cache_dir(self) -> Path:
        p = Path(self.data.price_history_cache_dir)
        return p if p.is_absolute() else REPO_ROOT / p

    @property
    def resolved_ledger_db_path(self) -> Path:
        p = Path(self.ledger.db_path)
        return p if p.is_absolute() else REPO_ROOT / p


def load_settings(path: Path | str = DEFAULT_SETTINGS_PATH) -> Settings:
    with open(path, "r") as f:
        raw = yaml.safe_load(f)
    return Settings.model_validate(raw)
