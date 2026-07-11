import pytest

from robinhood_bot.monitoring.metrics import cagr, max_drawdown_pct, sharpe_ratio, summarize_equity_curve


def rows(*equities):
    return [{"equity": e} for e in equities]


def test_summarize_equity_curve_returns_none_when_empty():
    assert summarize_equity_curve([]) is None


def test_summarize_equity_curve_basic():
    summary = summarize_equity_curve(rows(100_000, 110_000, 105_000))
    assert summary.current_equity == 105_000
    assert summary.peak_equity == 110_000
    assert summary.drawdown_pct == pytest.approx((110_000 - 105_000) / 110_000 * 100)


def test_max_drawdown_captures_worst_peak_to_trough_not_just_latest():
    # Peak at 120k, trough at 90k (25% dd), then partial recovery to 100k
    # (only ~17% dd from peak) -- max_drawdown_pct must report the 25%, not
    # the smaller drawdown implied by the final point.
    curve = rows(100_000, 120_000, 90_000, 100_000)
    assert max_drawdown_pct(curve) == pytest.approx((120_000 - 90_000) / 120_000 * 100)


def test_max_drawdown_is_zero_for_monotonically_increasing_curve():
    assert max_drawdown_pct(rows(100_000, 110_000, 120_000)) == 0.0


def test_cagr_none_for_short_curves():
    assert cagr(rows(100_000)) is None
    assert cagr([]) is None


def test_cagr_positive_for_growing_equity():
    # 100k -> 121k over 2 periods with 252 periods/year should annualize huge,
    # just check the sign and that it's finite.
    growth_rate = cagr(rows(100_000, 110_000, 121_000), trading_days_per_year=252)
    assert growth_rate is not None
    assert growth_rate > 0


def test_sharpe_none_for_short_curves():
    assert sharpe_ratio(rows(100_000, 101_000)) is None


def test_sharpe_none_for_zero_volatility():
    assert sharpe_ratio(rows(100_000, 100_000, 100_000, 100_000)) is None


def test_sharpe_positive_for_consistent_gains():
    curve = rows(100_000, 101_000, 102_010, 103_030)
    sharpe = sharpe_ratio(curve)
    assert sharpe is not None
    assert sharpe > 0
