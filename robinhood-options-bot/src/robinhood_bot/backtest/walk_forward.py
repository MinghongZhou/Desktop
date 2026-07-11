"""Walk-forward validation: run the same rule-based strategy across
several contiguous, non-overlapping trading windows instead of one big
in-sample backtest.

The strategy here has no fitted parameters to re-optimize per fold (it's
rule-based, not ML), so the point of folding isn't parameter re-fitting --
it's catching a strategy that only "works" because one lucky regime
dominates the full-period backtest. Each fold trades a distinct slice of
calendar time (no overlap, no re-trading the same days twice); the
warmup period feeding each fold's indicators is allowed to reach back into
earlier history, since that's just indicator lookback, not a trade.
"""
from __future__ import annotations

import uuid

import pandas as pd

from robinhood_bot.backtest.engine import MIN_HISTORY_DAYS, BacktestConfig, BacktestResult, run_backtest
from robinhood_bot.config import RiskSettings
from robinhood_bot.ledger.store import Ledger


def run_walk_forward(
    price_df: pd.DataFrame,
    config: BacktestConfig,
    risk_settings: RiskSettings,
    ledger: Ledger,
    n_folds: int = 3,
) -> list[BacktestResult]:
    if n_folds < 1:
        raise ValueError("n_folds must be >= 1")

    total_days = len(price_df)
    tradable_days = total_days - MIN_HISTORY_DAYS
    fold_size = tradable_days // n_folds
    if fold_size < 1:
        raise ValueError(
            f"Not enough history for {n_folds} folds: need at least "
            f"{MIN_HISTORY_DAYS + n_folds} rows, got {total_days}."
        )

    batch_id = uuid.uuid4().hex[:8]
    results = []
    for fold in range(n_folds):
        trading_start = fold * fold_size
        # Last fold absorbs the remainder so no trailing days are dropped.
        trading_end = tradable_days if fold == n_folds - 1 else (fold + 1) * fold_size
        fold_slice = price_df.iloc[trading_start: MIN_HISTORY_DAYS + trading_end]
        run_id = f"walkforward_{batch_id}_fold{fold}_{config.ticker}"
        result = run_backtest(fold_slice, config, risk_settings, ledger, run_id=run_id)
        results.append(result)
    return results
