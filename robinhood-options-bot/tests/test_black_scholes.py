import math

import pytest

from robinhood_bot.options_pricing.black_scholes import price_and_greeks


def test_call_price_matches_known_reference_value():
    # S=100, K=100, T=1, r=0.05, sigma=0.2, q=0 -> textbook value ~10.4506
    result = price_and_greeks(
        spot=100, strike=100, time_to_expiry_years=1,
        risk_free_rate=0.05, sigma=0.2, is_call=True,
    )
    assert result.price == pytest.approx(10.4506, abs=1e-3)
    assert result.delta == pytest.approx(0.6368, abs=1e-3)


def test_put_price_matches_known_reference_value():
    # Same inputs, put -> textbook value ~5.5735
    result = price_and_greeks(
        spot=100, strike=100, time_to_expiry_years=1,
        risk_free_rate=0.05, sigma=0.2, is_call=False,
    )
    assert result.price == pytest.approx(5.5735, abs=1e-3)
    assert result.delta == pytest.approx(-0.3632, abs=1e-3)


def test_put_call_parity_holds():
    call = price_and_greeks(100, 100, 1, 0.05, 0.2, is_call=True)
    put = price_and_greeks(100, 100, 1, 0.05, 0.2, is_call=False)
    # C - P = S - K*e^(-rT)
    lhs = call.price - put.price
    rhs = 100 - 100 * math.exp(-0.05 * 1)
    assert lhs == pytest.approx(rhs, abs=1e-6)


def test_deep_itm_call_delta_approaches_one():
    result = price_and_greeks(200, 100, 0.5, 0.05, 0.2, is_call=True)
    assert result.delta > 0.95


def test_expired_option_returns_intrinsic_value():
    result = price_and_greeks(110, 100, 0, 0.05, 0.2, is_call=True)
    assert result.price == pytest.approx(10.0)
    assert result.delta == 1.0

    result_otm = price_and_greeks(90, 100, 0, 0.05, 0.2, is_call=True)
    assert result_otm.price == 0.0
    assert result_otm.delta == 0.0


def test_zero_sigma_raises():
    with pytest.raises(ValueError):
        price_and_greeks(100, 100, 1, 0.05, 0.0, is_call=True)
