import pytest

from robinhood_bot.backtest.engine import MIN_HISTORY_DAYS, BacktestConfig, run_backtest
from robinhood_bot.ledger.store import Ledger

from conftest import make_price_series


@pytest.fixture
def ledger(tmp_path):
    lg = Ledger(tmp_path / "backtest_ledger.sqlite3")
    yield lg
    lg.close()


def test_raises_on_insufficient_history(ledger, risk_settings):
    short_df = make_price_series(n=MIN_HISTORY_DAYS - 1)
    config = BacktestConfig(ticker="TEST")
    with pytest.raises(ValueError, match="warmup"):
        run_backtest(short_df, config, risk_settings, ledger)


def test_equity_curve_length_matches_tradable_days(price_df, ledger, risk_settings):
    config = BacktestConfig(ticker="TEST")
    result = run_backtest(price_df, config, risk_settings, ledger)
    expected_tradable_days = len(price_df) - MIN_HISTORY_DAYS
    assert len(result.equity_curve) == expected_tradable_days


def test_signal_recorded_for_every_tradable_day(price_df, ledger, risk_settings):
    config = BacktestConfig(ticker="TEST")
    result = run_backtest(price_df, config, risk_settings, ledger)
    signals = ledger.recent_signals(run_id=result.run_id, limit=10_000)
    assert len(signals) == len(price_df) - MIN_HISTORY_DAYS


def test_impossible_iv_rank_threshold_means_no_trades_ever(price_df, ledger, risk_settings):
    config = BacktestConfig(ticker="TEST", iv_rank_threshold=101.0)
    result = run_backtest(price_df, config, risk_settings, ledger)
    assert result.final_equity == pytest.approx(config.starting_cash)
    orders = ledger.recent_orders(run_id=result.run_id, limit=10_000)
    assert orders == []


def test_trades_happen_with_permissive_threshold_and_get_settled(price_df, ledger, risk_settings):
    config = BacktestConfig(ticker="TEST", iv_rank_threshold=0.0, dte_target=10)
    result = run_backtest(price_df, config, risk_settings, ledger)
    orders = ledger.recent_orders(run_id=result.run_id, limit=10_000)
    assert len(orders) > 0

    opens = [o for o in orders if not o["strategy_tag"].endswith("_expiration_settlement")]
    settlements = [o for o in orders if o["strategy_tag"].endswith("_expiration_settlement")]
    assert len(opens) > 0
    # With a 10-day DTE target and 300+ tradable days, essentially every
    # opened position should have expired and settled by the end.
    assert len(settlements) > 0


def test_commission_strictly_reduces_final_equity_when_trades_occur(price_df, ledger, risk_settings):
    base_config = BacktestConfig(ticker="TEST", iv_rank_threshold=0.0, dte_target=10)
    free_result = run_backtest(price_df, base_config, risk_settings, ledger)

    priced_config = BacktestConfig(
        ticker="TEST", iv_rank_threshold=0.0, dte_target=10, commission_per_contract=5.0,
    )
    priced_result = run_backtest(price_df, priced_config, risk_settings, ledger)

    orders = ledger.recent_orders(run_id=free_result.run_id, limit=10_000)
    assert len(orders) > 0  # sanity: the comparison is meaningless with zero trades
    assert priced_result.final_equity < free_result.final_equity


def test_slippage_strictly_reduces_final_equity_when_trades_occur(price_df, ledger, risk_settings):
    base_config = BacktestConfig(ticker="TEST", iv_rank_threshold=0.0, dte_target=10)
    free_result = run_backtest(price_df, base_config, risk_settings, ledger)

    slipped_config = BacktestConfig(
        ticker="TEST", iv_rank_threshold=0.0, dte_target=10, slippage_pct=0.10,
    )
    slipped_result = run_backtest(price_df, slipped_config, risk_settings, ledger)

    assert slipped_result.final_equity < free_result.final_equity


def test_iv_multiplier_only_changes_pricing_not_signal_days(price_df, ledger, risk_settings):
    low_iv_config = BacktestConfig(ticker="TEST", iv_rank_threshold=0.0, dte_target=10, iv_multiplier=0.5)
    high_iv_config = BacktestConfig(ticker="TEST", iv_rank_threshold=0.0, dte_target=10, iv_multiplier=2.0)

    low_result = run_backtest(price_df, low_iv_config, risk_settings, ledger)
    high_result = run_backtest(price_df, high_iv_config, risk_settings, ledger)

    # Same number of signal-days regardless of the pricing multiplier --
    # the signal itself doesn't depend on iv_multiplier.
    low_signals = ledger.recent_signals(run_id=low_result.run_id, limit=10_000)
    high_signals = ledger.recent_signals(run_id=high_result.run_id, limit=10_000)
    assert len(low_signals) == len(high_signals)
