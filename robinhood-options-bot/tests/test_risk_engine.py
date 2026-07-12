from datetime import date, datetime, timezone

import pytest

from robinhood_bot.broker.base import Account
from robinhood_bot.config import RiskSettings
from robinhood_bot.options_pricing.simulated_chain import build_simulated_chain
from robinhood_bot.risk.engine import RiskEngine
from robinhood_bot.strategy.definitions import bull_put_spread


def make_settings(**overrides) -> RiskSettings:
    defaults = dict(
        max_risk_per_trade_pct=2.5,
        max_concurrent_positions=6,
        max_capital_deployed_pct=60,
        daily_loss_limit_pct=4,
        drawdown_circuit_breaker_pct=12,
        max_portfolio_delta=300,
        max_portfolio_theta=-150,
        max_portfolio_vega=500,
    )
    defaults.update(overrides)
    return RiskSettings(**defaults)


def make_account(equity: float = 100_000) -> Account:
    return Account(equity=equity, cash=equity, buying_power=equity, positions=[])


def make_spread_legs():
    as_of = datetime(2026, 1, 1, tzinfo=timezone.utc)
    chain = build_simulated_chain(underlying="TEST", spot=100, as_of=as_of, iv=0.3)
    return bull_put_spread(chain, short_delta=-0.30, width=5.0)


def test_approves_a_reasonable_trade_within_all_limits():
    engine = RiskEngine(make_settings())
    engine.mark_new_trading_day(date(2026, 1, 1), 100_000)
    decision = engine.evaluate_new_trade(
        make_account(), make_spread_legs(), open_position_groups=0, reserved_risk_capital=0,
    )
    assert decision.approved
    assert decision.suggested_quantity >= 1


def test_rejects_when_one_contract_exceeds_per_trade_risk_budget():
    engine = RiskEngine(make_settings(max_risk_per_trade_pct=0.01))
    engine.mark_new_trading_day(date(2026, 1, 1), 100_000)
    decision = engine.evaluate_new_trade(
        make_account(), make_spread_legs(), open_position_groups=0, reserved_risk_capital=0,
    )
    assert not decision.approved
    assert "risk budget" in decision.reason


def test_rejects_when_max_concurrent_positions_reached():
    engine = RiskEngine(make_settings(max_concurrent_positions=2))
    engine.mark_new_trading_day(date(2026, 1, 1), 100_000)
    decision = engine.evaluate_new_trade(
        make_account(), make_spread_legs(), open_position_groups=2, reserved_risk_capital=0,
    )
    assert not decision.approved
    assert "concurrent positions" in decision.reason


def test_rejects_when_capital_deployment_cap_reached():
    engine = RiskEngine(make_settings(max_capital_deployed_pct=60))
    engine.mark_new_trading_day(date(2026, 1, 1), 100_000)
    decision = engine.evaluate_new_trade(
        make_account(), make_spread_legs(),
        open_position_groups=0, reserved_risk_capital=60_000,  # already at the 60% cap
    )
    assert not decision.approved
    assert "Capital deployment cap" in decision.reason


def test_daily_loss_limit_blocks_new_entries_for_the_rest_of_the_day():
    engine = RiskEngine(make_settings(daily_loss_limit_pct=4))
    engine.mark_new_trading_day(date(2026, 1, 1), 100_000)
    losing_account = make_account(equity=95_000)  # -5%, past the 4% limit
    decision = engine.evaluate_new_trade(
        losing_account, make_spread_legs(), open_position_groups=0, reserved_risk_capital=0,
    )
    assert not decision.approved
    assert "Daily loss limit" in decision.reason


def test_drawdown_circuit_breaker_halts_and_persists_until_manually_cleared():
    engine = RiskEngine(make_settings(drawdown_circuit_breaker_pct=10))
    engine.mark_new_trading_day(date(2026, 1, 1), 100_000)
    engine.update_equity(100_000)
    engine.update_equity(88_000)  # -12% from peak, past the 10% breaker
    assert engine.is_halted

    decision = engine.evaluate_new_trade(
        make_account(equity=88_000), make_spread_legs(),
        open_position_groups=0, reserved_risk_capital=0,
    )
    assert not decision.approved
    assert "Drawdown circuit breaker" in decision.reason

    # A new trading day alone must NOT clear it -- only an explicit manual clear.
    engine.mark_new_trading_day(date(2026, 1, 2), 88_000)
    assert engine.is_halted

    engine.clear_drawdown_halt()
    assert not engine.is_halted


