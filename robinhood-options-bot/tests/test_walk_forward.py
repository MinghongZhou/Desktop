import pytest

from robinhood_bot.backtest.engine import MIN_HISTORY_DAYS, BacktestConfig
from robinhood_bot.backtest.walk_forward import run_walk_forward
from robinhood_bot.ledger.store import Ledger

from conftest import make_price_series


@pytest.fixture
def ledger(tmp_path):
    lg = Ledger(tmp_path / "walk_forward_ledger.sqlite3")
    yield lg
    lg.close()


def test_folds_produce_distinct_run_ids(ledger, risk_settings):
    price_df = make_price_series(n=MIN_HISTORY_DAYS + 90)
    config = BacktestConfig(ticker="TEST")
    results = run_walk_forward(price_df, config, risk_settings, ledger, n_folds=3)
    assert len(results) == 3
    assert len({r.run_id for r in results}) == 3


def test_folds_cover_all_tradable_days_without_overlap(ledger, risk_settings):
    price_df = make_price_series(n=MIN_HISTORY_DAYS + 90)
    config = BacktestConfig(ticker="TEST")
    results = run_walk_forward(price_df, config, risk_settings, ledger, n_folds=3)

    total_fold_days = sum(len(r.equity_curve) for r in results)
    expected_tradable_days = len(price_df) - MIN_HISTORY_DAYS
    assert total_fold_days == expected_tradable_days


def test_raises_when_not_enough_history_for_requested_folds(ledger, risk_settings):
    price_df = make_price_series(n=MIN_HISTORY_DAYS + 2)
    config = BacktestConfig(ticker="TEST")
    with pytest.raises(ValueError, match="Not enough history"):
        run_walk_forward(price_df, config, risk_settings, ledger, n_folds=5)


def test_rejects_non_positive_fold_count(ledger, risk_settings):
    price_df = make_price_series(n=MIN_HISTORY_DAYS + 90)
    config = BacktestConfig(ticker="TEST")
    with pytest.raises(ValueError, match="n_folds"):
        run_walk_forward(price_df, config, risk_settings, ledger, n_folds=0)
