"""Historical underlying price fetch + local cache.

Options chain history is not fetched here -- see the module docstring in
options_pricing for why (free historical options data doesn't really exist;
Phase 4/5 simulate option prices from this underlying history instead).

Two sources: `fetch_price_history` (yfinance) and `fetch_price_history_alpaca`
(Alpaca's bars endpoint). yfinance is left in place but is not reliable --
Yahoo Finance appears to fingerprint and block yfinance's client
specifically, even once general network access works (see README's "Known
issues"). Alpaca is the verified-working source; prefer it.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf

from robinhood_bot.broker.alpaca import DATA_BASE_URL, AlpacaTransport
from robinhood_bot.logging_setup import get_logger

log = get_logger(__name__)

_BAR_COLUMNS = {"o": "Open", "h": "High", "l": "Low", "c": "Close", "v": "Volume"}


def _read_cache(cache_path: Path) -> pd.DataFrame | None:
    if not cache_path.exists():
        return None
    cached = pd.read_parquet(cache_path)
    if cached.empty:
        return None
    last_date = cached.index.max()
    if datetime.now(timezone.utc) - last_date.to_pydatetime().replace(
        tzinfo=timezone.utc
    ) < timedelta(days=1):
        return cached
    return None


def _write_cache(df: pd.DataFrame, cache_path: Path) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(cache_path)


def fetch_price_history(
    ticker: str,
    lookback_days: int,
    cache_dir: Path,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """Returns daily OHLCV for `ticker` via yfinance, using a local Parquet
    cache. See the module docstring -- this source is unreliable; prefer
    `fetch_price_history_alpaca`.

    The cache is refreshed automatically if it's missing, empty, or more
    than a day stale, since fresh data matters more than saving one
    network call for a bot that's about to make sizing decisions off it.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{ticker}.parquet"

    if not force_refresh:
        cached = _read_cache(cache_path)
        if cached is not None:
            log.info("price_history.cache_hit", ticker=ticker, rows=len(cached), source="yfinance")
            return cached

    log.info("price_history.fetching", ticker=ticker, lookback_days=lookback_days, source="yfinance")
    start = (datetime.now(timezone.utc) - timedelta(days=int(lookback_days * 1.5))).date()
    df = yf.download(ticker, start=start, progress=False, auto_adjust=True)

    if df.empty:
        raise ValueError(f"yfinance returned no data for ticker {ticker!r}")

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.tail(lookback_days)
    _write_cache(df, cache_path)
    log.info("price_history.cached", ticker=ticker, rows=len(df), path=str(cache_path), source="yfinance")
    return df


def fetch_price_history_alpaca(
    ticker: str,
    lookback_days: int,
    cache_dir: Path,
    transport: AlpacaTransport,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """Same contract as `fetch_price_history` (daily OHLCV, Parquet-cached),
    sourced from Alpaca's `/v2/stocks/{symbol}/bars` endpoint instead of
    yfinance. Cached separately (`{ticker}_alpaca.parquet`) so the two
    sources never collide. Requires an already-authenticated
    `AlpacaTransport` (see broker/alpaca.py) -- this module has no opinion
    on where credentials come from.

    `feed="iex"` is used explicitly since that's what free/paper Alpaca
    accounts are authorized for; a paid plan with full SIP access could use
    "sip" instead for better data quality.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{ticker}_alpaca.parquet"

    if not force_refresh:
        cached = _read_cache(cache_path)
        if cached is not None:
            log.info("price_history.cache_hit", ticker=ticker, rows=len(cached), source="alpaca")
            return cached

    log.info("price_history.fetching", ticker=ticker, lookback_days=lookback_days, source="alpaca")
    start = (datetime.now(timezone.utc) - timedelta(days=int(lookback_days * 1.6))).date()
    end = datetime.now(timezone.utc).date()

    bars: list[dict] = []
    page_token: str | None = None
    while True:
        params: dict[str, Any] = {
            "timeframe": "1Day",
            "start": start.isoformat(),
            "end": end.isoformat(),
            "adjustment": "split",
            "feed": "iex",
            "limit": 10000,
        }
        if page_token is not None:
            params["page_token"] = page_token
        data = transport.get(DATA_BASE_URL, f"/v2/stocks/{ticker}/bars", params=params)
        bars.extend(data.get("bars", []))
        page_token = data.get("next_page_token")
        if not page_token:
            break

    if not bars:
        raise ValueError(f"Alpaca returned no bar data for ticker {ticker!r}")

    df = pd.DataFrame(bars)
    df["t"] = pd.to_datetime(df["t"])
    df = df.set_index("t").sort_index()
    df.index.name = None
    df = df.rename(columns=_BAR_COLUMNS)[list(_BAR_COLUMNS.values())]
    df = df.tail(lookback_days)

    _write_cache(df, cache_path)
    log.info("price_history.cached", ticker=ticker, rows=len(df), path=str(cache_path), source="alpaca")
    return df


def realized_volatility(df: pd.DataFrame, window: int = 21) -> pd.Series:
    """Annualized close-to-close realized volatility over a rolling window.

    Used as the IV proxy for the simulated options pricing model (Phase 2)
    when calibrating against real historical implied vol isn't possible.
    """
    log_returns = np.log(df["Close"] / df["Close"].shift(1))
    return log_returns.rolling(window).std() * (252 ** 0.5)
