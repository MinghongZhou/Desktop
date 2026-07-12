from datetime import date, datetime, timezone

import pandas as pd
import pytest

from robinhood_bot.broker.base import OptionContract, OptionRight, OrderSide
from robinhood_bot.options_pricing.simulated_chain import build_simulated_chain
from robinhood_bot.strategy.definitions import (
    NoValidStrikeError,
    bear_call_spread,
    bull_put_spread,
    cash_secured_put,
    covered_call,
    iron_condor,
)
from robinhood_bot.strategy.signals import (
    StrategyTag,
    Trend,
    is_volatility_spiking,
    recommend_strategy,
    trend_signal,
)


@pytest.fixture
def chain():
    as_of = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return build_simulated_chain(underlying="TEST", spot=100, as_of=as_of, iv=0.3)


def test_cash_secured_put_sells_one_put(chain):
    legs = cash_secured_put(chain)
    assert len(legs) == 1
    assert legs[0].contract.right is OptionRight.PUT
    assert legs[0].side is OrderSide.SELL_TO_OPEN


def test_covered_call_sells_one_call(chain):
    legs = covered_call(chain)
    assert len(legs) == 1
    assert legs[0].contract.right is OptionRight.CALL
    assert legs[0].side is OrderSide.SELL_TO_OPEN


def test_bull_put_spread_has_defined_max_loss_shape(chain):
    legs = bull_put_spread(chain, short_delta=-0.30, width=5.0)
    assert len(legs) == 2
    short_leg = next(l for l in legs if l.side is OrderSide.SELL_TO_OPEN)
    long_leg = next(l for l in legs if l.side is OrderSide.BUY_TO_OPEN)
    assert short_leg.contract.right is OptionRight.PUT
    assert long_leg.contract.right is OptionRight.PUT
    # long put strike must be below the short put strike (bought protection)
    assert long_leg.contract.strike < short_leg.contract.strike


def test_bear_call_spread_has_defined_max_loss_shape(chain):
    legs = bear_call_spread(chain, short_delta=0.30, width=5.0)
    short_leg = next(l for l in legs if l.side is OrderSide.SELL_TO_OPEN)
    long_leg = next(l for l in legs if l.side is OrderSide.BUY_TO_OPEN)
    assert long_leg.contract.strike > short_leg.contract.strike


