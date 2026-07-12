from datetime import date, datetime, timezone

import pytest

from robinhood_bot.broker.base import (
    OptionContract,
    OptionRight,
    OrderLeg,
    OrderSide,
    OrderStatus,
)
from robinhood_bot.broker.shadow import ShadowBrokerClient


def make_contract(bid=1.0, ask=1.2) -> OptionContract:
    return OptionContract(
        underlying="AAPL",
        expiration=date(2026, 12, 18),
        strike=190.0,
        right=OptionRight.PUT,
        bid=bid,
        ask=ask,
        last=(bid + ask) / 2,
        implied_volatility=0.3,
        delta=-0.3,
        gamma=0.01,
        theta=-0.05,
        vega=0.1,
        as_of=datetime.now(timezone.utc),
    )


def test_buy_to_open_then_sell_to_close_flattens_long_position():
    broker = ShadowBrokerClient(starting_cash=10_000)
    contract = make_contract()

    open_result = broker.place_order(
        [OrderLeg(contract, OrderSide.BUY_TO_OPEN, quantity=1)],
        strategy_tag="test_long_put",
    )
    assert open_result.status == OrderStatus.FILLED
    account = broker.get_account()
    assert len(account.positions) == 1
    assert account.positions[0].quantity == 1
    assert account.cash < 10_000  # buying costs cash

    close_result = broker.place_order(
        [OrderLeg(contract, OrderSide.SELL_TO_CLOSE, quantity=1)],
        strategy_tag="test_long_put",
    )
    assert close_result.status == OrderStatus.FILLED
    account = broker.get_account()
    assert account.positions == []


def test_sell_to_open_then_buy_to_close_flattens_short_position():
    """Regression test: buy-to-close must reduce the magnitude of a short
    position (move toward zero), not increase it."""
    broker = ShadowBrokerClient(starting_cash=10_000)
    contract = make_contract()

    open_result = broker.place_order(
        [OrderLeg(contract, OrderSide.SELL_TO_OPEN, quantity=2)],
        strategy_tag="test_short_put",
    )
    assert open_result.status == OrderStatus.FILLED
    account = broker.get_account()
    assert account.positions[0].quantity == -2
    cash_after_open = account.cash
    assert cash_after_open > 10_000  # selling to open credits cash

    close_result = broker.place_order(
        [OrderLeg(contract, OrderSide.BUY_TO_CLOSE, quantity=2)],
        strategy_tag="test_short_put",
    )
    assert close_result.status == OrderStatus.FILLED
    account = broker.get_account()
    assert account.positions == []
    assert account.cash < cash_after_open  # buying back costs cash


def test_order_rejected_when_no_market():
    broker = ShadowBrokerClient(starting_cash=10_000)
    dead_contract = make_contract(bid=0.0, ask=0.0)

    result = broker.place_order(
        [OrderLeg(dead_contract, OrderSide.BUY_TO_OPEN, quantity=1)],
        strategy_tag="test",
    )
    assert result.status == OrderStatus.REJECTED
    assert broker.get_account().positions == []


def test_remark_position_updates_equity_without_treating_it_as_a_trade():
    """Regression test for a real bug: get_account().equity used to mark
    open positions at their fill-time bid/ask forever, since nothing ever
    updated it. remark_position() is how the backtest engine fixes that
    daily."""
    import dataclasses

    broker = ShadowBrokerClient(starting_cash=10_000)
    contract = make_contract(bid=1.0, ask=1.2)  # mid = 1.1
    broker.place_order(
        [OrderLeg(contract, OrderSide.BUY_TO_OPEN, quantity=1)], strategy_tag="test",
    )
    equity_before = broker.get_account().equity

    # The underlying moved a lot; the contract is now worth much more.
    repriced = dataclasses.replace(contract, bid=5.0, ask=5.2)
    broker.remark_position(contract.occ_symbol, repriced)

    account = broker.get_account()
    assert account.equity > equity_before  # long position gained value
    position = account.positions[0]
    assert position.quantity == 1  # unchanged -- not treated as a trade
    assert position.average_open_price == 1.1  # unchanged -- original fill price preserved
    assert position.contract.bid == 5.0  # but pricing is now current


def test_remark_position_is_a_noop_for_unknown_symbol():
    broker = ShadowBrokerClient(starting_cash=10_000)
    contract = make_contract()
    broker.remark_position(contract.occ_symbol, contract)  # must not raise
    assert broker.get_account().positions == []
