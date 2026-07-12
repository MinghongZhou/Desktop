"""Builds the configured price-history fetcher from settings, mirroring
broker/factory.py's pattern for broker adapter selection.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

import pandas as pd

from robinhood_bot.config import DataSettings


def build_price_history_fetcher(
    settings: DataSettings, cache_dir: Path
) -> Callable[..., pd.DataFrame]:
    """Returns a `fetch(ticker, lookback_days, force_refresh=False) -> DataFrame` callable."""
    if settings.price_history_source == "alpaca":
        from robinhood_bot.broker.alpaca import RequestsAlpacaTransport
        from robinhood_bot.data.price_history import fetch_price_history_alpaca

        api_key = os.environ.get("ALPACA_API_KEY")
        api_secret = os.environ.get("ALPACA_API_SECRET")
        if not api_key or not api_secret:
            raise RuntimeError(
                "data.price_history_source is 'alpaca' but ALPACA_API_KEY / "
                "ALPACA_API_SECRET are not set in the environment."
            )
        transport = RequestsAlpacaTransport(api_key, api_secret)

        def fetch(ticker: str, lookback_days: int, force_refresh: bool = False) -> pd.DataFrame:
            return fetch_price_history_alpaca(
                ticker, lookback_days, cache_dir, transport, force_refresh=force_refresh,
            )

        return fetch

    if settings.price_history_source == "yfinance":
        from robinhood_bot.data.price_history import fetch_price_history

        def fetch(ticker: str, lookback_days: int, force_refresh: bool = False) -> pd.DataFrame:
            return fetch_price_history(ticker, lookback_days, cache_dir, force_refresh=force_refresh)

        return fetch

    raise ValueError(f"Unknown price_history_source: {settings.price_history_source!r}")
