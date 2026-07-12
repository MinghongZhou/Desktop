"""Defined-risk options strategy builders.

Every function here returns a list[OrderLeg] ready to hand to
`BrokerClient.place_order`. Deliberately excludes naked/undefined-risk
structures (e.g. a short call with no long call above it) -- see the plan's
hard-coded safety rules. Strike selection is delta-targeted, the standard
way retail options strategies pick strikes without needing a view on
absolute price.
"""
from __future__ import annotations

from robinhood_bot.broker.base import OptionContract, OptionRight, OrderLeg, OrderSide
from robinhood_bot.options_pricing.simulated_chain import find_contract_by_delta

QUANTITY = 1  # contracts per leg; position sizing (Phase 3) scales this up


def cash_secured_put(chain: list[OptionContract], target_delta: float = -0.30) -> list[OrderLeg]:
    """Sell one put; assumes cash is reserved to buy 100 shares if assigned."""
    short_put = find_contract_by_delta(chain, target_delta, OptionRight.PUT)
    return [OrderLeg(short_put, OrderSide.SELL_TO_OPEN, QUANTITY)]


def covered_call(chain: list[OptionContract], target_delta: float = 0.30) -> list[OrderLeg]:
    """Sell one call. Assumes 100 shares of the underlying are already held --
    this builder only constructs the option leg, not the share purchase."""
    short_call = find_contract_by_delta(chain, target_delta, OptionRight.CALL)
    return [OrderLeg(short_call, OrderSide.SELL_TO_OPEN, QUANTITY)]


class NoValidStrikeError(ValueError):
    """Raised when no chain contract can complete a spread's protective leg
    -- e.g. sparse/wide real strike spacing (caught via a live Alpaca test
    against a thinly-quoted LEAPS expiration, where "closest available
    strike to target" degenerated to the short leg's own strike, producing
    an invalid duplicate-leg order Alpaca correctly rejected)."""


def bull_put_spread(
    chain: list[OptionContract], short_delta: float = -0.30, width: float = 5.0,
    max_width_multiple: float = 1.5,
) -> list[OrderLeg]:
    """Sell a put at `short_delta`, buy a further-OTM put `width` below it.
    Defined max loss = width - net credit received.

    Rejects the trade (raises NoValidStrikeError) if the closest available
    protective strike would make the realized width more than
    `max_width_multiple` times the requested `width`. Real strike grids
    are often sparser than the target -- a live backtest against real SPY
    strikes saw "5-wide" requests silently become 15-wide (3x) spreads,
    which is a materially different, riskier trade than the one asked
    for, not just an approximation of it. Better to skip the trade than
    silently take on 2-3x the intended max loss."""
    short_put = find_contract_by_delta(chain, short_delta, OptionRight.PUT)
    long_strike_target = short_put.strike - width
    long_candidates = [
        c for c in chain
        if c.right is OptionRight.PUT
        and c.expiration == short_put.expiration
        # Must be strictly below the short strike -- that's what makes it
        # protective. Without this, "closest available strike to target"
        # can pick the short leg's own strike (or even a higher one) when
        # the real strike grid is sparse, producing an invalid spread.
        and c.strike < short_put.strike
    ]
    if not long_candidates:
        raise NoValidStrikeError(
            f"No put strike below {short_put.strike} available for expiration "
            f"{short_put.expiration} to build a bull put spread with width {width}."
        )
    long_put = min(long_candidates, key=lambda c: abs(c.strike - long_strike_target))
    realized_width = short_put.strike - long_put.strike
    if realized_width > width * max_width_multiple:
        raise NoValidStrikeError(
            f"Closest available protective put strike ({long_put.strike}) is "
            f"{realized_width} points from the short strike ({short_put.strike}), "
            f"more than {max_width_multiple}x the requested width ({width})."
        )
    return [
        OrderLeg(short_put, OrderSide.SELL_TO_OPEN, QUANTITY),
        OrderLeg(long_put, OrderSide.BUY_TO_OPEN, QUANTITY),
    ]


def bear_call_spread(
    chain: list[OptionContract], short_delta: float = 0.30, width: float = 5.0,
    max_width_multiple: float = 1.5,
) -> list[OrderLeg]:
    """Sell a call at `short_delta`, buy a further-OTM call `width` above it.
    Defined max loss = width - net credit received. See bull_put_spread's
    docstring for why `max_width_multiple` exists."""
    short_call = find_contract_by_delta(chain, short_delta, OptionRight.CALL)
    long_strike_target = short_call.strike + width
    long_candidates = [
        c for c in chain
        if c.right is OptionRight.CALL
        and c.expiration == short_call.expiration
        # Must be strictly above the short strike -- see bull_put_spread's
        # comment on why "closest available" alone isn't sufficient.
        and c.strike > short_call.strike
    ]
    if not long_candidates:
        raise NoValidStrikeError(
            f"No call strike above {short_call.strike} available for expiration "
            f"{short_call.expiration} to build a bear call spread with width {width}."
        )
    long_call = min(long_candidates, key=lambda c: abs(c.strike - long_strike_target))
    realized_width = long_call.strike - short_call.strike
    if realized_width > width * max_width_multiple:
        raise NoValidStrikeError(
            f"Closest available protective call strike ({long_call.strike}) is "
            f"{realized_width} points from the short strike ({short_call.strike}), "
            f"more than {max_width_multiple}x the requested width ({width})."
        )
    return [
        OrderLeg(short_call, OrderSide.SELL_TO_OPEN, QUANTITY),
        OrderLeg(long_call, OrderSide.BUY_TO_OPEN, QUANTITY),
    ]


def iron_condor(
    chain: list[OptionContract],
    put_delta: float = -0.20,
    call_delta: float = 0.20,
    width: float = 5.0,
) -> list[OrderLeg]:
    """Bull put spread + bear call spread on the same expiration; defined
    max loss on both sides."""
    return bull_put_spread(chain, put_delta, width) + bear_call_spread(chain, call_delta, width)
