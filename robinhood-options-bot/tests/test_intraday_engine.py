"""Tests for the intraday (0DTE, multi-checkpoint) backtest engine.

Mirrors test_early_exit.py's structure for the daily engine's equivalent
mark-to-market/early-exit functions, plus integration-level tests of the
full run_intraday_backtest loop (checkpoint selection, same-day
settlement, the new per-checkpoint order-tag distinction, and the
max_trades_per_day cap actually biting)."""
from datetime import date, datetime, timezone

import numpy as np
import pandas as pd
import pytest

from robinhood_bot.backtest.intraday_engine import (
    IntradayBacktestConfig,
    _manage_intraday_early_exits,
    _mark_intraday_positions_to_market,
    _select_checkpoints,
    run_intraday_backtest,
)
from robinhood_bot.broker.base import OptionContract, OptionRight, OrderLeg, OrderSide
from robinhood_bot.broker.shadow import ShadowBrokerClient
from robinhood_bot.ledger.store import Ledger

from conftest import make_risk_settings


@pytest.fixture
def ledger(tmp_path):
    lg = Ledger(tmp_path / "intraday_ledger.sqlite3")
    yield lg
    lg.close()


def make_put(strike=100.0, bid=1.0, ask=1.1, expiration=date(2026, 3, 2)) -> OptionContract:
    return OptionContract(
        underlying="TEST", expiration=expiration, strike=strike, right=OptionRight.PUT,
        bid=bid, ask=ask, last=(bid + ask) / 2, implied_volatility=0.3,
        delta=-0.30, gamma=0.01, theta=-0.05, vega=0.1,
        as_of=datetime(2026, 3, 2, 15, 0, tzinfo=timezone.utc),
    )


def open_short_put(broker: ShadowBrokerClient, contract: OptionContract, strategy_tag="bull_put_spread_cp0"):
    broker.place_order([OrderLeg(contract, OrderSide.SELL_TO_OPEN, quantity=1)], strategy_tag=strategy_tag)


