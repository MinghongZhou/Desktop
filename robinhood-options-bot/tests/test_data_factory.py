import pytest

from robinhood_bot.config import DataSettings
from robinhood_bot.data.factory import build_price_history_fetcher


def make_settings(source: str) -> DataSettings:
    return DataSettings(
        price_history_source=source,
        price_history_cache_dir="data/historical",
        default_lookback_days=100,
    )


def test_alpaca_source_requires_env_credentials(tmp_path, monkeypatch):
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_API_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="ALPACA_API_KEY"):
        build_price_history_fetcher(make_settings("alpaca"), tmp_path)


def test_alpaca_source_builds_fetcher_when_credentials_present(tmp_path, monkeypatch):
    monkeypatch.setenv("ALPACA_API_KEY", "test-key")
    monkeypatch.setenv("ALPACA_API_SECRET", "test-secret")
    fetch = build_price_history_fetcher(make_settings("alpaca"), tmp_path)
    assert callable(fetch)


def test_yfinance_source_builds_fetcher(tmp_path):
    fetch = build_price_history_fetcher(make_settings("yfinance"), tmp_path)
    assert callable(fetch)


def test_unknown_source_raises(tmp_path):
    with pytest.raises(ValueError, match="Unknown price_history_source"):
        build_price_history_fetcher(
            DataSettings.model_construct(
                price_history_source="bogus",
                price_history_cache_dir="data/historical",
                default_lookback_days=100,
            ),
            tmp_path,
        )
