import pytest

from robinhood_bot.broker.alpaca import AlpacaBrokerClient
from robinhood_bot.broker.factory import build_broker_client
from robinhood_bot.broker.mcp_placeholder import RobinhoodMCPBrokerClient
from robinhood_bot.broker.shadow import ShadowBrokerClient
from robinhood_bot.config import BrokerSettings


def test_shadow_adapter_builds_shadow_broker_client():
    broker = build_broker_client(BrokerSettings(adapter="shadow"), starting_cash=50_000)
    assert isinstance(broker, ShadowBrokerClient)
    assert broker.get_account().equity == 50_000


def test_mcp_placeholder_adapter_builds_placeholder():
    broker = build_broker_client(BrokerSettings(adapter="mcp_placeholder"))
    assert isinstance(broker, RobinhoodMCPBrokerClient)
    with pytest.raises(NotImplementedError):
        broker.get_account()


def test_alpaca_adapter_requires_env_credentials(monkeypatch):
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_API_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="ALPACA_API_KEY"):
        build_broker_client(BrokerSettings(adapter="alpaca"))


def test_alpaca_adapter_builds_client_when_credentials_present(monkeypatch):
    monkeypatch.setenv("ALPACA_API_KEY", "test-key")
    monkeypatch.setenv("ALPACA_API_SECRET", "test-secret")
    broker = build_broker_client(BrokerSettings(adapter="alpaca"))
    assert isinstance(broker, AlpacaBrokerClient)