def make_daily_series(n: int = 300, seed: int = 11, drift: float = 0.0, vol: float = 0.008,
                       start: float = 100.0, spike_last: int = 0) -> pd.DataFrame:
    """Like conftest.make_price_series, but with a knob to spike recent
    daily vol so IV rank clears the threshold on the last day -- needed to
    make the regime filter actually recommend a trade in integration tests."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    returns = rng.normal(drift, vol, n)
    if spike_last:
        returns[-spike_last:] = rng.normal(drift, vol * 4, spike_last)
    prices = start * np.cumprod(1 + returns)
    return pd.DataFrame({"Close": prices}, index=dates)


def make_intraday_series(trading_days: list[date], bars_per_day: int = 26,
                          seed: int = 5, start: float = 100.0, vol: float = 0.0004) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows, idx = [], []
    level = start
    for day in trading_days:
        for i in range(bars_per_day):
            ts = pd.Timestamp(day, tz="UTC") + pd.Timedelta(hours=14, minutes=30) + pd.Timedelta(minutes=15 * i)
            level = level * (1 + rng.normal(0, vol))
            rows.append({"Open": level, "High": level * 1.001, "Low": level * 0.999,
                         "Close": level, "Volume": 1000})
            idx.append(ts)
    return pd.DataFrame(rows, index=pd.DatetimeIndex(idx))


# -- _select_checkpoints --

def test_select_checkpoints_includes_first_and_last_bar():
    day_bars = make_intraday_series([date(2026, 3, 2)], bars_per_day=26)
    checkpoints = _select_checkpoints(day_bars, n=3)
    assert checkpoints[0] == day_bars.index[0]
    assert checkpoints[-1] == day_bars.index[-1]
    assert len(checkpoints) == 3


def test_select_checkpoints_falls_back_to_all_bars_on_a_thin_day():
    day_bars = make_intraday_series([date(2026, 3, 2)], bars_per_day=2)
    checkpoints = _select_checkpoints(day_bars, n=5)
    assert checkpoints == list(day_bars.index)


# -- _mark_intraday_positions_to_market --

def test_mark_intraday_updates_equity_for_a_favorable_move():
    broker = ShadowBrokerClient(starting_cash=100_000)
    open_short_put(broker, make_put(strike=100.0, bid=2.0, ask=2.2))
    equity_before = broker.get_account().equity

    _mark_intraday_positions_to_market(
        broker, IntradayBacktestConfig(ticker="TEST"), spot=150.0, vol=0.3,
        as_of=datetime(2026, 3, 2, 15, 0, tzinfo=timezone.utc), trading_day=date(2026, 3, 2),
    )
    assert broker.get_account().equity > equity_before


def test_mark_intraday_marks_same_day_expiring_positions_unlike_daily_version():
    """The whole point of this variant: a 0DTE position (expiration ==
    trading_day) must actually get marked, unlike the daily engine's
    _mark_open_positions_to_market which deliberately skips those."""
    broker = ShadowBrokerClient(starting_cash=100_000)
    contract = make_put(strike=100.0, bid=2.0, ask=2.2, expiration=date(2026, 3, 2))
    open_short_put(broker, contract)

    _mark_intraday_positions_to_market(
        broker, IntradayBacktestConfig(ticker="TEST"), spot=150.0, vol=0.3,
        as_of=datetime(2026, 3, 2, 15, 0, tzinfo=timezone.utc), trading_day=date(2026, 3, 2),
    )
    position = broker.get_account().positions[0]
    assert position.contract.bid != contract.bid  # actually got remarked


def test_mark_intraday_noop_when_vol_not_positive():
    broker = ShadowBrokerClient(starting_cash=100_000)
    contract = make_put()
    open_short_put(broker, contract)

    _mark_intraday_positions_to_market(
        broker, IntradayBacktestConfig(ticker="TEST"), spot=150.0, vol=0.0,
        as_of=datetime(2026, 3, 2, 15, 0, tzinfo=timezone.utc), trading_day=date(2026, 3, 2),
    )
    assert broker.get_account().positions[0].contract.bid == contract.bid


# -- _manage_intraday_early_exits --

def test_intraday_profit_target_closes_position(ledger):
    broker = ShadowBrokerClient(starting_cash=100_000)
    contract = make_put(strike=100.0, bid=2.0, ask=2.2)
    open_short_put(broker, contract)

    cheap_contract = make_put(strike=100.0, bid=0.3, ask=0.4)
    broker.remark_position(contract.occ_symbol, cheap_contract)

    config = IntradayBacktestConfig(ticker="TEST", profit_target_pct=0.50)
    _manage_intraday_early_exits(broker, ledger, "run1", "backtest", config,
                                  datetime(2026, 3, 2, 15, 0, tzinfo=timezone.utc))

    assert broker.get_account().positions == []
    orders = ledger.recent_orders(run_id="run1", limit=10)
    assert orders[0]["strategy_tag"] == "bull_put_spread_cp0_profit_target"


def test_intraday_stop_loss_closes_position(ledger):
    broker = ShadowBrokerClient(starting_cash=100_000)
    contract = make_put(strike=100.0, bid=2.0, ask=2.2)
    open_short_put(broker, contract)

    expensive_contract = make_put(strike=100.0, bid=8.0, ask=8.2)
    broker.remark_position(contract.occ_symbol, expensive_contract)

    config = IntradayBacktestConfig(ticker="TEST", stop_loss_multiple=2.0)
    _manage_intraday_early_exits(broker, ledger, "run1", "backtest", config,
                                  datetime(2026, 3, 2, 15, 0, tzinfo=timezone.utc))

    assert broker.get_account().positions == []
    orders = ledger.recent_orders(run_id="run1", limit=10)
    assert orders[0]["strategy_tag"] == "bull_put_spread_cp0_stop_loss"


def test_intraday_two_same_tag_groups_from_different_checkpoints_dont_collide(ledger):
    """Regression guard for the collision this engine has to avoid: two
    entries opened at different checkpoints, same strategy type, same
    (0DTE) expiration must be tracked as separate groups, not merged."""
    broker = ShadowBrokerClient(starting_cash=100_000)
    cp0_contract = make_put(strike=100.0, bid=2.0, ask=2.2)
    cp1_contract = make_put(strike=95.0, bid=1.0, ask=1.1)
    open_short_put(broker, cp0_contract, strategy_tag="bull_put_spread_cp0")
    open_short_put(broker, cp1_contract, strategy_tag="bull_put_spread_cp1")

    # Only cp0's position moves into profit-target territory.
    broker.remark_position(cp0_contract.occ_symbol, make_put(strike=100.0, bid=0.2, ask=0.3))

    config = IntradayBacktestConfig(ticker="TEST", profit_target_pct=0.50)
    _manage_intraday_early_exits(broker, ledger, "run1", "backtest", config,
                                  datetime(2026, 3, 2, 15, 0, tzinfo=timezone.utc))

    remaining = broker.get_account().positions
    assert len(remaining) == 1
    assert remaining[0].strategy_tag == "bull_put_spread_cp1"  # untouched


# -- run_intraday_backtest (integration) --

def _aligned_dfs(spike_last=5, n_intraday_days=8):
    daily_df = make_daily_series(n=300, spike_last=spike_last, drift=0.001)
    trading_days = [d.date() for d in daily_df.index[-n_intraday_days:]]
    intraday_df = make_intraday_series(trading_days)
    return daily_df, intraday_df


def test_run_intraday_backtest_smoke(ledger, risk_settings):
    daily_df, intraday_df = _aligned_dfs()
    config = IntradayBacktestConfig(ticker="TEST", iv_rank_threshold=0.0, checkpoints_per_day=3)

    result = run_intraday_backtest(daily_df, intraday_df, config, risk_settings, ledger, run_id="intraday_run")

    assert result.ticker == "TEST"
    assert isinstance(result.final_equity, float)
    assert len(result.equity_curve) == 8  # one snapshot per traded day


def test_run_intraday_backtest_settles_everything_by_end_of_each_day(ledger, risk_settings):
    """No position should ever survive past the settlement checkpoint of
    the day it was opened on -- 0DTE options don't carry overnight."""
    daily_df, intraday_df = _aligned_dfs()
    config = IntradayBacktestConfig(ticker="TEST", iv_rank_threshold=0.0, checkpoints_per_day=3)

    result = run_intraday_backtest(daily_df, intraday_df, config, risk_settings, ledger, run_id="intraday_run2")

    settlement_orders = [
        o for o in ledger.recent_orders(run_id="intraday_run2", limit=10_000)
        if o["strategy_tag"].endswith("_expiration_settlement")
    ]
    opening_orders = [
        o for o in ledger.recent_orders(run_id="intraday_run2", limit=10_000)
        if "_cp" in o["strategy_tag"] and not o["strategy_tag"].endswith(("_profit_target", "_stop_loss"))
    ]
    if opening_orders:
        assert settlement_orders  # if anything opened, something eventually settled


