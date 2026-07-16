from datetime import datetime, timezone

import pandas as pd
import pytest

from robinhood_bot.data.news_sentiment import fetch_news_alpaca

from test_broker_alpaca import FakeAlpacaTransport


def make_article(created_at: str, headline: str, summary: str = "") -> dict:
    return {
        "id": 1, "author": "Test", "content": "", "source": "test",
        "created_at": created_at, "updated_at": created_at,
        "headline": headline, "summary": summary, "symbols": ["SPY"], "images": [], "url": "",
    }


def test_fetch_news_alpaca_maps_headlines_correctly(tmp_path):
    transport = FakeAlpacaTransport()
    transport.get_responses["/v1beta1/news"] = {
        "news": [
            make_article("2026-01-02T14:30:00Z", "Stock rallies on strong earnings"),
            make_article("2026-01-03T15:00:00Z", "Guidance cut sends shares lower"),
        ],
        "next_page_token": None,
    }
    df = fetch_news_alpaca("SPY", lookback_days=5, cache_dir=tmp_path, transport=transport)

    assert list(df.columns) == ["headline", "summary"]
    assert len(df) == 2
    assert df["headline"].iloc[0] == "Stock rallies on strong earnings"
    assert isinstance(df.index, pd.DatetimeIndex)
    assert df.index.is_monotonic_increasing


def test_fetch_news_alpaca_follows_pagination(tmp_path):
    transport = FakeAlpacaTransport()
    transport.get_response_sequences["/v1beta1/news"] = [
        {"news": [make_article("2026-01-02T14:30:00Z", "First")], "next_page_token": "page2"},
        {"news": [make_article("2026-01-03T14:30:00Z", "Second")], "next_page_token": None},
    ]
    df = fetch_news_alpaca("SPY", lookback_days=5, cache_dir=tmp_path, transport=transport)

    assert len(df) == 2
    assert transport.calls[1][3]["page_token"] == "page2"


def test_fetch_news_alpaca_returns_empty_df_on_no_articles(tmp_path):
    transport = FakeAlpacaTransport()
    transport.get_responses["/v1beta1/news"] = {"news": [], "next_page_token": None}
    df = fetch_news_alpaca("SPY", lookback_days=5, cache_dir=tmp_path, transport=transport)

    assert df.empty
    assert list(df.columns) == ["headline", "summary"]


def test_fetch_news_alpaca_uses_cache_on_second_call(tmp_path):
    transport = FakeAlpacaTransport()
    now = datetime.now(timezone.utc).isoformat()
    transport.get_responses["/v1beta1/news"] = {
        "news": [make_article(now, "Fresh headline")],
        "next_page_token": None,
    }
    fetch_news_alpaca("SPY", lookback_days=5, cache_dir=tmp_path, transport=transport, force_refresh=True)
    assert len(transport.calls) == 1

    fetch_news_alpaca("SPY", lookback_days=5, cache_dir=tmp_path, transport=transport, force_refresh=False)
    assert len(transport.calls) == 1  # served from cache, no new call


def test_fetch_news_alpaca_caches_separately_per_ticker(tmp_path):
    transport = FakeAlpacaTransport()
    transport.get_responses["/v1beta1/news"] = {
        "news": [make_article("2026-01-02T14:30:00Z", "SPY headline")],
        "next_page_token": None,
    }
    fetch_news_alpaca("SPY", lookback_days=5, cache_dir=tmp_path, transport=transport)

    assert (tmp_path / "SPY_news.parquet").exists()
    assert not (tmp_path / "AAPL_news.parquet").exists()
