from datetime import date

import pytest

from robinhood_bot.backtest.engine import MIN_HISTORY_DAYS, BacktestConfig
from robinhood_bot.broker.shadow import ShadowBrokerClient
from robinhood_bot.execution.paper_loop import _run_one_cycle, run_paper_trading_daemon
from robinhood_bot.ledger.store import Ledger
from robinhood_bot.risk.engine import RiskEngine

from conftest import make_price_series


@pytest.fixture
def ledger(tmp_path):
    lg = Ledger(tmp_path / "paper_loop_ledger.sqlite3")
    yield lg
    lg.close()


class FakeClock:
    """Returns a new date each call, simulating one day passing per cycle."""
    def __init__(self, start: date, days: list[int]):
        self._start = start
        self._days = iter(days)

    def __call__(self) -> date:
        from datetime import timedelta
        return self._start + timedelta(days=next(self._days))


class RecordingAlerter:
    def __init__(self):
        self.events = []

    def send(self, event):
        self.events.append(event)


def make_growing_price_feed(max_extra_days: int):
    """Returns a callable that yields a price series one day longer each
    call, simulating a live feed accumulating history over cycles."""
    full_series = make_price_series(n=MIN_HISTORY_DAYS + max_extra_days, drift=0.001, vol=0.02)
    state = {"days_added": 0}

    def _fetch():
        n = MIN_HISTORY_DAYS + state["days_added"]
        state["days_added"] = min(state["days_added"] + 1, max_extra_days)
        return full_series.iloc[:n]

    return _fetch


def test_runs_exactly_max_cycles_and_sleeps_between_not_after(ledger, risk_settings):
    broker = ShadowBrokerClient(starting_cash=100_000)
    risk_engine = RiskEngine(risk_settings)
    config = BacktestConfig(ticker="TEST", iv_rank_threshold=0.0, dte_target=10)
    fetch_price_df = make_growing_price_feed(max_extra_days=5)

    sleep_calls = []
    cycles = run_paper_trading_daemon(
        broker, risk_engine, ledger, "paper_run", config, fetch_price_df,
        sleep_fn=lambda seconds: sleep_calls.append(seconds),
        clock_fn=FakeClock(date(2026, 1, 1), days=[0, 1, 2]),
        max_cycles=3,
    )
    assert cycles == 3
    assert len(sleep_calls) == 2  # sleeps between cycles, not after the last one


def test_skips_cycle_when_clock_returns_same_date_twice(ledger, risk_settings):
    broker = ShadowBrokerClient(starting_cash=100_000)
    risk_engine = RiskEngine(risk_settings)
    config = BacktestConfig(ticker="TEST", iv_rank_threshold=0.0, dte_target=10)
    fetch_price_df = make_growing_price_feed(max_extra_days=5)

    call_count = {"n": 0}

    def counting_fetch():
        call_count["n"] += 1
        return fetch_price_df()

    # Same date twice in a row (woke up early) should not trigger a second fetch/cycle.
    # Sequence: day0 (run, cycle 1) -> day0 again (skip) -> day1 (run, cycle 2 -> stop).
    cycles = run_paper_trading_daemon(
        broker, risk_engine, ledger, "paper_run", config, counting_fetch,
        sleep_fn=lambda seconds: None,
        clock_fn=FakeClock(date(2026, 1, 1), days=[0, 0, 1]),
        max_cycles=2,
    )
    assert cycles == 2
    assert call_count["n"] == 2  # only fetched on the 2 cycles that actually ran


def test_ledger_accumulates_across_cycles(ledger, risk_settings):
    broker = ShadowBrokerClient(starting_cash=100_000)
    risk_engine = RiskEngine(risk_settings)
    config = BacktestConfig(ticker="TEST", iv_rank_threshold=0.0, dte_target=10)
    fetch_price_df = make_growing_price_feed(max_extra_days=5)

    run_paper_trading_daemon(
        broker, risk_engine, ledger, "paper_run", config, fetch_price_df,
        sleep_fn=lambda seconds: None,
        clock_fn=FakeClock(date(2026, 1, 1), days=[0, 1, 2, 3]),
        max_cycles=4,
    )
    equity_curve = ledger.equity_curve(run_id="paper_run")
    assert len(equity_curve) == 4  # one snapshot per cycle


def test_alerter_never_fires_when_no_trade_is_ever_considered(ledger, risk_settings):
    """With an impossible IV-rank threshold, no risk_decision row is ever
    recorded -- confirms the alerter path doesn't spuriously fire off
    something that was never actually written to the ledger."""
    broker = ShadowBrokerClient(starting_cash=100_000)
    risk_engine = RiskEngine(risk_settings)
    config = BacktestConfig(ticker="TEST", iv_rank_threshold=101.0, dte_target=10)
    fetch_price_df = make_growing_price_feed(max_extra_days=8)
    alerter = RecordingAlerter()

    run_paper_trading_daemon(
        broker, risk_engine, ledger, "paper_run", config, fetch_price_df,
        alerter=alerter,
        sleep_fn=lambda seconds: None,
        clock_fn=FakeClock(date(2026, 1, 1), days=list(range(6))),
        max_cycles=6,
    )
    assert alerter.events == []
    assert ledger.recent_risk_decisions(run_id="paper_run", limit=10_000) == []


def test_run_one_cycle_does_not_realert_on_a_stale_preexisting_row(ledger, risk_settings):
    """Directly exercises the dedup guard in _run_one_cycle: a
    halt-worthy row already sitting in the ledger from a previous cycle
    must not cause a fresh alert on a cycle that adds no new row."""
    broker = ShadowBrokerClient(starting_cash=100_000)
    risk_engine = RiskEngine(risk_settings)
    alerter = RecordingAlerter()

    # Seed a stale halt-worthy row as if a previous cycle recorded it.
    ledger.record_risk_decision(
        "paper_run", "paper", "bull_put_spread", approved=False,
        reason="Kill switch is active.", suggested_quantity=0, max_loss_per_unit=None,
    )

    # This cycle guarantees NO_TRADE (impossible threshold), so no new row
    # should be added, and therefore no new alert should fire.
    no_trade_config = BacktestConfig(ticker="TEST", iv_rank_threshold=101.0, dte_target=10)
    price_df = make_price_series(n=MIN_HISTORY_DAYS + 1)
    _run_one_cycle(broker, risk_engine, ledger, "paper_run", no_trade_config, price_df, alerter)

    assert alerter.events == []


def test_on_cycle_complete_fires_once_per_completed_cycle_not_after_skips(ledger, risk_settings):
    broker = ShadowBrokerClient(starting_cash=100_000)
    risk_engine = RiskEngine(risk_settings)
    config = BacktestConfig(ticker="TEST", iv_rank_threshold=0.0, dte_target=10)
    fetch_price_df = make_growing_price_feed(max_extra_days=5)

    calls = []
    cycles = run_paper_trading_daemon(
        broker, risk_engine, ledger, "paper_run", config, fetch_price_df,
        sleep_fn=lambda seconds: None,
        # Same date repeated once (a skipped cycle) must not trigger a callback.
        clock_fn=FakeClock(date(2026, 1, 1), days=[0, 0, 1, 2]),
        max_cycles=3,
        on_cycle_complete=lambda: calls.append(True),
    )
    assert cycles == 3
    assert len(calls) == 3
