"""Alpaca-backed BrokerClient -- a real, connectable adapter for use while
Robinhood's MCP connection is unavailable.

Implements the exact same `BrokerClient` interface `ShadowBrokerClient` and
`RobinhoodMCPBrokerClient` do. Switching brokers is a one-line config
change (`broker.adapter: alpaca` vs `mcp_placeholder`) -- nothing in
strategy/risk/backtest/execution code depends on which one is active.
Alpaca was picked because it has a free paper-trading tier and supports
options natively, not because it's uniquely "right" -- if Alpaca's API also
turns out unreachable from a given environment, the fix is that
environment's network policy, not another adapter rewrite.

*** STATUS as of 2026-07-11, after the network policy was widened and
verified against a real paper account:
- get_account(), get_quote(): VERIFIED against a live call. Field mapping
  correct as originally written.
- get_option_chain(): VERIFIED, but only after fixing two real bugs the
  live call caught -- the underlying symbol belongs in the URL path
  (`/v1beta1/options/snapshots/{underlying}`), not as an `underlying_symbols`
  query param on a path-less endpoint; and results are paginated
  (`next_page_token`), which the original version didn't follow. Both are
  fixed now (see the method for detail).
- place_order() / cancel_order(): STILL UNVERIFIED. Deliberately not
  exercised against the live account, since doing so places a real
  (paper-money, but real) order -- that needs an explicit, deliberate test
  the user has approved, not a side effect of debugging something else.
  Multi-leg (`order_class: "mleg"`) option orders remain the highest-risk
  unverified surface in this file. ***

HTTP is behind an injectable `AlpacaTransport` so this adapter is fully
unit-testable with zero network access -- see tests/test_broker_alpaca.py.
Those tests exercise this adapter's own mapping logic against fabricated
example payloads; they do NOT prove the payload shapes match Alpaca's
actual API.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime, timezone
from typing import Any

from robinhood_bot.broker.base import (
    Account,
    BrokerClient,
    OptionContract,
    OptionRight,
    Order,
    OrderLeg,
    OrderResult,
    OrderSide,
    OrderStatus,
    Position,
    Quote,
)

TRADING_PAPER_BASE_URL = "https://paper-api.alpaca.markets"
TRADING_LIVE_BASE_URL = "https://api.alpaca.markets"
DATA_BASE_URL = "https://data.alpaca.markets"

_ALPACA_STATUS_TO_ORDER_STATUS = {
    "filled": OrderStatus.FILLED,
    "partially_filled": OrderStatus.FILLED,
    "canceled": OrderStatus.CANCELLED,
    "expired": OrderStatus.REJECTED,
    "rejected": OrderStatus.REJECTED,
    "new": OrderStatus.PENDING,
    "accepted": OrderStatus.PENDING,
    "pending_new": OrderStatus.PENDING,
}

# Alpaca's `position_intent` field values match our OrderSide values
# exactly (both use buy_to_open/sell_to_open/buy_to_close/sell_to_close),
# which is a real but easy-to-mistrust coincidence worth calling out.
_SIDE_TO_ALPACA_ACTION = {
    OrderSide.BUY_TO_OPEN: "buy",
    OrderSide.SELL_TO_OPEN: "sell",
    OrderSide.BUY_TO_CLOSE: "buy",
    OrderSide.SELL_TO_CLOSE: "sell",
}


class AlpacaAPIError(Exception):
    """Raised on any non-2xx response, with the response body attached so
    callers see exactly what Alpaca said was wrong instead of a bare
    HTTP status."""


class AlpacaTransport(ABC):
    """Thin HTTP abstraction so AlpacaBrokerClient never touches `requests`
    directly -- inject a fake for tests, `RequestsAlpacaTransport` for
    production."""

    @abstractmethod
    def get(self, base_url: str, path: str, params: dict | None = None) -> Any:
        ...

    @abstractmethod
    def post(self, base_url: str, path: str, json_body: dict) -> Any:
        ...

    @abstractmethod
    def delete(self, base_url: str, path: str) -> Any:
        ...


class RequestsAlpacaTransport(AlpacaTransport):
    def __init__(self, api_key: str, api_secret: str):
        self._headers = {
            "APCA-API-KEY-ID": api_key,
            "APCA-API-SECRET-KEY": api_secret,
        }

    def get(self, base_url: str, path: str, params: dict | None = None) -> Any:
        return self._handle(lambda: self._requests().get(
            f"{base_url}{path}", headers=self._headers, params=params, timeout=15,
        ))

    def post(self, base_url: str, path: str, json_body: dict) -> Any:
        return self._handle(lambda: self._requests().post(
            f"{base_url}{path}", headers=self._headers, json=json_body, timeout=15,
        ))

    def delete(self, base_url: str, path: str) -> Any:
        return self._handle(lambda: self._requests().delete(
            f"{base_url}{path}", headers=self._headers, timeout=15,
        ))

    @staticmethod
    def _requests():
        import requests
        return requests

    @staticmethod
    def _handle(do_request):
        response = do_request()
        if not response.ok:
            raise AlpacaAPIError(f"Alpaca API error {response.status_code}: {response.text}")
        return response.json() if response.content else {}


class AlpacaBrokerClient(BrokerClient):
    def __init__(self, transport: AlpacaTransport, paper: bool = True):
        self._transport = transport
        self._trading_base = TRADING_PAPER_BASE_URL if paper else TRADING_LIVE_BASE_URL

    def get_quote(self, symbol: str) -> Quote:
        data = self._transport.get(DATA_BASE_URL, f"/v2/stocks/{symbol}/quotes/latest")
        quote = data["quote"]
        return Quote(
            symbol=symbol,
            bid=float(quote["bp"]),
            ask=float(quote["ap"]),
            last=(float(quote["bp"]) + float(quote["ap"])) / 2,
            as_of=_parse_timestamp(quote["t"]),
        )

    def get_option_chain(
        self, underlying: str, expiration: date | None = None
    ) -> list[OptionContract]:
        """Verified against a live paper account call on 2026-07-11. The
        underlying goes in the URL path (`/v1beta1/options/snapshots/{underlying}`)
        -- an earlier version of this method incorrectly passed it as an
        `underlying_symbols` query param on a path-less endpoint, which was
        never exercised against a live call until now. Results are also
        paginated (`next_page_token`); a full chain needs every page, which
        the earlier version silently didn't fetch."""
        params: dict[str, Any] = {"feed": "indicative"}
        if expiration is not None:
            params["expiration_date"] = expiration.isoformat()

        contracts: list[OptionContract] = []
        page_token: str | None = None
        while True:
            page_params = dict(params)
            if page_token is not None:
                page_params["page_token"] = page_token
            data = self._transport.get(
                DATA_BASE_URL, f"/v1beta1/options/snapshots/{underlying}", params=page_params,
            )
            for occ_symbol, snapshot in data.get("snapshots", {}).items():
                contracts.append(_snapshot_to_contract(occ_symbol, snapshot))
            page_token = data.get("next_page_token")
            if not page_token:
                break
        return contracts

    def get_account(self) -> Account:
        data = self._transport.get(self._trading_base, "/v2/account")
        positions_data = self._transport.get(self._trading_base, "/v2/positions")
        return Account(
            equity=float(data["equity"]),
            cash=float(data["cash"]),
            buying_power=float(data["buying_power"]),
            positions=[_position_from_alpaca(p) for p in positions_data if p.get("asset_class") == "us_option"],
        )

    def place_order(self, legs: list[OrderLeg], strategy_tag: str,
                     limit_price: float | None = None) -> OrderResult:
        """HIGH RISK / unverified -- see module docstring. Multi-leg
        (`order_class: "mleg"`) option orders are a newer Alpaca API
        surface; verify this payload shape against a live paper account
        before trusting it with real trades."""
        body: dict[str, Any] = {
            "time_in_force": "day",
            "type": "limit" if limit_price is not None else "market",
        }
        if limit_price is not None:
            body["limit_price"] = str(round(limit_price, 2))

        if len(legs) == 1:
            leg = legs[0]
            body.update({
                "symbol": leg.contract.occ_symbol,
                "qty": str(leg.quantity),
                "side": _SIDE_TO_ALPACA_ACTION[leg.side],
                "position_intent": leg.side.value,
            })
        else:
            body["order_class"] = "mleg"
            body["qty"] = str(legs[0].quantity)
            body["legs"] = [
                {
                    "symbol": leg.contract.occ_symbol,
                    "ratio_qty": str(leg.quantity),
                    "side": _SIDE_TO_ALPACA_ACTION[leg.side],
                    "position_intent": leg.side.value,
                }
                for leg in legs
            ]

        order = Order(
            order_id="",  # filled in below once Alpaca assigns one
            legs=legs,
            limit_price=limit_price,
            strategy_tag=strategy_tag,
            submitted_at=datetime.now(timezone.utc),
        )
        try:
            data = self._transport.post(self._trading_base, "/v2/orders", body)
        except AlpacaAPIError as exc:
            return OrderResult(order=order, status=OrderStatus.REJECTED, fill_price=None,
                                filled_at=None, reason=str(exc))

        order = Order(
            order_id=data["id"], legs=legs, limit_price=limit_price,
            strategy_tag=strategy_tag, submitted_at=order.submitted_at,
        )
        status = _ALPACA_STATUS_TO_ORDER_STATUS.get(data.get("status"), OrderStatus.PENDING)
        fill_price = float(data["filled_avg_price"]) if data.get("filled_avg_price") else None
        filled_at = _parse_timestamp(data["filled_at"]) if data.get("filled_at") else None
        return OrderResult(order=order, status=status, fill_price=fill_price, filled_at=filled_at)

    def cancel_order(self, order_id: str) -> OrderResult:
        self._transport.delete(self._trading_base, f"/v2/orders/{order_id}")
        data = self._transport.get(self._trading_base, f"/v2/orders/{order_id}")
        order = Order(order_id=order_id, legs=[], limit_price=None,
                       strategy_tag="", submitted_at=datetime.now(timezone.utc))
        status = _ALPACA_STATUS_TO_ORDER_STATUS.get(data.get("status"), OrderStatus.CANCELLED)
        return OrderResult(order=order, status=status, fill_price=None, filled_at=None)


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _snapshot_to_contract(occ_symbol: str, snapshot: dict) -> OptionContract:
    """HIGH RISK / unverified -- see module docstring."""
    underlying, expiration, right, strike = _parse_occ_symbol(occ_symbol)
    quote = snapshot.get("latestQuote", {})
    greeks = snapshot.get("greeks", {})
    trade = snapshot.get("latestTrade", {})
    return OptionContract(
        underlying=underlying,
        expiration=expiration,
        strike=strike,
        right=right,
        bid=float(quote.get("bp", 0.0)),
        ask=float(quote.get("ap", 0.0)),
        last=float(trade.get("p", 0.0)),
        implied_volatility=snapshot.get("impliedVolatility"),
        delta=greeks.get("delta"),
        gamma=greeks.get("gamma"),
        theta=greeks.get("theta"),
        vega=greeks.get("vega"),
        as_of=_parse_timestamp(quote["t"]) if quote.get("t") else datetime.now(timezone.utc),
    )