def test_kill_switch_blocks_trades_until_cleared():
    engine = RiskEngine(make_settings())
    engine.mark_new_trading_day(date(2026, 1, 1), 100_000)
    engine.trip_kill_switch("manual test trip")
    decision = engine.evaluate_new_trade(
        make_account(), make_spread_legs(), open_position_groups=0, reserved_risk_capital=0,
    )
    assert not decision.approved
    assert "Kill switch" in decision.reason

    engine.clear_kill_switch()
    decision = engine.evaluate_new_trade(
        make_account(), make_spread_legs(), open_position_groups=0, reserved_risk_capital=0,
    )
    assert decision.approved


def test_rejects_when_projected_portfolio_delta_exceeds_cap():
    engine = RiskEngine(make_settings(max_portfolio_delta=1))
    engine.mark_new_trading_day(date(2026, 1, 1), 100_000)
    decision = engine.evaluate_new_trade(
        make_account(), make_spread_legs(), open_position_groups=0, reserved_risk_capital=0,
    )
    assert not decision.approved
    assert "delta" in decision.reason


def test_rejects_when_projected_portfolio_theta_breaches_floor():
    engine = RiskEngine(make_settings(max_portfolio_theta=1_000_000))  # impossible floor
    engine.mark_new_trading_day(date(2026, 1, 1), 100_000)
    decision = engine.evaluate_new_trade(
        make_account(), make_spread_legs(), open_position_groups=0, reserved_risk_capital=0,
    )
    assert not decision.approved
    assert "theta" in decision.reason


def test_rejects_when_projected_portfolio_vega_exceeds_cap():
    engine = RiskEngine(make_settings(max_portfolio_vega=0.001))
    engine.mark_new_trading_day(date(2026, 1, 1), 100_000)
    decision = engine.evaluate_new_trade(
        make_account(), make_spread_legs(), open_position_groups=0, reserved_risk_capital=0,
    )
    assert not decision.approved
    assert "vega" in decision.reason


def test_undefined_risk_trade_is_rejected_with_clear_reason():
    from robinhood_bot.strategy.definitions import covered_call

    as_of = datetime(2026, 1, 1, tzinfo=timezone.utc)
    chain = build_simulated_chain(underlying="TEST", spot=100, as_of=as_of, iv=0.3)
    naked_call_legs = covered_call(chain, target_delta=0.30)

    engine = RiskEngine(make_settings())
    engine.mark_new_trading_day(date(2026, 1, 1), 100_000)
    decision = engine.evaluate_new_trade(
        make_account(), naked_call_legs, open_position_groups=0, reserved_risk_capital=0,
    )
    assert not decision.approved
    assert "unbounded" in decision.reason


def test_export_import_state_round_trips_peak_equity_and_daily_baseline():
    engine = RiskEngine(make_settings())
    engine.mark_new_trading_day(date(2026, 1, 1), 100_000)
    engine.update_equity(105_000)  # bumps peak equity

    restored = RiskEngine(make_settings())
    restored.import_state(engine.export_state())

    assert restored._peak_equity == 105_000
    assert restored._daily_start_equity == 100_000
    assert restored._current_day == date(2026, 1, 1)
    assert restored.is_halted is False


def test_export_import_state_round_trips_halt_flags():
    engine = RiskEngine(make_settings())
    engine.mark_new_trading_day(date(2026, 1, 1), 100_000)
    engine.trip_kill_switch("test")

    restored = RiskEngine(make_settings())
    restored.import_state(engine.export_state())

    assert restored.is_halted is True
    assert restored._halt_reason() == "Kill switch is active."


def test_export_state_before_any_trading_day_round_trips_none_fields():
    engine = RiskEngine(make_settings())

    restored = RiskEngine(make_settings())
    restored.import_state(engine.export_state())

    assert restored._peak_equity is None
    assert restored._daily_start_equity is None
    assert restored._current_day is None
