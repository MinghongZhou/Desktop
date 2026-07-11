"""Bounds the worst-case dollar loss of a proposed trade and sizes it
against a risk budget.

This is where the "no naked/undefined-risk options" safety rule is actually
enforced in code, not just promised in a docstring: a lone short call with
no long leg raises `UndefinedRiskError` and the risk engine refuses it.
"""
from __future__ import annotations

from robinhood_bot.broker.base import OptionRight, OrderLeg, OrderSide


class UndefinedRiskError(Exception):
    """Raised when a proposed trade's max loss can't be bounded from its
    legs alone -- e.g. a naked short call with no covering shares tracked."""


def net_credit_per_unit(legs: list[OrderLeg]) -> float:
    """Positive = net credit received, negative = net debit paid, in
    dollars per 1x the strategy's base quantity (i.e. per contract for a
    single-leg trade, per spread for a multi-leg one)."""
    total_per_share = 0.0
    for leg in legs:
        mid = (leg.contract.bid + leg.contract.ask) / 2
        if leg.side in (OrderSide.SELL_TO_OPEN, OrderSide.SELL_TO_CLOSE):
            total_per_share += mid
        else:
            total_per_share -= mid
    return total_per_share * 100


def estimate_max_loss_per_unit(legs: list[OrderLeg]) -> float:
    """Worst-case dollar loss per 1x the strategy's base quantity.

    Only handles the strategy shapes this bot is allowed to trade:
    - a single short put (cash-secured put): bounded because the
      underlying can't go below zero.
    - a two-leg vertical spread (bull put or bear call): bounded by the
      strike width minus credit received.
    - a four-leg iron condor (two verticals sharing an expiration):
      bounded by the wider of the two verticals' widths minus total
      credit, since only one side can be in the money at expiration.

    A single short call (or anything else this doesn't recognize) raises
    `UndefinedRiskError` rather than guessing.
    """
    credit = net_credit_per_unit(legs)
    puts = [l for l in legs if l.contract.right is OptionRight.PUT]
    calls = [l for l in legs if l.contract.right is OptionRight.CALL]

    if len(legs) == 1:
        leg = legs[0]
        if leg.side is not OrderSide.SELL_TO_OPEN:
            raise UndefinedRiskError(
                "Single-leg long options aren't sized by this engine (their "
                "max loss is just the premium paid, but they're not part of "
                "the target strategy set)."
            )
        if leg.contract.right is OptionRight.PUT:
            return max(leg.contract.strike * 100 - credit, 0.0)
        raise UndefinedRiskError(
            "A lone short call has unbounded loss unless covered by shares, "
            "which this risk engine does not track. Refusing to size it."
        )

    if len(legs) == 2 and (len(puts) == 2 or len(calls) == 2):
        width = abs(legs[0].contract.strike - legs[1].contract.strike) * 100
        return max(width - credit, 0.0)

    if len(legs) == 4 and len(puts) == 2 and len(calls) == 2:
        put_width = abs(puts[0].contract.strike - puts[1].contract.strike) * 100
        call_width = abs(calls[0].contract.strike - calls[1].contract.strike) * 100
        return max(max(put_width, call_width) - credit, 0.0)

    raise UndefinedRiskError(
        f"Don't know how to bound max loss for a {len(legs)}-leg combination "
        f"of {len(puts)} put(s) / {len(calls)} call(s)."
    )


def contracts_for_risk_budget(max_loss_per_unit: float, risk_budget_dollars: float) -> int:
    """Floor division; 0 if even one unit exceeds the budget."""
    if max_loss_per_unit <= 0 or risk_budget_dollars <= 0:
        return 0
    return int(risk_budget_dollars // max_loss_per_unit)