def _parse_occ_symbol(occ_symbol: str) -> tuple[str, date, OptionRight, float]:
    """Parses a standard OCC option symbol, e.g. AAPL240119C00190000."""
    i = 0
    while i < len(occ_symbol) and not occ_symbol[i].isdigit():
        i += 1
    underlying = occ_symbol[:i]
    date_str = occ_symbol[i:i + 6]
    right_char = occ_symbol[i + 6]
    strike_str = occ_symbol[i + 7:]
    expiration = date(2000 + int(date_str[0:2]), int(date_str[2:4]), int(date_str[4:6]))
    right = OptionRight.CALL if right_char == "C" else OptionRight.PUT
    strike = int(strike_str) / 1000
    return underlying, expiration, right, strike


def _position_from_alpaca(data: dict) -> Position:
    """HIGH RISK / unverified -- see module docstring. Alpaca represents
    quantity as always-positive with a separate `side` field ("long"/
    "short"); this maps that onto our signed-quantity convention."""
    underlying, expiration, right, strike = _parse_occ_symbol(data["symbol"])
    qty = float(data["qty"])
    signed_qty = int(qty) if data.get("side", "long") == "long" else -int(qty)
    contract = OptionContract(
        underlying=underlying,
        expiration=expiration,
        strike=strike,
        right=right,
        bid=0.0, ask=0.0, last=float(data.get("current_price", 0.0)),
        implied_volatility=None, delta=None, gamma=None, theta=None, vega=None,
        as_of=datetime.now(timezone.utc),
    )
    return Position(
        contract=contract,
        quantity=signed_qty,
        average_open_price=float(data["avg_entry_price"]),
        strategy_tag=data.get("strategy_tag", "unknown"),
    )


def build_alpaca_broker_client(api_key: str, api_secret: str, paper: bool = True) -> AlpacaBrokerClient:
    return AlpacaBrokerClient(RequestsAlpacaTransport(api_key, api_secret), paper=paper)
