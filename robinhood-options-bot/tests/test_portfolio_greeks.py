from datetime import datetime, timezone

import pytest

from robinhood_bot.broker.base import Account, OptionRight, OrderLeg, OrderSide, Position
from robinhood_bot.options_pricing.simulated_chain import build_simulated_chain
from robinhood_bot.risk.portfolio_greeks import add, incremental_greeks, portfolio_greeks, scale


def make_chain():
    as_of = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return build_simulated_chain(underlying="TEST", spot=100, as_of=as_of, iv=0.3)


def test_short_put_position_contributes_positive_theta():
    chain = make_chain()
    put = next(c for c in chain if c.right is OptionRight.PUT)
    account = Account(
        equity=10_000, cash=10_000, buying_power=10_000,
        positions=[Position(contract=put, quantity=-1, average_open_price=1.0, strategy_tag="test")],
    )
    greeks = portfolio_greeks(account)
    # short position: contract theta (negative for a long option) * negative
    # quantity = positive portfolio theta -- premium selling collects theta.
    assert greeks.theta > 0
    assert greeks.delta == put.delta * -1 * 100


def test_incremental_greeks_matches_expected_sign_for_sell_to_open():
    chain = make_chain()
    put = next(c for c in chain if c.right is OptionRight.PUT)
    legs = [OrderLeg(put, OrderSide.SELL_TO_OPEN, quantity=2)]
    greeks = incremental_greeks(legs)
    assert greeks.delta == pytest.approx(put.delta * -2 * 100)


def test_add_and_scale_are_pure_arithmetic():
    from robinhood_bot.risk.portfolio_greeks import PortfolioGreeks

    a = PortfolioGreeks(delta=10, theta=-2, vega=5)
    b = PortfolioGreeks(delta=1, theta=1, vega=1)
    summed = add(a, b)
    assert summed == PortfolioGreeks(delta=11, theta=-1, vega=6)

    scaled = scale(a, 3)
    assert scaled == PortfolioGreeks(delta=30, theta=-6, vega=15)
