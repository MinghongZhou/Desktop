"""Placeholder adapter for the Robinhood MCP connection.

STATUS: not wired up yet. Every method raises NotImplementedError until the
Robinhood MCP server is connected and its tool interface is known.

When you're ready to wire it in:
  1. Replace the `mcp_call` placeholder below with whatever client/transport
     is used to invoke the Robinhood MCP server's tools (an MCP session
     object, an HTTP client pointed at the server, etc).
  2. Implement each method by calling the corresponding MCP tool and mapping
     its response onto the dataclasses in `broker/base.py`
     (Quote, OptionContract, Account, Position, OrderResult).
  3. Flip `config/settings.yaml` -> `broker.adapter: mcp_placeholder` once
     this class is real, but leave `mode: shadow` until Phase 7 (paper
     trading trial) passes -- the live-trading gate in config.py refuses to
     run this adapter in `mode: live` until it's implemented, since a
     NotImplementedError mid-order is exactly what the safety gates exist
     to prevent finding out about the hard way.
"""
from __future__ import annotations

from datetime import date

from robinhood_bot.broker.base import (
    Account,
    BrokerClient,
    OptionContract,
    Order,
    OrderLeg,
    OrderResult,
    Quote,
)

_NOT_WIRED_UP = (
    "RobinhoodMCPBrokerClient is a placeholder -- the Robinhood MCP connection "
    "has not been wired in yet. See the module docstring in "
    "broker/mcp_placeholder.py for what to implement."
)


class RobinhoodMCPBrokerClient(BrokerClient):
    def __init__(self, mcp_call=None):
        """`mcp_call` will be whatever handle is used to invoke Robinhood MCP tools."""
        self._mcp_call = mcp_call

    def get_quote(self, symbol: str) -> Quote:
        raise NotImplementedError(_NOT_WIRED_UP)

    def get_option_chain(
        self, underlying: str, expiration: date | None = None
    ) -> list[OptionContract]:
        raise NotImplementedError(_NOT_WIRED_UP)

    def get_account(self) -> Account:
        raise NotImplementedError(_NOT_WIRED_UP)

    def place_order(self, legs: list[OrderLeg], strategy_tag: str,
                     limit_price: float | None = None) -> OrderResult:
        raise NotImplementedError(_NOT_WIRED_UP)

    def cancel_order(self, order_id: str) -> OrderResult:
        raise NotImplementedError(_NOT_WIRED_UP)
