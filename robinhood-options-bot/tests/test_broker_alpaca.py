"""Tests AlpacaBrokerClient's own mapping logic against fabricated example
payloads (a FakeAlpacaTransport, no network). These prove our code maps a
given JSON shape correctly -- they do NOT prove that shape matches
Alpaca's actual live API, which hasn't been reachable to verify from this
environment. See the module docstring in broker/alpaca.py."""
from datetime import date, datetime

from robinhood_bot.broker.alpaca import (
    DATA_BASE_URL,
    TRADING_PAPER_BASE_URL,
    AlpacaAPIError,
    AlpacaBrokerClient,
    AlpacaTransport,
    _parse_occ_symbol,
)
from robinhood_bot.broker.base import OptionContract, OptionRight, OrderLeg, OrderSide


class FakeAlpacaTransport(AlpacaTransport):
    def __init__(self):
        self.calls = []
        self.get_responses = {}
        self.post_responses = {}
        self.delete_responses = {}

    def get(self, base_url, path, params=None):
        self.calls.append(("GET", base_url, path, params))
        return self.get_responses[path]

    def post(self, base_url, path, json_body):
        self.calls.append(("POST", base_url, path, json_body))
        response = self.post_responses[path]
        if isinstance(response, Exception):
            raise response
        return response

    def delete(self, base_url, path):
        self.calls.append(("DELETE", base_url, path))
        return self.delete_responses.get(path, {})


def make_contract(strike=190.0, right=OptionRight.PUT, expiration=date(2026, 1, 16)):
    return OptionContract(
        underlying="AAPL", expiration=expiration, strike=strike, right=right,
        bid=1.0, ask=1.2, last=1.1, implied_volatility=0.3,
        delta=-0.3, gamma=0.01, theta=-0.05, vega=0.1,
        as_of=datetime(2026, 1, 1),
    )


def test_parse_occ_symbol_round_trips_with_occ_symbol_property():
    contract = make_contract(strike=190.0, right=OptionRight.CALL, expiration=date(2026, 1, 16))
    underlying, expiration, right, strike = _parse_occ_symbol(contract.occ_symbol)
    assert underlying == "AAPL"
    assert expiration == date(2026, 1, 16)
    assert right == OptionRight.CALL
    assert strike == 190.0


def test_get_quote_maps_bid_ask():
    transport = FakeAlpacaTransport()
    transport.get_responses["/v2/stocks/AAPL/quotes/latest"] = {
        "quote": {"bp": 189.5, "ap": 189.7, "t": "2026-01-01T15:00:00Z"}
    }
    broker = AlpacaBrokerClient(transport)
    quote = broker.get_quote("AAPL")
    assert quote.bid == 189.5
    assert quote.ask == 189.7
    assert quote.symbol == "AAPL"
    assert transport.calls[0][1] == DATA_BASE_URL  # quotes come from the data API, not the trading API


def test_get_account_maps_fields_and_filters_to_option_positions():
    transport = FakeAlpacaTransport()
    transport.get_responses["/v2/account"] = {
        "equity": "101234.56", "cash": "50000.00", "buying_power": "60000.00",
    }
    transport.get_responses["/v2/positions"] = [
        {"symbol": "AAPL", "asset_class": "us_equity", "qty": "10", "side": "long", "avg_entry_price": "150"},
        {
            "symbol": "AAPL260116P00190000", "asset_class": "us_option", "qty": "2",
            "side": "short", "avg_entry_price": "1.10", "current_price": "1.05",
        },
    ]
    broker = AlpacaBrokerClient(transport)
    account = broker.get_account()
    assert account.equity == 101234.56
    assert account.cash == 50000.00
    assert len(account.positions) == 1  # equity position filtered out
    position = account.positions[0]
    assert position.quantity == -2  # short
    assert position.contract.strike == 190.0
    assert position.contract.right is OptionRight.PUT


def test_place_order_single_leg_uses_top_level_fields():
    transport = FakeAlpacaTransport()
    transport.post_responses["/v2/orders"] = {
        "id": "order-123", "status": "filled", "filled_avg_price": "1.15",
        "filled_at": "2026-01-01T15:05:00Z",
    }
    broker = AlpacaBrokerClient(transport)
    legs = [OrderLeg(make_contract(), OrderSide.SELL_TO_OPEN, quantity=2)]
    result = broker.place_order(legs, strategy_tag="cash_secured_put")

    method, base_url, path, body = transport.calls[0]
    assert method == "POST"
    assert base_url == TRADING_PAPER_BASE_URL  # paper=True is the default
    assert path == "/v2/orders"
    assert "legs" not in body
    assert body["symbol"] == legs[0].contract.occ_symbol
    assert body["side"] == "sell"
    assert body["position_intent"] == "sell_to_open"
    assert result.order.order_id == "order-123"
    assert result.fill_price == 1.15


def test_place_order_multi_leg_uses_mleg_order_class():
    transport = FakeAlpacaTransport()
    transport.post_responses["/v2/orders"] = {"id": "order-456", "status": "accepted"}
    broker = AlpacaBrokerClient(transport)
    legs = [
        OrderLeg(make_contract(strike=190.0), OrderSide.SELL_TO_OPEN, quantity=1),
        OrderLeg(make_contract(strike=185.0), OrderSide.BUY_TO_OPEN, quantity=1),
    ]
    result = broker.place_order(legs, strategy_tag="bull_put_spread")

    _, _, _, body = transport.calls[0]
    assert body["order_class"] == "mleg"
    assert len(body["legs"]) == 2
    assert body["legs"][0]["position_intent"] == "sell_to_open"
    assert body["legs"][1]["position_intent"] == "buy_to_open"
    assert result.order.order_id == "order-456"


def test_place_order_maps_api_error_to_rejected_result():
    transport = FakeAlpacaTransport()
    transport.post_responses["/v2/orders"] = AlpacaAPIError("Alpaca API error 422: insufficient buying power")
    broker = AlpacaBrokerClient(transport)
    legs = [OrderLeg(make_contract(), OrderSide.SELL_TO_OPEN, quantity=1)]
    result = broker.place_order(legs, strategy_tag="cash_secured_put")

    from robinhood_bot.broker.base import OrderStatus
    assert result.status is OrderStatus.REJECTED
    assert "insufficient buying power" in result.reason


def test_get_option_chain_maps_snapshots():
    transport = FakeAlpacaTransport()
    transport.get_responses["/v1beta1/options/snapshots"] = {
        "snapshots": {
            "AAPL260116P00190000": {
                "latestQuote": {"bp": 1.0, "ap": 1.2, "t": "2026-01-01T15:00:00Z"},
                "latestTrade": {"p": 1.1},
                "greeks": {"delta": -0.3, "gamma": 0.01, "theta": -0.05, "vega": 0.1},
                "impliedVolatility": 0.28,
            },
        },
    }
    broker = AlpacaBrokerClient(transport)
    chain = broker.get_option_chain("AAPL")
    assert len(chain) == 1
    contract = chain[0]
    assert contract.strike == 190.0
    assert contract.right is OptionRight.PUT
    assert contract.delta == -0.3
    assert contract.bid == 1.0
