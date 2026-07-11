"""Sensitivity analysis for the assumptions the backtest depends on most.

The single biggest source of false confidence in this project's backtests
is the simulated-options-pricing assumption (Black-Scholes calibrated to
realized volatility standing in for real implied vol). `run_iv_sensitivity`
quantifies how much results move if that proxy is wrong by a given margin
-- it scales the volatility fed into option *pricing* only
(`BacktestConfig.iv_multiplier`), leaving the realized-vol-based IV-rank
*signal* that decides whether to trade unscaled, so this isolates "was the
pricing model right" from "would the strategy have even fired differently."

`run_execution_sensitivity` does the same for fill-quality assumptions
(slippage, commissions), which `ShadowBrokerClient` otherwise models as
perfect (zero-cost, exact-mid-price) fills.
"""
from __future__ import annotations

import dataclasses
import uuid

import pandas as pd

from robinhood_bot.backtest.engine import BacktestConfig, BacktestResult, run_backtest
from robinhood_bot.config import RiskSettings
from robinhood_bot.ledger.store import Ledger


def run_iv_sensitivity(
    price_df: pd.DataFrame,
    config: BacktestConfig,
    risk_settings: RiskSettings,
    ledger: Ledger,
    iv_multipliers: tuple[float, ...] = (0.7, 1.0, 1.3),
) -> dict[float, BacktestResult]:
    batch_id = uuid.uuid4().hex[:8]
    results = {}
    for multiplier in iv_multipliers:
        scenario_config = dataclasses.replace(config, iv_multiplier=multiplier)
        run_id = f"iv_sensitivity_{batch_id}_x{multiplier}_{config.ticker}"
        results[multiplier] = run_backtest(price_df, scenario_config, risk_settings, ledger, run_id=run_id)
    return results


def run_execution_sensitivity(
    price_df: pd.DataFrame,
    config: BacktestConfig,
    risk_settings: RiskSettings,
    ledger: Ledger,
    scenarios: dict[str, tuple[float, float]] | None = None,
) -> dict[str, BacktestResult]:
    """Reruns the backtest under different (slippage_pct, commission_per_contract)
    assumptions to quantify how much fill-quality assumptions matter.
    Default scenarios: perfect fills, and two increasingly realistic ones."""
    scenarios = scenarios or {
        "perfect_fills": (0.0, 0.0),
        "moderate_friction": (0.02, 0.65),
        "high_friction": (0.05, 1.0),
    }
    batch_id = uuid.uuid4().hex[:8]
    results = {}
    for name, (slippage_pct, commission) in scenarios.items():
        scenario_config = dataclasses.replace(
            config, slippage_pct=slippage_pct, commission_per_contract=commission,
        )
        run_id = f"execution_sensitivity_{batch_id}_{name}_{config.ticker}"
        results[name] = run_backtest(price_df, scenario_config, risk_settings, ledger, run_id=run_id)
    return results