def _lone_put_contract(strike: float) -> OptionContract:
    return OptionContract(
        underlying="TEST", expiration=date(2026, 12, 18), strike=strike, right=OptionRight.PUT,
        bid=1.0, ask=1.2, last=1.1, implied_volatility=0.3,
        delta=-0.30, gamma=0.01, theta=-0.05, vega=0.1,
        as_of=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def _lone_call_contract(strike: float) -> OptionContract:
    return OptionContract(
        underlying="TEST", expiration=date(2026, 12, 18), strike=strike, right=OptionRight.CALL,
        bid=1.0, ask=1.2, last=1.1, implied_volatility=0.3,
        delta=0.30, gamma=0.01, theta=-0.05, vega=0.1,
        as_of=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def test_bull_put_spread_raises_when_no_lower_strike_available():
    """Regression test for a real bug caught against a live Alpaca account:
    a chain with only one strike at an expiration (sparse real strike
    spacing, e.g. a thinly-quoted LEAPS expiration) used to make the
    "closest available strike to target" fall back to the short leg's own
    strike, producing an invalid duplicate-leg order the broker correctly
    rejected. Now it raises clearly instead."""
    with pytest.raises(NoValidStrikeError):
        bull_put_spread([_lone_put_contract(100.0)], short_delta=-0.30, width=5.0)


def test_bear_call_spread_raises_when_no_higher_strike_available():
    with pytest.raises(NoValidStrikeError):
        bear_call_spread([_lone_call_contract(100.0)], short_delta=0.30, width=5.0)


def test_bull_put_spread_rejects_realized_width_too_far_from_target():
    """Regression test for a real finding from a live backtest: real strike
    grids are often sparser than the requested width, and the old code
    silently accepted whatever was closest -- 5-wide requests became
    15-wide (3x) spreads, a materially different, riskier trade. Now it's
    refused instead of silently taken."""
    short = _lone_put_contract(100.0)
    far_long = OptionContract(
        underlying="TEST", expiration=short.expiration, strike=50.0, right=OptionRight.PUT,
        bid=0.1, ask=0.2, last=0.15, implied_volatility=0.3,
        delta=-0.05, gamma=0.01, theta=-0.02, vega=0.05,
        as_of=short.as_of,
    )
    with pytest.raises(NoValidStrikeError, match="more than"):
        bull_put_spread([short, far_long], short_delta=-0.30, width=5.0, max_width_multiple=1.5)


def test_bull_put_spread_accepts_realized_width_within_tolerance():
    short = _lone_put_contract(100.0)
    close_long = OptionContract(
        underlying="TEST", expiration=short.expiration, strike=93.0, right=OptionRight.PUT,
        bid=0.5, ask=0.6, last=0.55, implied_volatility=0.3,
        delta=-0.15, gamma=0.01, theta=-0.03, vega=0.08,
        as_of=short.as_of,
    )
    legs = bull_put_spread([short, close_long], short_delta=-0.30, width=5.0, max_width_multiple=1.5)
    assert len(legs) == 2  # 7-wide is within 1.5x of the 5-wide target -- accepted


def test_iron_condor_combines_both_spreads(chain):
    legs = iron_condor(chain)
    assert len(legs) == 4
    rights = {l.contract.right for l in legs}
    assert rights == {OptionRight.CALL, OptionRight.PUT}


def test_trend_signal_detects_bullish_uptrend():
    prices = pd.DataFrame({"Close": [100 + i * 0.5 for i in range(60)]})
    assert trend_signal(prices, fast=10, slow=30) is Trend.BULLISH


def test_trend_signal_detects_bearish_downtrend():
    prices = pd.DataFrame({"Close": [100 - i * 0.5 for i in range(60)]})
    assert trend_signal(prices, fast=10, slow=30) is Trend.BEARISH


def test_recommend_strategy_skips_trade_below_iv_rank_threshold():
    assert recommend_strategy(Trend.BULLISH, iv_rank_value=20.0) is StrategyTag.NO_TRADE


def test_recommend_strategy_maps_trend_to_defined_risk_spread():
    assert recommend_strategy(Trend.BULLISH, iv_rank_value=80.0) is StrategyTag.BULL_PUT_SPREAD
    assert recommend_strategy(Trend.BEARISH, iv_rank_value=80.0) is StrategyTag.BEAR_CALL_SPREAD
    assert recommend_strategy(Trend.NEUTRAL, iv_rank_value=80.0) is StrategyTag.IRON_CONDOR


def test_recommend_strategy_skips_trade_when_volatility_is_spiking():
    """Even with an attractively high IV rank, a currently-spiking vol
    environment (found via walk-forward validation to be where the
    strategy's worst losses cluster) should be refused."""
    assert recommend_strategy(
        Trend.BULLISH, iv_rank_value=90.0, vol_spiking=True,
    ) is StrategyTag.NO_TRADE


def test_is_volatility_spiking_detects_sharp_recent_jump():
    vol = pd.Series([0.15] * 10 + [0.30])  # last value more than doubled over 5 days
    assert is_volatility_spiking(vol, lookback=5, spike_multiple=1.3) is True


def test_is_volatility_spiking_false_for_stable_vol():
    vol = pd.Series([0.20] * 11)
    assert is_volatility_spiking(vol, lookback=5, spike_multiple=1.3) is False


def test_is_volatility_spiking_false_for_insufficient_history():
    vol = pd.Series([0.20, 0.25])
    assert is_volatility_spiking(vol, lookback=5) is False


def test_is_volatility_spiking_false_for_nan_values():
    vol = pd.Series([float("nan")] * 6)
    assert is_volatility_spiking(vol, lookback=5) is False
