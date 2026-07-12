import numpy as np
import pandas as pd
import pytest

from robinhood_bot.backtest.breakout_engine import (
    BreakoutBacktestConfig,
    run_breakout_backtest,
)
from robinhood_bot.ledger.store import Ledger


@pytest.fixture
def ledger(tmp_path):
    lg = Ledger(tmp_path / "breakout_ledger.sqlite3")
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


def make_flat_then_breakout_series(n_flat: int = 100, n_breakout: int = 150, seed: int = 3) -> pd.DataFrame:
    """A choppy flat period (should generate no breakout) followed by a
    strong sustained rally well above the prior range (guarantees a
    breakout entry, and gives the chandelier stop room to trail up)."""
    flat = make_ohlc_series(n=n_flat, seed=seed, drift=0.0, vol=0.006, day_range_pct=0.01, start=100.0)
    breakout = make_ohlc_series(n=n_breakout, seed=seed + 1, drift=0.004, vol=0.004,
                                 day_range_pct=0.006, start=float(flat["Close"].iloc[-1]))
    breakout.index = pd.date_range(flat.index[-1] + pd.Timedelta(days=1), periods=n_breakout, freq="B")
    return pd.concat([flat, breakout])


def make_breakout_then_reversal_series(n_flat=100, n_up=100, n_down=60, seed=11) -> pd.DataFrame:
    flat = make_ohlc_series(n=n_flat, seed=seed, drift=0.0, vol=0.006, day_range_pct=0.01, start=100.0)
    up = make_ohlc_series(n=n_up, seed=seed + 1, drift=0.004, vol=0.004, day_range_pct=0.006,
                           start=float(flat["Close"].iloc[-1]))
    up.index = pd.date_range(flat.index[-1] + pd.Timedelta(days=1), periods=n_up, freq="B")
    down = make_ohlc_series(n=n_down, seed=seed + 2, drift=-0.015, vol=0.005, day_range_pct=0.01,
                             start=float(up["Close"].iloc[-1]))
    down.index = pd.date_range(up.index[-1] + pd.Timedelta(days=1), periods=n_down, freq="B")
    return pd.concat([flat, up, down])


def test_raises_on_insufficient_history(ledger):
    from robinhood_bot.backtest.breakout_engine import MIN_HISTORY_DAYS
    short_df = make_ohlc_series(n=MIN_HISTORY_DAYS - 1)
    config = BreakoutBacktestConfig(ticker="TEST")
    with pytest.raises(ValueError, match="warmup"):
        run_breakout_backtest(short_df, config, ledger)


def test_no_breakout_during_a_flat_choppy_market(ledger):
    df = make_ohlc_series(n=250, seed=5, drift=0.0, vol=0.005, day_range_pct=0.008)
    config = BreakoutBacktestConfig(ticker="TEST", entry_window=55)
    result = run_breakout_backtest(df, config, ledger)
    # A genuinely flat/choppy series shouldn't reliably punch through its
    # own 55-day high -- not a hard guarantee for every seed, but true
    # enough here that a persistent open position would be a red flag.
    assert result.final_equity == pytest.approx(config.starting_cash, rel=0.05)


def test_breakout_enters_long_and_grows_equity(ledger):
    df = make_flat_then_breakout_series()
    config = BreakoutBacktestConfig(ticker="TEST", entry_window=55)
    result = run_breakout_backtest(df, config, ledger)

    assert result.equity_curve[-1]["cash"] < config.starting_cash  # capital got deployed
    assert result.final_equity > config.starting_cash


def test_chandelier_stop_trails_up_and_locks_in_gains_on_reversal(ledger):
    """After a sustained rally then a sharp reversal, the exit price
    should be well above the original entry -- proof the stop actually
    trailed up with the position instead of sitting fixed at entry."""
    df = make_breakout_then_reversal_series()
    config = BreakoutBacktestConfig(ticker="TEST", entry_window=55, stop_atr_multiple=3.0)
    result = run_breakout_backtest(df, config, ledger)

    assert result.trades  # the reversal should have closed out the position
    trade = result.trades[0]
    assert trade.exit_price > trade.entry_price  # stop trailed up, not a loss at exit


def test_signal_recorded_for_every_tradable_day(ledger):
    df = make_ohlc_series(n=250)
    config = BreakoutBacktestConfig(ticker="TEST", entry_window=55)
    result = run_breakout_backtest(df, config, ledger)
    signals = ledger.recent_signals(run_id=result.run_id, limit=10_000)
    assert len(signals) == len(result.equity_curve)


def test_position_size_respects_risk_budget(ledger, tmp_path):
    df = make_flat_then_breakout_series()
    starting_cash = 100_000
    small_risk = run_breakout_backtest(
        df, BreakoutBacktestConfig(ticker="TEST", entry_window=55, risk_per_trade_pct=0.5,
                                    starting_cash=starting_cash), ledger,
    )
    ledger2 = Ledger(tmp_path / "ledger2.sqlite3")
    large_risk = run_breakout_backtest(
        df, BreakoutBacktestConfig(ticker="TEST", entry_window=55, risk_per_trade_pct=4.0,
                                    starting_cash=starting_cash), ledger2,
    )
    ledger2.close()

    # Both entered something (equity moved away from starting cash)...
    assert small_risk.final_equity != starting_cash
    # ...but the larger risk budget bought more shares, so it captured a
    # bigger absolute gain from the same rally.
    assert large_risk.final_equity > small_risk.final_equity


def test_slippage_and_commission_strictly_reduce_final_equity(ledger, tmp_path):
    df = make_flat_then_breakout_series()
    clean = run_breakout_backtest(df, BreakoutBacktestConfig(ticker="TEST", entry_window=55), ledger)

    ledger2 = Ledger(tmp_path / "ledger2.sqlite3")
    friction = run_breakout_backtest(
        df, BreakoutBacktestConfig(ticker="TEST", entry_window=55, slippage_pct=0.01, commission_per_trade=5.0),
        ledger2,
    )
    ledger2.close()

    assert friction.final_equity < clean.final_equity
