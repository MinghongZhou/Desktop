import pytest

from robinhood_bot.backtest.engine import BacktestConfig
from robinhood_bot.backtest.sensitivity import run_execution_sensitivity, run_iv_sensitivity
from robinhood_bot.ledger.store import Ledger

from conftest import make_price_series


@pytest.fixture
def ledger(tmp_path):
    lg = Ledger(tmp_path / "sensitivity_ledger.sqlite3")
    yield lg
    lg.close()


@pytest.fixture
def price_df_long():
    return make_price_series(n=320)


def test_iv_sensitivity_returns_one_result_per_multiplier(price_df_long, ledger, risk_settings):
    config = BacktestConfig(ticker="TEST", iv_rank_threshold=0.0, dte_target=10)
    results = run_iv_sensitivity(price_df_long, config, risk_settings, ledger, iv_multipliers=(0.7, 1.0, 1.3))
    assert set(results.keys()) == {0.7, 1.0, 1.3}
    for result in results.values():
        assert len(result.equity_curve) > 0


def test_execution_sensitivity_default_scenarios_present(price_df_long, ledger, risk_settings):
    config = BacktestConfig(ticker="TEST", iv_rank_threshold=0.0, dte_target=10)
    results = run_execution_sensitivity(price_df_long, config, risk_settings, ledger)
    assert set(results.keys()) == {"perfect_fills", "moderate_friction", "high_friction"}


def test_execution_sensitivity_friction_never_helps(price_df_long, ledger, risk_settings):
    # Slippage changes entry fill prices, which shifts early-exit trigger
    # points and can cascade into different trade sequences between
    # scenarios -- disable it so this stays a clean "same trades, worse
    # prices" comparison. See the equivalent note in test_backtest_engine.py.
    config = BacktestConfig(ticker="TEST", iv_rank_threshold=0.0, dte_target=10, enable_early_exit=False)
    results = run_execution_sensitivity(price_df_long, config, risk_settings, ledger)

    orders = ledger.recent_orders(run_id=results["perfect_fills"].run_id, limit=10_000)
    assert len(orders) > 0  # sanity: comparison is meaningless with zero trades

    assert results["perfect_fills"].final_equity >= results["moderate_friction"].final_equity
    assert results["moderate_friction"].final_equity >= results["high_friction"].final_equity