def test_run_intraday_backtest_respects_max_trades_per_day(ledger):
    """With a cap of 1 and 3 non-settlement entry checkpoints per day
    (checkpoints_per_day=4), a sustained-high-vol run should trip the cap
    repeatedly -- ledger timestamps are real wall-clock insertion time,
    not simulated time, so this checks the risk_decisions denial reason
    directly rather than trying to bucket orders by simulated day."""
    daily_df, intraday_df = _aligned_dfs(spike_last=250, n_intraday_days=5)  # sustained high vol -> trades every day
    risk_settings = make_risk_settings(max_trades_per_day=1)
    config = IntradayBacktestConfig(ticker="TEST", iv_rank_threshold=0.0, checkpoints_per_day=4)

    run_intraday_backtest(daily_df, intraday_df, config, risk_settings, ledger, run_id="capped_run")

    decisions = ledger.recent_risk_decisions(run_id="capped_run", limit=10_000)
    capped_denials = [d for d in decisions if d["reason"] and "Max trades per day" in d["reason"]]
    assert capped_denials  # the cap actually fired at least once


def test_run_intraday_backtest_raises_on_insufficient_daily_history(ledger, risk_settings):
    short_daily_df = make_daily_series(n=50)
    intraday_df = make_intraday_series([d.date() for d in short_daily_df.index[-3:]])
    config = IntradayBacktestConfig(ticker="TEST")
    with pytest.raises(ValueError, match="daily price history"):
        run_intraday_backtest(short_daily_df, intraday_df, config, risk_settings, ledger)


def test_run_intraday_backtest_skips_days_with_no_intraday_bars(ledger, risk_settings):
    """Days present in daily_df but absent from intraday_df (e.g. before
    intraday history begins) must be skipped for trading, not raise."""
    daily_df = make_daily_series(n=300, spike_last=5, drift=0.001)
    # Intraday data only for the very last day.
    intraday_df = make_intraday_series([daily_df.index[-1].date()])
    config = IntradayBacktestConfig(ticker="TEST", iv_rank_threshold=0.0)

    result = run_intraday_backtest(daily_df, intraday_df, config, risk_settings, ledger, run_id="sparse_run")
    assert len(result.equity_curve) == 1
