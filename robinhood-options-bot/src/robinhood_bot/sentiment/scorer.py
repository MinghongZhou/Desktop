"""Scores news headlines with VADER and aggregates them into a per-day
sentiment series aligned to a price history's trading days.

VADER is a general-purpose lexicon/rule-based sentiment analyzer, not a
finance-tuned one -- it's the pragmatic first choice here (pure Python,
no heavyweight ML dependency, instant to run over thousands of
headlines for a backtest) but it visibly misses finance-specific
phrasing: "Company beats expectations, raises full-year outlook" scores
as neutral (0.0), not positive, since "beat" and "raise" don't carry
their financial connotation in VADER's general lexicon. A finance-tuned
lexicon (Loughran-McDonald) or model (FinBERT) would likely score
headlines like that correctly and is the natural upgrade path if this
first pass shows real signal worth refining.
"""
from __future__ import annotations

import pandas as pd
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

_analyzer = SentimentIntensityAnalyzer()


def score_headline(text: str) -> float:
    """VADER compound score in [-1, 1]; empty/whitespace-only text scores 0.0 (neutral)."""
    if not text or not text.strip():
        return 0.0
    return _analyzer.polarity_scores(text)["compound"]


def score_news_df(news_df: pd.DataFrame) -> pd.Series:
    """Per-article compound score, indexed the same as `news_df`. Scores
    `headline` and `summary` together (summary is often empty on the
    free tier, in which case this is just the headline score)."""
    summary = news_df["summary"].fillna("") if "summary" in news_df.columns else ""
    combined_text = news_df["headline"].fillna("") + ". " + summary
    return combined_text.apply(score_headline)


def daily_sentiment_series(news_df: pd.DataFrame, trading_days: pd.DatetimeIndex) -> pd.Series:
    """Mean compound sentiment score per trading day, aligned to
    `trading_days` (e.g. a price history's index). A day with no articles
    gets NaN -- callers should treat that as "no signal," not as neutral
    (0.0 sentiment is a real, scored outcome; NaN is "we don't know"),
    since the two mean different things for a filter that only acts on
    strong disagreement.

    Real Alpaca timestamps (both bars and news) are tz-aware UTC, but this
    also has to work with naive test fixtures, so tz-awareness is
    harmonized explicitly before grouping/reindexing -- grouping by
    `.date` used to silently drop the timezone, which matched fine
    against naive trading_days in unit tests but produced all-NaN output
    against real (tz-aware) trading_days: pandas treats a tz-aware and a
    tz-naive timestamp as never equal, so the reindex matched nothing.
    """
    if news_df.empty:
        return pd.Series(float("nan"), index=trading_days)

    scores = score_news_df(news_df)
    news_index = scores.index
    if trading_days.tz is not None:
        news_index = news_index.tz_localize(trading_days.tz) if news_index.tz is None else news_index.tz_convert(trading_days.tz)
    elif news_index.tz is not None:
        news_index = news_index.tz_localize(None)

    daily = scores.groupby(news_index.normalize()).mean()
    aligned = daily.reindex(trading_days.normalize())
    aligned.index = trading_days
    return aligned
