"""Proves run_backtest(price_df) and repeated run_live_trading_day() calls
over the same data produce identical ledger contents. This is the
architectural property Phase 7's live-vs-backtest comparison depends on:
paper trading isn't running "similar" logic to the backtest, it's calling
the exact same per-day function one day at a time."""
import pytest

from robinhood_bot.backtest.engine import MIN_HISTORY_DAYS, BacktestConfig, run_backtest, run_live_trading_day
from robinhood_bot.broker.shadow import ShadowBrokerClient
from robinhood_bot.ledger.store import Ledger
from robinhood_bot.risk.engine import RiskEngine

from conftest import make_price_series


@pytest.fixture
def ledger(tmp_path):
    lg = Ledger(tmp_path / "equivalence_ledger.sqlite3")
    yield lg
    lg.close()


def test_repeated_single_days_match_a_single_backtest_run(ledger, risk_settings):
    price_df = make_price_series(n=MIN_HISTORY_DAYS + 60, drift=0.001, vol=0.02)
    config = BacktestConfig(ticker="TEST", iv_rank_threshold=0.0, dte_target=10)

    backtest_result = run_backtest(price_df, config, risk_settings, ledger, run_id="batch_run")

    broker = ShadowBrokerClient(starting_cash=config.starting_cash)
    risk_engine = RiskEngine(risk_settings)
    for i in range(MIN_HISTORY_DAYS, len(price_df)):
        run_live_trading_day(
            broker, risk_engine, ledger, "incremental_run", config,
            price_df.iloc[: i + 1], mode="paper",
        )

    batch_account_equity = backtest_result.final_equity
    incremental_account_equity = broker.get_account().equity
    assert incremental_account_equity == pytest.approx(batch_account_equity)

    batch_signals = ledger.recent_signals(run_id="batch_run", limit=10_000)
    incremental_signals = ledger.recent_signals(run_id="incremental_run", limit=10_000)
    assert len(batch_signals) == len(incremental_signals)

    batch_orders = ledger.recent_orders(run_id="batch_run", limit=10_000)
    incremental_orders = ledger.recent_orders(run_id="incremental_run", limit=10_000)
    assert len(batch_orders) == len(incremental_orders)
    assert [o["strategy_tag"] for o in batch_orders] == [o["strategy_tag"] for o in incremental_orders]
    assert [o["fill_price"] for o in batch_orders] == [o["fill_price"] for o in incremental_orders]


def test_run_live_trading_day_raises_on_insufficient_history(ledger, risk_settings):
    short_df = make_price_series(n=MIN_HISTORY_DAYS - 1)
    broker = ShadowBrokerClient(starting_cash=100_000)
    risk_engine = RiskEngine(risk_settings)
    config = BacktestConfig(ticker="TEST")
    with pytest.raises(ValueError, match="warmup"):
        run_live_trading_day(broker, risk_engine, ledger, "run1", config, short_df)
