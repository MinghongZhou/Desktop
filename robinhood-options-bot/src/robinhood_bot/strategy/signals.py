"""Entry signal generation: trend filter + IV-rank timing -> strategy choice.

Credit spreads (bull put / bear call / iron condor) are the default
recommendation over cash-secured puts or covered calls when a trade is
signaled at all, because their max loss is capped at (width - credit)
regardless of the stock price -- a cash-secured put's max loss is the full
strike (minus premium), which is a much larger dollar figure for the same
underlying. That fits the moderate-risk, safety-margin-first mandate better.
"""
from __future__ import annotations

from enum import Enum

import pandas as pd


class Trend(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class StrategyTag(str, Enum):
    BULL_PUT_SPREAD = "bull_put_spread"
    BEAR_CALL_SPREAD = "bear_call_spread"
    IRON_CONDOR = "iron_condor"
    NO_TRADE = "no_trade"


def trend_signal(price_df: pd.DataFrame, fast: int = 20, slow: int = 50,
                  neutral_band_pct: float = 0.01) -> Trend:
    """SMA(fast) vs SMA(slow) crossover, with a neutral band to avoid
    flip-flopping on noise right at the crossover point."""
    sma_fast = price_df["Close"].rolling(fast).mean().iloc[-1]
    sma_slow = price_df["Close"].rolling(slow).mean().iloc[-1]
    spread_pct = (sma_fast - sma_slow) / sma_slow

    if spread_pct > neutral_band_pct:
        return Trend.BULLISH
    if spread_pct < -neutral_band_pct:
        return Trend.BEARISH
    return Trend.NEUTRAL


def recommend_strategy(
    trend: Trend, iv_rank_value: float, iv_rank_threshold: float = 50.0
) -> StrategyTag:
    """Only recommends selling premium when IV rank clears the threshold --
    selling premium in a low-IV environment is poor risk/reward regardless
    of trend."""
    if pd.isna(iv_rank_value) or iv_rank_value < iv_rank_threshold:
        return StrategyTag.NO_TRADE

    return {
        Trend.BULLISH: StrategyTag.BULL_PUT_SPREAD,
        Trend.BEARISH: StrategyTag.BEAR_CALL_SPREAD,
        Trend.NEUTRAL: StrategyTag.IRON_CONDOR,
    }[trend]
