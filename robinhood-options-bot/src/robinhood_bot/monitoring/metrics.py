"""Performance metrics computed from the ledger's equity curve.

Trade-level stats (win rate, profit factor) need paired open/close fills
per strategy -- that pairing is naturally produced by the backtest engine
(Phase 5) and the execution loop's position tracking (Phase 6/7), so those
metrics live there. This module only needs the equity_snapshots table and
is usable the moment any run starts recording snapshots.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class EquitySummary:
    current_equity: float
    peak_equity: float
    drawdown_pct: float


def summarize_equity_curve(equity_rows: list[dict]) -> EquitySummary | None:
    if not equity_rows:
        return None
    equities = [row["equity"] for row in equity_rows]
    peak = max(equities)
    current = equities[-1]
    drawdown_pct = (peak - current) / peak * 100 if peak else 0.0
    return EquitySummary(current_equity=current, peak_equity=peak, drawdown_pct=drawdown_pct)


def max_drawdown_pct(equity_rows: list[dict]) -> float:
    """Largest peak-to-trough decline over the whole curve, not just from
    the all-time peak to the latest point (that's what `EquitySummary`
    gives you) -- this is the standard backtest/paper-trading metric."""
    peak = float("-inf")
    worst = 0.0
    for row in equity_rows:
        equity = row["equity"]
        peak = max(peak, equity)
        if peak > 0:
            worst = max(worst, (peak - equity) / peak * 100)
    return worst


def cagr(equity_rows: list[dict], trading_days_per_year: int = 252) -> float | None:
    """Compound annual growth rate, treating each row as one period."""
    if len(equity_rows) < 2:
        return None
    start, end = equity_rows[0]["equity"], equity_rows[-1]["equity"]
    if start <= 0:
        return None
    periods = len(equity_rows) - 1
    years = periods / trading_days_per_year
    if years <= 0:
        return None
    return (end / start) ** (1 / years) - 1


def sharpe_ratio(
    equity_rows: list[dict], risk_free_rate: float = 0.0, trading_days_per_year: int = 252
) -> float | None:
    if len(equity_rows) < 3:
        return None
    equities = [row["equity"] for row in equity_rows]
    returns = [
        (equities[i] - equities[i - 1]) / equities[i - 1]
        for i in range(1, len(equities))
        if equities[i - 1] > 0
    ]
    if len(returns) < 2:
        return None
    mean_return = sum(returns) / len(returns)
    variance = sum((r - mean_return) ** 2 for r in returns) / (len(returns) - 1)
    std = math.sqrt(variance)
    if std == 0:
        return None
    daily_rf = risk_free_rate / trading_days_per_year
    return (mean_return - daily_rf) / std * math.sqrt(trading_days_per_year)
