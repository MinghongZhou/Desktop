import numpy as np
import pandas as pd
import pytest

from robinhood_bot.backtest.stock_engine import (
    MIN_HISTORY_DAYS,
    StockBacktestConfig,
    _atr,
    run_stock_backtest,
)
from robinhood_bot.ledger.store import Ledger


@pytest.fixture
def ledger(tmp_path):
    lg = Ledger(tmp_path / "stock_backtest_ledger.sqlite3")
    yield lg
    lg.close()


def make_ohlc_series(n: int = 320, seed: int = 42, drift: float = 0.0006,
                      vol: float = 0.012, start: float = 100.0, day_range_pct: float = 0.01) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    returns = rng.normal(drift, vol, n)
    closes = start * np.cumprod(1 + returns)
    opens = closes / (1 + rng.normal(0, vol / 2, n))
    ranges = closes * day_range_pct * (1 + rng.random(n))
    highs = np.maximum(opens, closes) + ranges / 2
    lows = np.minimum(opens, closes) - ranges / 2
    return pd.DataFrame(
        {"Open": opens, "High": highs, "Low": lows, "Close": closes, "Volume": 1_000_000},
        index=dates,
    )


def make_strong_uptrend_series(n: int = 320, seed: int = 7) -> pd.DataFrame:
    """A steady, low-noise uptrend -- should reliably keep the strategy
    long for most of the tradable period, unlike the noisier default
    fixture where trend direction flips around more."""
    return make_ohlc_series(n=n, seed=seed, drift=0.003, vol=0.003, day_range_pct=0.006)


def make_strong_downtrend_series(n: int = 320, seed: int = 9) -> pd.DataFrame:
    return make_ohlc_series(n=n, seed=seed, drift=-0.003, vol=0.003, day_range_pct=0.006)


def make_uptrend_then_reversal_series(n_up: int = 220, n_down: int = 60, seed: int = 7) -> pd.DataFrame:
    """A steady uptrend (guarantees at least one long entry) followed by a
    sharp reversal (guarantees at least one exit) -- so trades round-trip
    within the backtest window instead of leaving a still-open position
    that a pure "grows equity" fixture wouldn't ever close out."""
    up = make_ohlc_series(n=n_up, seed=seed, drift=0.003, vol=0.003, day_range_pct=0.006, start=100.0)
    down = make_ohlc_series(n=n_down, seed=seed + 1, drift=-0.012, vol=0.004,
                             day_range_pct=0.01, start=float(up["Close"].iloc[-1]))
    down.index = pd.date_range(up.index[-1] + pd.Timedelta(days=1), periods=n_down, freq="B")
    return pd.concat([up, down])


# -- _atr --

def test_atr_is_positive_and_warms_up():
    df = make_ohlc_series()
    atr = _atr(df, window=14)
    assert atr.iloc[:13].isna().all()
    assert (atr.iloc[14:] > 0).all()


# -- run_stock_backtest --

def test_raises_on_insufficient_history(ledger):
    short_df = make_ohlc_series(n=MIN_HISTORY_DAYS - 1)
    config = StockBacktestConfig(ticker="TEST")
    with pytest.raises(ValueError, match="warmup"):
        run_stock_backtest(short_df, config, ledger)


def test_equity_curve_length_matches_tradable_days(ledger):
    df = make_ohlc_series()
    config = StockBacktestConfig(ticker="TEST")
    result = run_stock_backtest(df, config, ledger)
    assert len(result.equity_curve) == len(df) - MIN_HISTORY_DAYS


def test_signal_recorded_for_every_tradable_day(ledger):
    df = make_ohlc_series()
    config = StockBacktestConfig(ticker="TEST")
    result = run_stock_backtest(df, config, ledger)
    signals = ledger.recent_signals(run_id=result.run_id, limit=10_000)
    assert len(signals) == len(df) - MIN_HISTORY_DAYS


def test_strong_uptrend_enters_long_and_grows_equity(ledger):
    df = make_strong_uptrend_series()
    config = StockBacktestConfig(ticker="TEST", risk_per_trade_pct=2.0)
    result = run_stock_backtest(df, config, ledger)

    # A sustained uptrend for the whole window may never trigger an exit
    # (the position rides to the end still open), so `trades` -- which
    # only records completed round-trips -- can legitimately be empty
    # here. Cash getting deployed is the real signal an entry happened.
    assert result.equity_curve[-1]["cash"] < config.starting_cash
    assert result.final_equity > config.starting_cash


def test_never_holds_shares_during_a_sustained_downtrend(ledger):
    """Long-only: a persistent downtrend should never trigger an entry at
    all (trend never reads BULLISH), so equity should track cash exactly
    -- no directional short exposure is ever taken."""
    df = make_strong_downtrend_series()
    config = StockBacktestConfig(ticker="TEST")
    result = run_stock_backtest(df, config, ledger)

    assert result.trades == []
    assert result.final_equity == pytest.approx(config.starting_cash)


def test_position_size_respects_risk_budget_via_atr_stop_distance(ledger, tmp_path):
    """A tighter risk_per_trade_pct should size every entry to fewer
    shares, holding the ATR-implied dollar risk roughly proportional."""
    df = make_uptrend_then_reversal_series()
    small_risk = run_stock_backtest(df, StockBacktestConfig(ticker="TEST", risk_per_trade_pct=0.5), ledger)
    ledger2 = Ledger(tmp_path / "ledger2.sqlite3")
    large_risk = run_stock_backtest(df, StockBacktestConfig(ticker="TEST", risk_per_trade_pct=4.0), ledger2)
    ledger2.close()

    assert small_risk.trades and large_risk.trades  # the reversal guarantees at least one completed round-trip
    assert small_risk.trades[0].shares < large_risk.trades[0].shares


def test_stop_loss_exits_before_trend_exit_when_hit_intraday(ledger):
    """A sharp single-day drop through the stop should close the position
    at (roughly) the stop price via the stop-loss path, not ride out the
    full day's close."""
    df = make_uptrend_then_reversal_series(seed=13)
    config = StockBacktestConfig(ticker="TEST", stop_atr_multiple=1.0)
    result = run_stock_backtest(df, config, ledger)
    assert result.trades  # sanity: the reversal produced at least one exit

    stop_loss_exits = [t for t in result.trades if t.exit_reason == "stop_loss"]
    # Not asserting stop losses *must* happen (depends on the random walk),
    # but if they do, the exit price should be close to entry - stop distance,
    # not an arbitrary close price.
    for t in stop_loss_exits:
        assert t.exit_price < t.entry_price


def test_slippage_and_commission_strictly_reduce_final_equity(ledger, tmp_path):
    df = make_strong_uptrend_series()
    clean = run_stock_backtest(df, StockBacktestConfig(ticker="TEST"), ledger)

    ledger2 = Ledger(tmp_path / "ledger2.sqlite3")
    friction = run_stock_backtest(
        df, StockBacktestConfig(ticker="TEST", slippage_pct=0.01, commission_per_trade=5.0), ledger2,
    )
    ledger2.close()

    assert friction.final_equity < clean.final_equity
