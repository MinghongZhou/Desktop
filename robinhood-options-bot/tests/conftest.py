import numpy as np
import pandas as pd
import pytest

from robinhood_bot.config import RiskSettings


def make_price_series(n: int = 320, seed: int = 42, drift: float = 0.0006,
                       vol: float = 0.012, start: float = 100.0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    returns = rng.normal(drift, vol, n)
    prices = start * np.cumprod(1 + returns)
    return pd.DataFrame({"Close": prices}, index=dates)


def make_risk_settings(**overrides) -> RiskSettings:
    defaults = dict(
        max_risk_per_trade_pct=2.5,
        max_concurrent_positions=6,
        max_capital_deployed_pct=60,
        daily_loss_limit_pct=4,
        drawdown_circuit_breaker_pct=12,
        max_portfolio_delta=300,
        max_portfolio_theta=-150,
        max_portfolio_vega=500,
    )
    defaults.update(overrides)
    return RiskSettings(**defaults)


@pytest.fixture
def price_df():
    return make_price_series()


@pytest.fixture
def risk_settings():
    return make_risk_settings()
