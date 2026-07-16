"""Historical news headlines via Alpaca's news API, local Parquet-cached
the same way price history is (see price_history.py).

Real, timestamped, point-in-time headlines going back years -- verified
against a real account before building around it. This is what makes a
sentiment *backtest* honest rather than hindsight-biased: each headline's
own `created_at` is what a trading-day filter looks up, never "today's"
news applied retroactively.

Full article `content` is typically empty on the free/paper tier -- only
`headline` and (sometimes) `summary` are populated, so sentiment scoring
(sentiment/scorer.py) works off those two fields only.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from robinhood_bot.broker.alpaca import DATA_BASE_URL, AlpacaTransport
from robinhood_bot.logging_setup import get_logger

log = get_logger(__name__)


def _read_cache(cache_path: Path) -> pd.DataFrame | None:
    if not cache_path.exists():
        return None
    cached = pd.read_parquet(cache_path)
    if cached.empty:
        return None
    last_ts = cached.index.max()
    if datetime.now(timezone.utc) - last_ts.to_pydatetime().replace(tzinfo=timezone.utc) < timedelta(hours=6):
        return cached
    return None


def fetch_news_alpaca(
    ticker: str,
    lookback_days: int,
    cache_dir: Path,
    transport: AlpacaTransport,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """Returns headlines for `ticker` over the last `lookback_days`,
    indexed by `created_at` (UTC), columns `headline` and `summary`.
    Cached separately from price history (`{ticker}_news.parquet`) with a
    much shorter freshness window than price bars (6h, not 1 day) since
    news arrives continuously through the trading day rather than once
    per close.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{ticker}_news.parquet"

    if not force_refresh:
        cached = _read_cache(cache_path)
        if cached is not None:
            log.info("news_sentiment.cache_hit", ticker=ticker, rows=len(cached))
            return cached

    log.info("news_sentiment.fetching", ticker=ticker, lookback_days=lookback_days)
    start = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).date()
    end = datetime.now(timezone.utc).date()

    articles: list[dict] = []
    page_token: str | None = None
    while True:
        params: dict[str, Any] = {
            "symbols": ticker,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "limit": 50,
            "include_content": False,
        }
        if page_token is not None:
            params["page_token"] = page_token
        data = transport.get(DATA_BASE_URL, "/v1beta1/news", params=params)
        articles.extend(data.get("news", []))
        page_token = data.get("next_page_token")
        if not page_token:
            break

    if not articles:
        df = pd.DataFrame(columns=["headline", "summary"])
        df.index = pd.DatetimeIndex([], name="created_at")
        _write_cache(df, cache_path)
        return df

    df = pd.DataFrame(articles)
    df["created_at"] = pd.to_datetime(df["created_at"])
    df = df.set_index("created_at").sort_index()
    df = df[["headline", "summary"]]

    _write_cache(df, cache_path)
    log.info("news_sentiment.cached", ticker=ticker, rows=len(df), path=str(cache_path))
    return df


def _write_cache(df: pd.DataFrame, cache_path: Path) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(cache_path)
