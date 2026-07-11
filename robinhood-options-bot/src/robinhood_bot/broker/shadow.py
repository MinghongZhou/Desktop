"""Shadow/paper BrokerClient: real quotes in, simulated fills, zero real orders.

Quotes and option chains are injected via `update_quote`/`update_chain` (the
data layer feeds these from live or historical prices) rather than fetched
internally, so the same class works for both backtesting and live paper
trading -- only what feeds it differs.

Fills are simulated at the mid of bid/ask. This deliberately ignores
slippage and partial fills for now; Phase 5 (backtest engine) sensitivity
analysis is where fill-assumption error gets quantified, not here.
"""
from __future__ import annotations

import itertools
from datetime import date, datetime, timezone

from robinhood_bot.broker.base import (
    Account,
    BrokerClient,
    OptionContract,
    OrderLeg,
    OrderResult,
    OrderStatus,
    Position,
    Quote,
    signed_quantity,
)


class ShadowBrokerClient(BrokerClient):
    def __init__(self, starting_cash: float):
        self._cash = starting_cash
        self._quotes: dict[str, Quote] = {}
        self._chains: dict[str, list[OptionContract]] = {}
        self._positions: dict[str, Position] = {}  # keyed by occ_symbol
        self._order_ids = itertools.count(1)

    # -- data feed hooks, called by the data layer / backtest engine --

    def update_quote(self, quote: Quote) -> None:
        self._quotes[quote.symbol] = quote

    def update_chain(self, underlying: str, contracts: list[OptionContract]) -> None:
        self._chains[underlying] = contracts

    # -- BrokerClient interface --

    def get_quote(self, symbol: str) -> Quote:
        try:
            return self._quotes[symbol]
        except KeyError:
            raise KeyError(
                f"No quote loaded for {symbol!r}; call update_quote() first."
            ) from None

    def get_option_chain(
        self, underlying: str, expiration: date | None = None
    ) -> list[OptionContract]:
        contracts = self._chains.get(underlying, [])
        if expiration is not None:
            contracts = [c for c in contracts if c.expiration == expiration]
        return contracts

    def get_account(self) -> Account:
        market_value = 0.0
        for pos in self._positions.values():
            mid = (pos.contract.bid + pos.contract.ask) / 2
            market_value += mid * 100 * pos.quantity
        equity = self._cash + market_value
        return Account(
            equity=equity,
            cash=self._cash,
            buying_power=self._cash,  # no margin modeling yet
            positions=list(self._positions.values()),
        )

    def place_order(self, legs: list[OrderLeg], strategy_tag: str,
                     limit_price: float | None = None) -> OrderResult:
        from robinhood_bot.broker.base import Order  # local import avoids cycle at module load

        order = Order(
            order_id=str(next(self._order_ids)),
            legs=legs,
            limit_price=limit_price,
            strategy_tag=strategy_tag,
            submitted_at=datetime.now(timezone.utc),
        )

        for leg in legs:
            if leg.contract.bid <= 0 and leg.contract.ask <= 0:
                return OrderResult(
                    order=order,
                    status=OrderStatus.REJECTED,
                    fill_price=None,
                    filled_at=None,
                    reason=f"No valid market for {leg.contract.occ_symbol}",
                )

        total_fill = 0.0
        for leg in legs:
            mid = (leg.contract.bid + leg.contract.ask) / 2
            signed_qty = signed_quantity(leg.side, leg.quantity)
            is_buy = signed_qty > 0
            cash_delta = -mid * 100 * leg.quantity if is_buy else mid * 100 * leg.quantity
            self._cash += cash_delta
            total_fill += mid if is_buy else -mid

            key = leg.contract.occ_symbol
            existing = self._positions.get(key)
            new_qty = (existing.quantity if existing else 0) + signed_qty
            if new_qty == 0:
                self._positions.pop(key, None)
            else:
                self._positions[key] = Position(
                    contract=leg.contract,
                    quantity=new_qty,
                    average_open_price=mid,
                    strategy_tag=strategy_tag,
                )

        return OrderResult(
            order=order,
            status=OrderStatus.FILLED,
            fill_price=round(total_fill, 4),
            filled_at=datetime.now(timezone.utc),
        )

    def cancel_order(self, order_id: str) -> OrderResult:
        raise NotImplementedError(
            "ShadowBrokerClient fills immediately; there is never a pending "
            "order to cancel."
        )

    def apply_cash_adjustment(self, amount: float) -> None:
        """Backtest-only hook for modeling commissions/fees, which
        `place_order()` fills don't otherwise account for. Not part of
        `BrokerClient` -- a real broker reports commission in the fill
        itself, so this has no equivalent on the MCP adapter."""
        self._cash += amount
