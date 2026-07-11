from datetime import datetime, timezone

import pytest

from robinhood_bot.broker.base import Order, OrderResult, OrderStatus
from robinhood_bot.ledger.store import Ledger
from robinhood_bot.options_pricing.simulated_chain import build_simulated_chain
from robinhood_bot.strategy.definitions import bull_put_spread


@pytest.fixture
def ledger(tmp_path):
    lg = Ledger(tmp_path / "test_ledger.sqlite3")
    yield lg
    lg.close()


def make_order_result():
    as_of = datetime(2026, 1, 1, tzinfo=timezone.utc)
    chain = build_simulated_chain(underlying="TEST", spot=100, as_of=as_of, iv=0.3)
    legs = bull_put_spread(chain, short_delta=-0.30, width=5.0)
    order = Order(
        order_id="1", legs=legs, limit_price=None,
        strategy_tag="bull_put_spread", submitted_at=as_of,
    )
    return OrderResult(order=order, status=OrderStatus.FILLED, fill_price=1.23, filled_at=as_of)


def test_record_and_read_back_signal(ledger):
    ledger.record_signal(
        run_id="run1", mode="backtest", ticker="TEST",
        trend="bullish", iv_rank=72.5, recommended_strategy="bull_put_spread",
    )
    rows = ledger.recent_signals(run_id="run1")
    assert len(rows) == 1
    assert rows[0]["ticker"] == "TEST"
    assert rows[0]["iv_rank"] == 72.5


def test_record_and_read_back_risk_decision(ledger):
    ledger.record_risk_decision(
        run_id="run1", mode="backtest", strategy_tag="bull_put_spread",
        approved=False, reason="Daily loss limit hit", suggested_quantity=0,
        max_loss_per_unit=250.0,
    )
    rows = ledger.recent_risk_decisions(run_id="run1")
    assert len(rows) == 1
    assert rows[0]["approved"] == 0
    assert rows[0]["reason"] == "Daily loss limit hit"


def test_record_and_read_back_order(ledger):
    ledger.record_order("run1", "backtest", make_order_result())
    rows = ledger.recent_orders(run_id="run1")
    assert len(rows) == 1
    assert rows[0]["status"] == "filled"
    assert rows[0]["strategy_tag"] == "bull_put_spread"
    assert rows[0]["quantity"] == 2  # 2 legs, 1 contract each


def test_equity_curve_is_ordered_oldest_first(ledger):
    ledger.record_equity_snapshot("run1", "backtest", equity=100_000, cash=100_000)
    ledger.record_equity_snapshot("run1", "backtest", equity=101_500, cash=99_000)
    curve = ledger.equity_curve(run_id="run1")
    assert len(curve) == 2
    assert curve[0]["equity"] == 100_000
    assert curve[-1]["equity"] == 101_500


def test_run_id_isolation(ledger):
    ledger.record_equity_snapshot("run1", "backtest", equity=100_000, cash=100_000)
    ledger.record_equity_snapshot("run2", "paper", equity=50_000, cash=50_000)
    assert len(ledger.equity_curve(run_id="run1")) == 1
    assert len(ledger.equity_curve(run_id="run2")) == 1
    assert len(ledger.equity_curve()) == 2  # no run_id filter -> everything
