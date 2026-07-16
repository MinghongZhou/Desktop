"""Tests for the optional sentiment filter wired into backtest/engine.py.
Off by default (sentiment_filter_enabled=False), so the live paper
trial and every pre-existing test are unaffected unless a test opts in
explicitly -- see BacktestConfig's docstring-adjacent comment."""
import numpy as np
import pandas as pd
import pytest

from robinhood_bot.backtest.engine import MIN_HISTORY_DAYS, BacktestConfig, run_backtest
from robinhood_bot.ledger.store import Ledger


@pytest.fixture
def ledger(tmp_path):
    lg = Ledger(tmp_path / "sentiment_filter_ledger.sqlite3")
    yield lg
    lg.close()


def make_strong_uptrend_df(n: int = 320, seed: int = 7) -> pd.DataFrame:
    """A steady uptrend, so trend_signal reads BULLISH (-> bull_put_spread,
    with a permissive iv_rank_threshold) on essentially every tradable day
    -- makes the sentiment filter's effect deterministic to assert on."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    returns = rng.normal(0.003, 0.003, n)
    prices = 100.0 * np.cumprod(1 + returns)
    return pd.DataFrame({"Close": prices}, index=dates)


def make_uniform_sentiment(price_df: pd.DataFrame, value: float) -> pd.Series:
    return pd.Series(value, index=price_df.index)


def test_sentiment_filter_disabled_by_default_ignores_sentiment_series(ledger, risk_settings):
    df = make_strong_uptrend_df()
    very_negative_sentiment = make_uniform_sentiment(df, -0.9)
    config = BacktestConfig(ticker="TEST", iv_rank_threshold=0.0, dte_target=10)  # sentiment_filter_enabled defaults False

    result = run_backtest(df, config, risk_settings, ledger, sentiment_series=very_negative_sentiment)
    orders = ledger.recent_orders(run_id=result.run_id, limit=10_000)
    assert len(orders) > 0  # filter never consulted -- behaves exactly as without it


def test_sentiment_filter_blocks_bullish_trade_against_strongly_negative_news(ledger, risk_settings):
    df = make_strong_uptrend_df()
    very_negative_sentiment = make_uniform_sentiment(df, -0.9)
    config = BacktestConfig(
        ticker="TEST", iv_rank_threshold=0.0, dte_target=10,
        sentiment_filter_enabled=True, sentiment_block_threshold=0.15,
    )

    result = run_backtest(df, config, risk_settings, ledger, sentiment_series=very_negative_sentiment)
    orders = ledger.recent_orders(run_id=result.run_id, limit=10_000)
    bull_put_opens = [o for o in orders if o["strategy_tag"] == "bull_put_spread"]
    assert bull_put_opens == []  # every bullish day's entry got blocked


def test_sentiment_filter_allows_bullish_trade_when_news_agrees(ledger, risk_settings):
    df = make_strong_uptrend_df()
    positive_sentiment = make_uniform_sentiment(df, 0.5)
    config = BacktestConfig(
        ticker="TEST", iv_rank_threshold=0.0, dte_target=10,
        sentiment_filter_enabled=True, sentiment_block_threshold=0.15,
    )

    result = run_backtest(df, config, risk_settings, ledger, sentiment_series=positive_sentiment)
    orders = ledger.recent_orders(run_id=result.run_id, limit=10_000)
    bull_put_opens = [o for o in orders if o["strategy_tag"] == "bull_put_spread"]
    assert bull_put_opens  # agreeing sentiment doesn't block anything


def test_sentiment_filter_noop_when_no_series_provided_even_if_enabled(ledger, risk_settings):
    df = make_strong_uptrend_df()
    config = BacktestConfig(
        ticker="TEST", iv_rank_threshold=0.0, dte_target=10,
        sentiment_filter_enabled=True,  # enabled, but no series passed in
    )

    result = run_backtest(df, config, risk_settings, ledger)  # sentiment_series omitted
    orders = ledger.recent_orders(run_id=result.run_id, limit=10_000)
    assert len(orders) > 0  # nothing to consult -- filter is a safe no-op


def test_sentiment_filter_noop_on_nan_days(ledger, risk_settings):
    df = make_strong_uptrend_df()
    all_nan_sentiment = pd.Series(float("nan"), index=df.index)
    config = BacktestConfig(
        ticker="TEST", iv_rank_threshold=0.0, dte_target=10,
        sentiment_filter_enabled=True, sentiment_block_threshold=0.15,
    )

    result = run_backtest(df, config, risk_settings, ledger, sentiment_series=all_nan_sentiment)
    orders = ledger.recent_orders(run_id=result.run_id, limit=10_000)
    assert len(orders) > 0  # "no signal" days trade exactly as if the filter were off
