import pandas as pd
import pytest

from robinhood_bot.options_pricing.iv_rank import iv_rank_series, iv_percentile_series


def test_iv_rank_at_series_max_is_100():
    vol = pd.Series([0.1, 0.2, 0.3, 0.15, 0.4])
    rank = iv_rank_series(vol, window=5)
    # last value (0.4) is both the trailing max and current -> rank 100
    assert rank.iloc[-1] == pytest.approx(100.0)


def test_iv_rank_at_series_min_is_zero():
    vol = pd.Series([0.4, 0.3, 0.2, 0.35, 0.1])
    rank = iv_rank_series(vol, window=5)
    assert rank.iloc[-1] == pytest.approx(0.0)


def test_iv_rank_flat_window_is_neutral():
    vol = pd.Series([0.2] * 10)
    rank = iv_rank_series(vol, window=5)
    assert rank.iloc[-1] == pytest.approx(50.0)


def test_iv_percentile_all_time_high_is_100():
    vol = pd.Series([0.1, 0.15, 0.12, 0.18, 0.5])
    pct = iv_percentile_series(vol, window=5)
    assert pct.iloc[-1] == pytest.approx(100.0)
