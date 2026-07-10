"""Black-Scholes pricing and Greeks.

This is the pricing model used to *simulate* option prices from underlying
price history for backtesting (see simulated_chain.py) -- it is not used to
price real orders, which always come from the broker's live bid/ask.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from scipy.stats import norm


@dataclass(frozen=True)
class Greeks:
    price: float
    delta: float
    gamma: float
    theta: float  # per calendar day
    vega: float  # per 1 vol point (i.e. sigma + 0.01)
    rho: float  # per 1% rate change


def _d1_d2(spot: float, strike: float, time_to_expiry_years: float,
           risk_free_rate: float, sigma: float, dividend_yield: float) -> tuple[float, float]:
    sqrt_t = math.sqrt(time_to_expiry_years)
    d1 = (
        math.log(spot / strike)
        + (risk_free_rate - dividend_yield + 0.5 * sigma**2) * time_to_expiry_years
    ) / (sigma * sqrt_t)
    d2 = d1 - sigma * sqrt_t
    return d1, d2


def price_and_greeks(
    spot: float,
    strike: float,
    time_to_expiry_years: float,
    risk_free_rate: float,
    sigma: float,
    is_call: bool,
    dividend_yield: float = 0.0,
) -> Greeks:
    """Black-Scholes-Merton price and Greeks for a European option.

    American-style early exercise (which Robinhood equity options technically
    allow) is not modeled -- for the cash-secured-put/covered-call/credit-spread
    strategies this bot targets, European pricing is a standard and
    reasonable approximation.
    """
    if time_to_expiry_years <= 0:
        intrinsic = max(0.0, spot - strike) if is_call else max(0.0, strike - spot)
        delta = 0.0
        if intrinsic > 0:
            delta = 1.0 if is_call else -1.0
        return Greeks(price=intrinsic, delta=delta, gamma=0.0, theta=0.0, vega=0.0, rho=0.0)
    if sigma <= 0:
        raise ValueError("sigma (implied/realized volatility) must be positive")

    d1, d2 = _d1_d2(spot, strike, time_to_expiry_years, risk_free_rate, sigma, dividend_yield)
    sqrt_t = math.sqrt(time_to_expiry_years)
    disc_r = math.exp(-risk_free_rate * time_to_expiry_years)
    disc_q = math.exp(-dividend_yield * time_to_expiry_years)
    pdf_d1 = norm.pdf(d1)

    gamma = disc_q * pdf_d1 / (spot * sigma * sqrt_t)
    vega = spot * disc_q * pdf_d1 * sqrt_t / 100  # per 1 vol point

    if is_call:
        price = spot * disc_q * norm.cdf(d1) - strike * disc_r * norm.cdf(d2)
        delta = disc_q * norm.cdf(d1)
        theta_annual = (
            -spot * disc_q * pdf_d1 * sigma / (2 * sqrt_t)
            - risk_free_rate * strike * disc_r * norm.cdf(d2)
            + dividend_yield * spot * disc_q * norm.cdf(d1)
        )
        rho = strike * time_to_expiry_years * disc_r * norm.cdf(d2) / 100
    else:
        price = strike * disc_r * norm.cdf(-d2) - spot * disc_q * norm.cdf(-d1)
        delta = -disc_q * norm.cdf(-d1)
        theta_annual = (
            -spot * disc_q * pdf_d1 * sigma / (2 * sqrt_t)
            + risk_free_rate * strike * disc_r * norm.cdf(-d2)
            - dividend_yield * spot * disc_q * norm.cdf(-d1)
        )
        rho = -strike * time_to_expiry_years * disc_r * norm.cdf(-d2) / 100

    return Greeks(
        price=price,
        delta=delta,
        gamma=gamma,
        theta=theta_annual / 365,
        vega=vega,
        rho=rho,
    )
