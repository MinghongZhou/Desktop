from datetime import datetime, timezone

import pandas as pd
import pytest

from robinhood_bot.data.price_history import fetch_intraday_bars_alpaca, fetch_price_history_alpaca

from test_broker_alpaca import FakeAlpacaTransport


def make_bar(day: str, close: float, time: str = "05:00:00") -> dict:
    return {"t": f"{day}T{time}Z", "o": close - 1, "h": close + 1, "l": close - 2, "c": close, "v": 1000}


def test_fetch_price_history_alpaca_maps_bars_correctly(tmp_path):
    transport = FakeAlpacaTransport()
    transport.get_responses["/v2/stocks/AAPL/bars"] = {
        "bars": [make_bar("2026-01-02", 100.0), make_bar("2026-01-03", 101.5)],
        "next_page_token": None,
    }
    df = fetch_price_history_alpaca("AAPL", lookback_days=5, cache_dir=tmp_path, transport=transport)

    assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert len(df) == 2
    assert df["Close"].iloc[0] == 100.0
    assert df["Close"].iloc[-1] == 101.5
    assert isinstance(df.index, pd.DatetimeIndex)
    assert df.index.is_monotonic_increasing


def test_fetch_price_history_alpaca_follows_pagination(tmp_path):
    transport = FakeAlpacaTransport()
    transport.get_response_sequences["/v2/stocks/AAPL/bars"] = [
        {"bars": [make_bar("2026-01-02", 100.0)], "next_page_token": "page2"},
        {"bars": [make_bar("2026-01-03", 101.5)], "next_page_token": None},
    ]
    df = fetch_price_history_alpaca("AAPL", lookback_days=5, cache_dir=tmp_path, transport=transport)

    assert len(df) == 2  # both pages collected
    assert transport.calls[1][3]["page_token"] == "page2"


def test_fetch_price_history_alpaca_raises_on_no_data(tmp_path):
    transport = FakeAlpacaTransport()
    transport.get_responses["/v2/stocks/AAPL/bars"] = {"bars": [], "next_page_token": None}
    with pytest.raises(ValueError, match="no bar data"):
        fetch_price_history_alpaca("AAPL", lookback_days=5, cache_dir=tmp_path, transport=transport)


def test_fetch_price_history_alpaca_uses_cache_on_second_call(tmp_path):
    from datetime import datetime, timezone

    transport = FakeAlpacaTransport()
    today = datetime.now(timezone.utc).date().isoformat()
    transport.get_responses["/v2/stocks/AAPL/bars"] = {
        "bars": [make_bar(today, 100.0)],  # dated "today" so the freshness check passes
        "next_page_token": None,
    }
    fetch_price_history_alpaca("AAPL", lookback_days=5, cache_dir=tmp_path, transport=transport, force_refresh=True)
    assert len(transport.calls) == 1

    # Second call with force_refresh=False and a fresh-enough cache should
    # hit the cache, not the transport again.
    fetch_price_history_alpaca("AAPL", lookback_days=5, cache_dir=tmp_path, transport=transport, force_refresh=False)
    assert len(transport.calls) == 1  # unchanged -- no new call made


def test_fetch_price_history_alpaca_and_yfinance_cache_separately(tmp_path):
    """Regression guard: the two sources must never collide on the same
    cache file, or switching sources would silently serve stale/wrong data."""
    transport = FakeAlpacaTransport()
    transport.get_responses["/v2/stocks/AAPL/bars"] = {
        "bars": [make_bar("2026-01-02", 100.0)],
        "next_page_token": None,
    }
    fetch_price_history_alpaca("AAPL", lookback_days=5, cache_dir=tmp_path, transport=transport)

    assert (tmp_path / "AAPL_alpaca.parquet").exists()
    assert not (tmp_path / "AAPL.parquet").exists()


def test_fetch_intraday_bars_maps_bars_and_uses_own_cache_file(tmp_path):
    transport = FakeAlpacaTransport()
    transport.get_responses["/v2/stocks/SPY/bars"] = {
        "bars": [
            make_bar("2026-01-02", 100.0, "14:30:00"),
            make_bar("2026-01-02", 100.5, "14:45:00"),
        ],
        "next_page_token": None,
    }
    df = fetch_intraday_bars_alpaca("SPY", "15Min", lookback_days=5, cache_dir=tmp_path, transport=transport)

    assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert len(df) == 2
    assert transport.calls[0][3]["timeframe"] == "15Min"
    assert (tmp_path / "SPY_alpaca_15Min.parquet").exists()
    # must not collide with the daily fetcher's cache file or with a
    # different intraday granularity's cache file
    assert not (tmp_path / "SPY_alpaca.parquet").exists()


def test_fetch_intraday_bars_trims_by_calendar_days_not_row_count(tmp_path):
    """Regression guard: unlike the daily fetcher's tail(lookback_days)
    (rows == days there), intraday bars have many rows per day, so
    trimming must be calendar-day-based or it would silently cut off
    mid-day instead of dropping whole old days."""
    transport = FakeAlpacaTransport()
    transport.get_responses["/v2/stocks/SPY/bars"] = {
        "bars": [
            make_bar("2026-01-01", 99.0, "14:30:00"),   # 10 days before the last bar -- should be trimmed
            make_bar("2026-01-10", 100.0, "14:30:00"),
            make_bar("2026-01-10", 100.5, "14:45:00"),
            make_bar("2026-01-10", 101.0, "15:00:00"),
        ],
        "next_page_token": None,
    }
    df = fetch_intraday_bars_alpaca("SPY", "15Min", lookback_days=5, cache_dir=tmp_path, transport=transport)

    assert len(df) == 3  # all 3 same-day bars kept, the old day dropped entirely
    assert df.index.min().date().isoformat() == "2026-01-10"


def test_fetch_intraday_bars_different_timeframes_cache_separately(tmp_path):
    transport = FakeAlpacaTransport()
    transport.get_responses["/v2/stocks/SPY/bars"] = {
        "bars": [make_bar("2026-01-02", 100.0, "14:30:00")],
        "next_page_token": None,
    }
    fetch_intraday_bars_alpaca("SPY", "5Min", lookback_days=5, cache_dir=tmp_path, transport=transport)
    fetch_intraday_bars_alpaca("SPY", "15Min", lookback_days=5, cache_dir=tmp_path, transport=transport)

    assert (tmp_path / "SPY_alpaca_5Min.parquet").exists()
    assert (tmp_path / "SPY_alpaca_15Min.parquet").exists()
    assert len(transport.calls) == 2  # second timeframe wasn't served from the first's cache


def test_fetch_intraday_bars_uses_cache_on_second_call(tmp_path):
    transport = FakeAlpacaTransport()
    today = datetime.now(timezone.utc).date().isoformat()
    transport.get_responses["/v2/stocks/SPY/bars"] = {
        "bars": [make_bar(today, 100.0, "14:30:00")],
        "next_page_token": None,
    }
    fetch_intraday_bars_alpaca("SPY", "15Min", lookback_days=5, cache_dir=tmp_path, transport=transport,
                                force_refresh=True)
    assert len(transport.calls) == 1

    fetch_intraday_bars_alpaca("SPY", "15Min", lookback_days=5, cache_dir=tmp_path, transport=transport,
                                force_refresh=False)
    assert len(transport.calls) == 1  # unchanged -- served from cache
