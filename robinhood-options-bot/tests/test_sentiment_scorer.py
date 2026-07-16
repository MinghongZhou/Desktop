import math

import pandas as pd
import pytest

from robinhood_bot.sentiment.scorer import daily_sentiment_series, score_headline, score_news_df


def test_score_headline_positive_for_clearly_positive_text():
    assert score_headline("Great news: profits soar and outlook improves") > 0.3


def test_score_headline_negative_for_clearly_negative_text():
    assert score_headline("Stock crashes after disastrous earnings miss") < -0.3


def test_score_headline_zero_for_empty_text():
    assert score_headline("") == 0.0
    assert score_headline("   ") == 0.0


def make_news_df(rows: list[tuple[str, str, str]]) -> pd.DataFrame:
    """rows: (created_at_iso, headline, summary)"""
    df = pd.DataFrame(rows, columns=["created_at", "headline", "summary"])
    df["created_at"] = pd.to_datetime(df["created_at"])
    return df.set_index("created_at")


def test_score_news_df_scores_each_row():
    news_df = make_news_df([
        ("2026-01-02T14:00:00Z", "Great news for investors", ""),
        ("2026-01-02T15:00:00Z", "Terrible losses reported", ""),
    ])
    scores = score_news_df(news_df)
    assert len(scores) == 2
    assert scores.iloc[0] > 0
    assert scores.iloc[1] < 0


def test_daily_sentiment_series_averages_same_day_articles():
    news_df = make_news_df([
        ("2026-01-02T14:00:00Z", "Great news for investors", ""),
        ("2026-01-02T15:00:00Z", "Wonderful profits reported", ""),
    ])
    trading_days = pd.DatetimeIndex(["2026-01-02"])
    series = daily_sentiment_series(news_df, trading_days)
    assert len(series) == 1
    assert series.iloc[0] > 0


def test_daily_sentiment_series_nan_for_days_with_no_news():
    news_df = make_news_df([("2026-01-02T14:00:00Z", "Great news", "")])
    trading_days = pd.DatetimeIndex(["2026-01-02", "2026-01-05"])
    series = daily_sentiment_series(news_df, trading_days)
    assert not math.isnan(series.iloc[0])
    assert math.isnan(series.iloc[1])


def test_daily_sentiment_series_all_nan_when_news_df_empty():
    empty_df = pd.DataFrame(columns=["headline", "summary"])
    empty_df.index = pd.DatetimeIndex([], name="created_at")
    trading_days = pd.DatetimeIndex(["2026-01-02", "2026-01-05"])
    series = daily_sentiment_series(empty_df, trading_days)
    assert series.isna().all()
    assert len(series) == 2


def test_daily_sentiment_series_matches_against_tz_aware_trading_days():
    """Regression test for a real bug: real Alpaca price bars are
    tz-aware (UTC), unlike the naive DatetimeIndex used in the other
    tests here. The original implementation grouped news by `.date`,
    which silently dropped the timezone and produced an all-NaN result
    once reindexed against tz-aware trading days, since pandas never
    considers a naive and a tz-aware timestamp equal."""
    news_df = make_news_df([("2026-01-02T14:00:00Z", "Great news for investors", "")])
    trading_days = pd.DatetimeIndex(["2026-01-02", "2026-01-05"], tz="UTC")
    series = daily_sentiment_series(news_df, trading_days)
    assert not math.isnan(series.iloc[0])
    assert math.isnan(series.iloc[1])


def test_daily_sentiment_series_matches_when_news_is_naive_but_trading_days_is_tz_aware():
    """The reverse tz mismatch: naive news timestamps against tz-aware
    trading days should still align correctly."""
    news_df = make_news_df([("2026-01-02T14:00:00", "Great news for investors", "")])
    assert news_df.index.tz is None
    trading_days = pd.DatetimeIndex(["2026-01-02", "2026-01-05"], tz="UTC")
    series = daily_sentiment_series(news_df, trading_days)
    assert not math.isnan(series.iloc[0])
    assert math.isnan(series.iloc[1])
