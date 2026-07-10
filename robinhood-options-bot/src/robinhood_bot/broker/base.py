"""Broker-agnostic interface every execution/backtest/paper path is written against.

Strategy, risk, backtest, and execution code must only ever depend on
`BrokerClient` and the data models below -- never on a concrete adapter.
That's what lets the real Robinhood MCP adapter get dropped in later
(see mcp_placeholder.py) without touching anything else.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum


class OptionRight(str, Enum):
    CALL = "call"
    PUT = "put"


class OrderSide(str, Enum):
    BUY_TO_OPEN = "buy_to_open"
    SELL_TO_OPEN = "sell_to_open"
    BUY_TO_CLOSE = "buy_to_close"
    SELL_TO_CLOSE = "sell_to_close"


class OrderStatus(str, Enum):
    PENDING = "pending"
    FILLED = "filled"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class Quote:
    symbol: str
    bid: float
    ask: float
    last: float
    as_of: datetime


@dataclass(frozen=True)
class OptionContract:
    underlying: str
    expiration: date
    strike: float
    right: OptionRight
    bid: float
    ask: float
    last: float
    implied_volatility: float | None
    delta: float | None
    gamma: float | None
    theta: float | None
    vega: float | None
    as_of: datetime

    @property
    def occ_symbol(self) -> str:
        """OCC-style option symbol, e.g. AAPL240119C00190000."""
        right_code = "C" if self.right is OptionRight.CALL else "P"
        strike_int = round(self.strike * 1000)
        return (
            f"{self.underlying}"
            f"{self.expiration.strftime('%y%m%d')}"
            f"{right_code}{strike_int:08d}"
        )


@dataclass(frozen=True)
class OrderLeg:
    contract: OptionContract
    side: OrderSide
    quantity: int  # contracts, always positive


@dataclass(frozen=True)
class Order:
    order_id: str
    legs: list[OrderLeg]
    limit_price: float | None  # net debit (+) or credit (-) per spread, if applicable
    strategy_tag: str  # e.g. "bull_put_spread", "covered_call"
    submitted_at: datetime


@dataclass(frozen=True)
class OrderResult:
    order: Order
    status: OrderStatus
    fill_price: float | None
    filled_at: datetime | None
    reason: str | None = None  # populated on rejection/cancellation


@dataclass(frozen=True)
class Position:
    contract: OptionContract
    quantity: int  # positive = long, negative = short
    average_open_price: float
    strategy_tag: str


@dataclass(frozen=True)
class Account:
    equity: float
    cash: float
    buying_power: float
    positions: list[Position] = field(default_factory=list)


class BrokerClient(ABC):
    """Everything strategy/risk/backtest/execution code needs from a broker."""

    @abstractmethod
    def get_quote(self, symbol: str) -> Quote:
        ...

    @abstractmethod
    def get_option_chain(
        self, underlying: str, expiration: date | None = None
    ) -> list[OptionContract]:
        ...

    @abstractmethod
    def get_account(self) -> Account:
        ...

    @abstractmethod
    def place_order(self, legs: list[OrderLeg], strategy_tag: str,
                     limit_price: float | None = None) -> OrderResult:
        ...

    @abstractmethod
    def cancel_order(self, order_id: str) -> OrderResult:
        ...
