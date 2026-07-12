from datetime import date, datetime, timezone

from robinhood_bot.broker.base import (
    OptionContract,
    OptionRight,
    OrderLeg,
    OrderSide,
)
from robinhood_bot.broker.shadow import ShadowBrokerClient
from robinhood_bot.execution.state_persistence import load_state, save_state
from robinhood_bot.risk.engine import RiskEngine


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


def test_load_state_returns_none_when_no_file_exists(tmp_path, risk_settings):
    assert load_state(tmp_path / "does_not_exist.json", risk_settings) is None


def test_save_then_load_round_trips_broker_cash_and_last_run_date(tmp_path, risk_settings):
    broker = ShadowBrokerClient(starting_cash=87_654.32)
    risk_engine = RiskEngine(risk_settings)
    risk_engine.mark_new_trading_day(date(2026, 3, 2), 87_654.32)

    path = tmp_path / "state.json"
    save_state(path, broker, risk_engine, date(2026, 3, 2))

    restored = load_state(path, risk_settings)
    assert restored is not None
    restored_broker, restored_risk_engine, restored_last_run_date = restored
    assert restored_broker.get_account().cash == 87_654.32
    assert restored_broker.get_account().positions == []
    assert restored_risk_engine.is_halted is False
    assert restored_last_run_date == date(2026, 3, 2)


def test_save_without_last_run_date_round_trips_none(tmp_path, risk_settings):
    broker = ShadowBrokerClient(starting_cash=1_000)
    risk_engine = RiskEngine(risk_settings)
    path = tmp_path / "state.json"

    save_state(path, broker, risk_engine)  # last_run_date omitted

    _, _, restored_last_run_date = load_state(path, risk_settings)
    assert restored_last_run_date is None


def test_save_then_load_round_trips_open_positions_and_halt_flags(tmp_path, risk_settings):
    broker = ShadowBrokerClient(starting_cash=10_000)
    contract = make_contract()
    broker.place_order(
        [OrderLeg(contract, OrderSide.SELL_TO_OPEN, quantity=2)],
        strategy_tag="bull_put_spread",
    )

    risk_engine = RiskEngine(risk_settings)
    risk_engine.mark_new_trading_day(date(2026, 3, 2), 10_000)
    risk_engine.trip_kill_switch("test halt")

    path = tmp_path / "nested" / "state.json"
    save_state(path, broker, risk_engine, date(2026, 3, 2))
    assert path.exists()

    restored_broker, restored_risk_engine, _ = load_state(path, risk_settings)

    positions = restored_broker.get_account().positions
    assert len(positions) == 1
    restored_position = positions[0]
    assert restored_position.quantity == -2
    assert restored_position.strategy_tag == "bull_put_spread"
    assert restored_position.contract.occ_symbol == contract.occ_symbol
    assert restored_position.contract.delta == contract.delta

    assert restored_risk_engine.is_halted is True


def test_save_overwrites_previous_state(tmp_path, risk_settings):
    broker = ShadowBrokerClient(starting_cash=1_000)
    risk_engine = RiskEngine(risk_settings)
    path = tmp_path / "state.json"

    save_state(path, broker, risk_engine, date(2026, 3, 2))
    broker.apply_cash_adjustment(500)
    save_state(path, broker, risk_engine, date(2026, 3, 3))

    restored_broker, _, restored_last_run_date = load_state(path, risk_settings)
    assert restored_broker.get_account().cash == 1_500
    assert restored_last_run_date == date(2026, 3, 3)
