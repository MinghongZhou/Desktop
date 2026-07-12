"""Direct tests of the mark-to-market and early-exit mechanisms added to
fix a real bug (open positions were marked at fill-time price forever)
and to give the strategy a way to react to an open position's unrealized
P&L instead of only ever holding to expiration."""
from datetime import date, datetime, timezone

import pytest

from robinhood_bot.backtest.engine import (
    BacktestConfig,
    _manage_early_exits,
    _mark_open_positions_to_market,
)
from robinhood_bot.broker.base import OptionContract, OptionRight, OrderLeg, OrderSide
from robinhood_bot.broker.shadow import ShadowBrokerClient
from robinhood_bot.ledger.store import Ledger


@pytest.fixture
def ledger(tmp_path):
    lg = Ledger(tmp_path / "early_exit_ledger.sqlite3")
    yield lg
    lg.close()


def make_put(strike=100.0, bid=2.0, ask=2.2, expiration=date(2026, 3, 1)) -> OptionContract:
    return OptionContract(
        underlying="TEST", expiration=expiration, strike=strike, right=OptionRight.PUT,
        bid=bid, ask=ask, last=(bid + ask) / 2, implied_volatility=0.3,
        delta=-0.30, gamma=0.01, theta=-0.05, vega=0.1,
        as_of=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def open_short_put(broker: ShadowBrokerClient, contract: OptionContract, strategy_tag="cash_secured_put"):
    broker.place_order([OrderLeg(contract, OrderSide.SELL_TO_OPEN, quantity=1)], strategy_tag=strategy_tag)


# -- _mark_open_positions_to_market --

def test_mark_to_market_updates_equity_for_a_favorable_move():
    broker = ShadowBrokerClient(starting_cash=100_000)
    open_short_put(broker, make_put(strike=100.0, bid=2.0, ask=2.2))  # mid=2.1, credit ~$210
    equity_at_open = broker.get_account().equity

    # Spot rallies far above the strike -- the put should now be worth
    # much less (good for the short seller).
    _mark_open_positions_to_market(
        broker, BacktestConfig(ticker="TEST"), spot=150.0, vol=0.3,
        as_of=datetime(2026, 1, 5, tzinfo=timezone.utc), as_of_date=date(2026, 1, 5),
    )
    equity_after = broker.get_account().equity
    assert equity_after > equity_at_open  # unrealized gain now reflected, not stuck at fill-time price


def test_mark_to_market_updates_equity_for_an_unfavorable_move():
    broker = ShadowBrokerClient(starting_cash=100_000)
    open_short_put(broker, make_put(strike=100.0, bid=2.0, ask=2.2))
    equity_at_open = broker.get_account().equity

    # Spot crashes well below the strike -- the put should now be worth
    # much more (bad for the short seller).
    _mark_open_positions_to_market(
        broker, BacktestConfig(ticker="TEST"), spot=70.0, vol=0.3,
        as_of=datetime(2026, 1, 5, tzinfo=timezone.utc), as_of_date=date(2026, 1, 5),
    )
    equity_after = broker.get_account().equity
    assert equity_after < equity_at_open


def test_mark_to_market_skips_positions_expiring_today():
    broker = ShadowBrokerClient(starting_cash=100_000)
    expiring_today = date(2026, 1, 5)
    contract = make_put(strike=100.0, expiration=expiring_today)
    open_short_put(broker, contract)

    _mark_open_positions_to_market(
        broker, BacktestConfig(ticker="TEST"), spot=150.0, vol=0.3,
        as_of=datetime(2026, 1, 5, tzinfo=timezone.utc), as_of_date=expiring_today,
    )
    position = broker.get_account().positions[0]
    assert position.contract.bid == contract.bid  # untouched -- settlement handles this day instead


def test_mark_to_market_noop_when_vol_is_nan():
    import math
    broker = ShadowBrokerClient(starting_cash=100_000)
    contract = make_put()
    open_short_put(broker, contract)

    _mark_open_positions_to_market(
        broker, BacktestConfig(ticker="TEST"), spot=150.0, vol=math.nan,
        as_of=datetime(2026, 1, 5, tzinfo=timezone.utc), as_of_date=date(2026, 1, 5),
    )
    position = broker.get_account().positions[0]
    assert position.contract.bid == contract.bid  # no valid vol -- marks left untouched


# -- _manage_early_exits --

def test_profit_target_closes_position_once_credit_mostly_captured(ledger):
    broker = ShadowBrokerClient(starting_cash=100_000)
    contract = make_put(strike=100.0, bid=2.0, ask=2.2)  # entry mid = 2.1
    open_short_put(broker, contract)

    # Reprice the position to a small fraction of its entry value -- most
    # of the credit has been captured, well past the 50% default target.
    cheap_contract = make_put(strike=100.0, bid=0.3, ask=0.4)
    broker.remark_position(contract.occ_symbol, cheap_contract)

    config = BacktestConfig(ticker="TEST", profit_target_pct=0.50)
    _manage_early_exits(broker, ledger, "run1", "backtest", config, date(2026, 1, 5), datetime(2026, 1, 5, tzinfo=timezone.utc))

    assert broker.get_account().positions == []  # closed early
    orders = ledger.recent_orders(run_id="run1", limit=10)
    assert orders[0]["strategy_tag"] == "cash_secured_put_profit_target"


def test_stop_loss_closes_position_once_loss_exceeds_multiple_of_credit(ledger):
    broker = ShadowBrokerClient(starting_cash=100_000)
    contract = make_put(strike=100.0, bid=2.0, ask=2.2)  # entry mid = 2.1, credit ~$210
    open_short_put(broker, contract)

    # Reprice the position much higher -- cost to close now far exceeds
    # 2x the credit received (the default stop_loss_multiple).
    expensive_contract = make_put(strike=100.0, bid=8.0, ask=8.2)
    broker.remark_position(contract.occ_symbol, expensive_contract)

    config = BacktestConfig(ticker="TEST", stop_loss_multiple=2.0)
    _manage_early_exits(broker, ledger, "run1", "backtest", config, date(2026, 1, 5), datetime(2026, 1, 5, tzinfo=timezone.utc))

    assert broker.get_account().positions == []
    orders = ledger.recent_orders(run_id="run1", limit=10)
    assert orders[0]["strategy_tag"] == "cash_secured_put_stop_loss"


def test_position_left_open_when_neither_threshold_hit(ledger):
    broker = ShadowBrokerClient(starting_cash=100_000)
    contract = make_put(strike=100.0, bid=2.0, ask=2.2)
    open_short_put(broker, contract)

    # Small, unremarkable move -- neither target should fire.
    slightly_cheaper = make_put(strike=100.0, bid=1.8, ask=2.0)
    broker.remark_position(contract.occ_symbol, slightly_cheaper)

    config = BacktestConfig(ticker="TEST")
    _manage_early_exits(broker, ledger, "run1", "backtest", config, date(2026, 1, 5), datetime(2026, 1, 5, tzinfo=timezone.utc))

    assert len(broker.get_account().positions) == 1  # still open
    assert ledger.recent_orders(run_id="run1", limit=10) == []


def test_early_exit_disabled_leaves_positions_open_regardless_of_pnl(ledger):
    broker = ShadowBrokerClient(starting_cash=100_000)
    contract = make_put(strike=100.0, bid=2.0, ask=2.2)
    open_short_put(broker, contract)

    expensive_contract = make_put(strike=100.0, bid=20.0, ask=20.2)  # huge loss
    broker.remark_position(contract.occ_symbol, expensive_contract)

    config = BacktestConfig(ticker="TEST", enable_early_exit=False)
    _manage_early_exits(broker, ledger, "run1", "backtest", config, date(2026, 1, 5), datetime(2026, 1, 5, tzinfo=timezone.utc))

    assert len(broker.get_account().positions) == 1  # untouched
