"""Aggregates option Greeks across a portfolio, for the exposure caps in
config/settings.yaml (`max_portfolio_delta/theta/vega`).

Sign conventions (easy to get backwards, so spelled out explicitly):
- `OptionContract.delta/theta/vega` are per-share Greeks for one *long*
  contract, as computed by Black-Scholes -- e.g. a long call's delta is in
  [0, 1], a long put's is in [-1, 0].
- A position's contribution is `greek * position.quantity * 100`
  (100 shares/contract), where `quantity` is already signed (positive =
  long, negative = short) by the broker layer. Selling a put therefore
  contributes *positive* theta (premium decay working in the seller's
  favor) even though the put's own per-share theta is negative -- that's
  correct, not a bug.
- Caps: delta and vega are symmetric (`abs(total) <= cap`) since too much
  net exposure in either direction is risky. Theta is a floor
  (`total >= cap`, and the configured cap is negative) since collecting
  more theta is the point of a premium-selling bot -- only too much
  *negative* theta (too many long options bleeding time value) is capped.
"""
from __future__ import annotations

from dataclasses import dataclass

from robinhood_bot.broker.base import Account, OrderLeg, signed_quantity


@dataclass(frozen=True)
class PortfolioGreeks:
    delta: float = 0.0
    theta: float = 0.0
    vega: float = 0.0


def portfolio_greeks(account: Account) -> PortfolioGreeks:
    delta = theta = vega = 0.0
    for pos in account.positions:
        c = pos.contract
        delta += (c.delta or 0.0) * pos.quantity * 100
        theta += (c.theta or 0.0) * pos.quantity * 100
        vega += (c.vega or 0.0) * pos.quantity * 100
    return PortfolioGreeks(delta, theta, vega)


def incremental_greeks(legs: list[OrderLeg]) -> PortfolioGreeks:
    """The Greeks change from filling `legs` at 1x quantity; scale() it by
    the actual contract count before combining with portfolio_greeks()."""
    delta = theta = vega = 0.0
    for leg in legs:
        c = leg.contract
        qty = signed_quantity(leg.side, leg.quantity)
        delta += (c.delta or 0.0) * qty * 100
        theta += (c.theta or 0.0) * qty * 100
        vega += (c.vega or 0.0) * qty * 100
    return PortfolioGreeks(delta, theta, vega)


def scale(greeks: PortfolioGreeks, factor: float) -> PortfolioGreeks:
    return PortfolioGreeks(greeks.delta * factor, greeks.theta * factor, greeks.vega * factor)


def add(a: PortfolioGreeks, b: PortfolioGreeks) -> PortfolioGreeks:
    return PortfolioGreeks(a.delta + b.delta, a.theta + b.theta, a.vega + b.vega)
