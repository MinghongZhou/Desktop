"""Builds the configured BrokerClient from settings.

This is where the "swapping brokers is a one-line config change" promise
actually gets exercised: everything else (strategy, risk, backtest,
execution) only ever sees the `BrokerClient` interface this returns.
"""
from __future__ import annotations

import os

from robinhood_bot.broker.base import BrokerClient
from robinhood_bot.config import BrokerSettings


def build_broker_client(settings: BrokerSettings, starting_cash: float = 100_000) -> BrokerClient:
    if settings.adapter == "shadow":
        from robinhood_bot.broker.shadow import ShadowBrokerClient
        return ShadowBrokerClient(starting_cash=starting_cash)

    if settings.adapter == "alpaca":
        from robinhood_bot.broker.alpaca import build_alpaca_broker_client
        api_key = os.environ.get("ALPACA_API_KEY")
        api_secret = os.environ.get("ALPACA_API_SECRET")
        if not api_key or not api_secret:
            raise RuntimeError(
                "broker.adapter is 'alpaca' but ALPACA_API_KEY / ALPACA_API_SECRET "
                "are not set in the environment. Credentials never go in "
                "config/settings.yaml."
            )
        return build_alpaca_broker_client(api_key, api_secret, paper=settings.alpaca_paper)

    if settings.adapter == "mcp_placeholder":
        from robinhood_bot.broker.mcp_placeholder import RobinhoodMCPBrokerClient
        return RobinhoodMCPBrokerClient()

    raise ValueError(f"Unknown broker adapter: {settings.adapter!r}")
