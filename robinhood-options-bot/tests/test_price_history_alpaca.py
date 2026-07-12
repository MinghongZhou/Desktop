import pandas as pd
import pytest

from robinhood_bot.data.price_history import fetch_price_history_alpaca

from test_broker_alpaca import FakeAlpacaTransport


def make_bar(day: str, close: float) -> dict:
    return {"t": f"{day}T05:00:00Z", "o": close - 1, "h": close + 1, "l": close - 2, "c": close, "v": 1000}


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
