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


def is_volatility_spiking(
    vol_series: pd.Series, lookback: int = 5, spike_multiple: float = 1.3
) -> bool:
    """True if realized vol has jumped sharply over the last `lookback`
    days -- a sign of an active, ongoing stress event, distinct from
    "IV rank is elevated" (which just means vol is high relative to its
    own trailing history, and could be high-and-stable or high-and-still-
    rising). A walk-forward validation run found the strategy's worst
    losses clustered in exactly this situation: IV rank was attractively
    high, so the strategy sold premium, right as a real market selloff
    was still accelerating (April 2025) rather than already having
    settled into a new (higher but stable) regime. Selling into a still-
    accelerating spike is a materially worse bet than selling once things
    have stabilized at a new elevated level, even though IV rank alone
    can't tell those two situations apart."""
    if len(vol_series) < lookback + 1:
        return False
    current = vol_series.iloc[-1]
    past = vol_series.iloc[-1 - lookback]
    if pd.isna(current) or pd.isna(past) or past <= 0:
        return False
    return bool(current > past * spike_multiple)


def recommend_strategy(
    trend: Trend, iv_rank_value: float, iv_rank_threshold: float = 50.0,
    vol_spiking: bool = False,
) -> StrategyTag:
    """Only recommends selling premium when IV rank clears the threshold --
    selling premium in a low-IV environment is poor risk/reward regardless
    of trend. Also refuses to trade while volatility is actively spiking
    (see `is_volatility_spiking`), even if IV rank looks attractive --
    that's exactly the situation elevated IV rank can't distinguish from
    "already-settled high vol" on its own."""
    if vol_spiking:
        return StrategyTag.NO_TRADE
    if pd.isna(iv_rank_value) or iv_rank_value < iv_rank_threshold:
        return StrategyTag.NO_TRADE

    return {
        Trend.BULLISH: StrategyTag.BULL_PUT_SPREAD,
        Trend.BEARISH: StrategyTag.BEAR_CALL_SPREAD,
        Trend.NEUTRAL: StrategyTag.IRON_CONDOR,
    }[trend]
