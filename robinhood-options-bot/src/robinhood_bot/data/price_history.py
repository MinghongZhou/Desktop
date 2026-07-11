"""Historical underlying price fetch + local cache.

Options chain history is not fetched here -- see the module docstring in
options_pricing for why (free historical options data doesn't really exist;
Phase 4/5 simulate option prices from this underlying history instead).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

from robinhood_bot.logging_setup import get_logger

log = get_logger(__name__)


def fetch_price_history(
    ticker: str,
    lookback_days: int,
    cache_dir: Path,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """Returns daily OHLCV for `ticker`, using a local Parquet cache.

    The cache is refreshed automatically if it's missing, empty, or more
    than a day stale, since fresh data matters more than saving one
    yfinance call for a bot that's about to make sizing decisions off it.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{ticker}.parquet"

    if not force_refresh and cache_path.exists():
        cached = pd.read_parquet(cache_path)
        if not cached.empty:
            last_date = cached.index.max()
            if datetime.now(timezone.utc) - last_date.to_pydatetime().replace(
                tzinfo=timezone.utc
            ) < timedelta(days=1):
                log.info("price_history.cache_hit", ticker=ticker, rows=len(cached))
                return cached

    log.info("price_history.fetching", ticker=ticker, lookback_days=lookback_days)
    start = (datetime.now(timezone.utc) - timedelta(days=int(lookback_days * 1.5))).date()
    df = yf.download(ticker, start=start, progress=False, auto_adjust=True)

    if df.empty:
        raise ValueError(f"yfinance returned no data for ticker {ticker!r}")

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.tail(lookback_days)
    df.to_parquet(cache_path)
    log.info("price_history.cached", ticker=ticker, rows=len(df), path=str(cache_path))
    return df


def realized_volatility(df: pd.DataFrame, window: int = 21) -> pd.Series:
    """Annualized close-to-close realized volatility over a rolling window.

    Used as the IV proxy for the simulated options pricing model (Phase 2)
    when calibrating against real historical implied vol isn't possible.
    """
    log_returns = np.log(df["Close"] / df["Close"].shift(1))
    return log_returns.rolling(window).std() * (252 ** 0.5)
