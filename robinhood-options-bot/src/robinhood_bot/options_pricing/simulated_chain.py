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

from datetime import date, datetime, time, timedelta

from robinhood_bot.broker.base import OptionContract, OptionRight
from robinhood_bot.options_pricing.black_scholes import price_and_greeks

# Approximate market close for same-day (0DTE) time-to-expiry, in UTC.
# Doesn't account for DST (ET is UTC-4 in summer, UTC-5 in winter) -- an
# acceptable +/-1h imprecision for a paper-trading strategy, consistent
# with the rest of this project's approach to calendar precision.
MARKET_CLOSE_UTC = time(20, 0)

DEFAULT_BID_ASK_SPREAD_PCT = 0.03  # 3% of mid, floored below
MIN_SPREAD = 0.02


def generate_strike_grid(
    spot: float, num_strikes: int = 41, pct_step: float | None = None, increment: float | None = None,
) -> list[float]:
    """Symmetric strike grid around spot, rounded to a sensible increment.

    `pct_step` defaults to one rounding increment's worth of spot (e.g.
    ~0.9% at SPY's ~$570), not a fixed percentage. A fixed 2.5% step used
    to combine badly with the increment rounding at higher prices: at
    SPY's level, a 2.5%-of-spot step is ~$14, which rounds to *three*
    $5 increments apart, not one -- so "adjacent" strikes in the grid were
    actually 15 dollars apart, silently turning every "5-wide spread"
    request into an unintended 15-wide one. A real backtest against real
    SPY prices caught this: it took 3x the intended max loss on several
    trades before `strategy/definitions.py` grew a width-tolerance check
    that (correctly) started refusing those trades -- which then also
    surfaced this as the actual root cause, since a fine grid never needed
    to be refused at all.

    `num_strikes` went from 15 to 41 alongside that fix: a fine per-increment
    step covers much less total dollar range for the same strike count (the
    old 15-strike/2.5%-step grid spanned +/-17.5% of spot; a 15-strike grid
    at one-increment steps only spans roughly +/-7%, too narrow to fit a
    reasonably-OTM short strike *plus* a protective leg beyond it). 41
    strikes at one-increment steps restores comparable total range while
    keeping the spacing fix.

    `increment` overrides the auto-derived rounding increment -- needed
    for tickers whose real strike spacing doesn't match the size-based
    default below (e.g. SPY's 0DTE strikes trade in $1 increments despite
    its ~$570 price, unlike most stocks at that price level; the
    intraday/0DTE engine passes this explicitly rather than accepting a
    $5 grid it can never build a narrow same-day spread on)."""
    if increment is None:
        increment = 0.5 if spot < 25 else (1.0 if spot < 200 else 5.0)
    if pct_step is None:
        pct_step = increment / spot
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
        if expiration == as_of_date:
            # Same-day (0DTE) expiration: the "at least 1 day" floor below
            # would price every intraday checkpoint identically regardless
            # of how many hours actually remain until close -- wrong for a
            # strategy that enters multiple times across the day. Use
            # actual fractional time remaining instead.
            close_dt = datetime.combine(expiration, MARKET_CLOSE_UTC, tzinfo=as_of.tzinfo)
            seconds_remaining = max((close_dt - as_of).total_seconds(), 60.0)
            time_to_expiry_years = seconds_remaining / (365 * 24 * 3600)
        else:
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
