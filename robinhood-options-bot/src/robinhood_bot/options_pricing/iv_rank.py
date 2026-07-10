"""IV rank / IV percentile, computed over the realized-vol proxy series.

Real IV rank is normally computed from a history of actual implied
volatility. Since real historical option quotes aren't available for free
(see data/price_history.py), this operates on the realized-volatility series
instead -- a standard proxy, but a proxy nonetheless. Strategy signals that
gate on "IV rank" are really gating on "realized-vol rank" during backtests.
"""
from __future__ import annotations

import pandas as pd


def iv_rank_series(vol_series: pd.Series, window: int = 252) -> pd.Series:
    """(current - trailing_min) / (trailing_max - trailing_min) * 100."""
    trailing_min = vol_series.rolling(window).min()
    trailing_max = vol_series.rolling(window).max()
    spread = trailing_max - trailing_min
    rank = (vol_series - trailing_min) / spread * 100
    return rank.where(spread > 0, 50.0)  # flat vol window -> treat as neutral


def iv_percentile_series(vol_series: pd.Series, window: int = 252) -> pd.Series:
    """% of the trailing window's observations at or below the current value."""
    def _pct_rank(values: pd.Series) -> float:
        current = values.iloc[-1]
        return (values <= current).sum() / len(values) * 100

    return vol_series.rolling(window).apply(_pct_rank, raw=False)
