"""Builds a synthetic option chain from underlying price + a volatility input.

This is the bridge between the price-history data layer and the
BrokerClient interface: it produces `OptionContract` objects (same type the
real Robinhood MCP adapter will eventually return) so backtest and strategy
code never need to know whether a chain came from Black-Scholes simulation
or a live broker.

*** Every price/greek here is MODELED, not a real historical quote. ***
See data/price_history.py and options_pricing/iv_rank.py for why free
historical options data isn't used instead.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from robinhood_bot.broker.base import OptionContract, OptionRight
from robinhood_bot.options_pricing.black_scholes import price_and_greeks

DEFAULT_BID_ASK_SPREAD_PCT = 0.03  # 3% of mid, floored below
MIN_SPREAD = 0.02


def generate_strike_grid(
    spot: float, num_strikes: int = 15, pct_step: float = 0.025
) -> list[float]:
    """Symmetric strike grid around spot, rounded to a sensible increment."""
    increment = 0.5 if spot < 25 else (1.0 if spot < 200 else 5.0)
    half = num_strikes // 2
    strikes = []
    for i in range(-half, half + 1):
        raw = spot * (1 + i * pct_step)
        strikes.append(round(raw / increment) * increment)
    return sorted(set(s for s in strikes if s > 0))


def generate_expirations(as_of: date, dte_targets: list[int] = (30, 45)) -> list[date]:
    return [as_of + timedelta(days=dte) for dte in dte_targets]


def build_simulated_chain(
    underlying: str,
    spot: float,
    as_of: datetime,
    iv: float,
    expirations: list[date] | None = None,
    strikes: list[float] | None = None,
    risk_free_rate: float = 0.05,
) -> list[OptionContract]:
    as_of_date = as_of.date()
    expirations = expirations or generate_expirations(as_of_date)
    strikes = strikes or generate_strike_grid(spot)

    contracts: list[OptionContract] = []
    for expiration in expirations:
        time_to_expiry_years = max((expiration - as_of_date).days, 1) / 365
        for strike in strikes:
            for right, is_call in ((OptionRight.CALL, True), (OptionRight.PUT, False)):
                greeks = price_and_greeks(
                    spot=spot,
                    strike=strike,
                    time_to_expiry_years=time_to_expiry_years,
                    risk_free_rate=risk_free_rate,
                    sigma=iv,
                    is_call=is_call,
                )
                mid = max(greeks.price, 0.01)
                half_spread = max(mid * DEFAULT_BID_ASK_SPREAD_PCT / 2, MIN_SPREAD / 2)
                contracts.append(
                    OptionContract(
                        underlying=underlying,
                        expiration=expiration,
                        strike=strike,
                        right=right,
                        bid=round(max(mid - half_spread, 0.0), 2),
                        ask=round(mid + half_spread, 2),
                        last=round(mid, 2),
                        implied_volatility=iv,
                        delta=greeks.delta,
                        gamma=greeks.gamma,
                        theta=greeks.theta,
                        vega=greeks.vega,
                        as_of=as_of,
                    )
                )
    return contracts


def find_contract_by_delta(
    chain: list[OptionContract],
    target_delta: float,
    right: OptionRight,
    expiration: date | None = None,
) -> OptionContract:
    """Closest contract to `target_delta` (signed: negative for puts)."""
    candidates = [c for c in chain if c.right is right]
    if expiration is not None:
        candidates = [c for c in candidates if c.expiration == expiration]
    if not candidates:
        raise ValueError(f"No contracts found for right={right}, expiration={expiration}")
    return min(candidates, key=lambda c: abs((c.delta or 0.0) - target_delta))
