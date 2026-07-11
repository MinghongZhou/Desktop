from datetime import datetime, timezone

import pytest

from robinhood_bot.options_pricing.simulated_chain import build_simulated_chain
from robinhood_bot.risk.position_sizing import (
    UndefinedRiskError,
    contracts_for_risk_budget,
    estimate_max_loss_per_unit,
    net_credit_per_unit,
)
from robinhood_bot.strategy.definitions import (
    bear_call_spread,
    bull_put_spread,
    cash_secured_put,
    covered_call,
    iron_condor,
)


@pytest.fixture
def chain():
    as_of = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return build_simulated_chain(underlying="TEST", spot=100, as_of=as_of, iv=0.3)


def test_vertical_spread_max_loss_is_width_minus_credit(chain):
    legs = bull_put_spread(chain, short_delta=-0.30, width=5.0)
    credit = net_credit_per_unit(legs)
    max_loss = estimate_max_loss_per_unit(legs)
    width = abs(legs[0].contract.strike - legs[1].contract.strike) * 100
    assert max_loss == pytest.approx(width - credit)
    assert 0 < max_loss < width  # credit received must be positive and less than width


def test_bear_call_spread_max_loss_is_bounded(chain):
    legs = bear_call_spread(chain, short_delta=0.30, width=5.0)
    max_loss = estimate_max_loss_per_unit(legs)
    assert max_loss > 0
    assert max_loss < 500  # width(5) * 100 upper bound


def test_iron_condor_max_loss_is_bounded_by_wider_side(chain):
    legs = iron_condor(chain)
    max_loss = estimate_max_loss_per_unit(legs)
    assert 0 < max_loss < 500


def test_cash_secured_put_max_loss_is_strike_based(chain):
    legs = cash_secured_put(chain, target_delta=-0.30)
    max_loss = estimate_max_loss_per_unit(legs)
    strike = legs[0].contract.strike
    credit = net_credit_per_unit(legs)
    assert max_loss == pytest.approx(strike * 100 - credit)


def test_naked_short_call_is_refused_as_undefined_risk(chain):
    legs = covered_call(chain, target_delta=0.30)
    with pytest.raises(UndefinedRiskError, match="unbounded"):
        estimate_max_loss_per_unit(legs)


def test_unrecognized_leg_combination_raises():
    with pytest.raises(UndefinedRiskError):
        estimate_max_loss_per_unit([])


def test_contracts_for_risk_budget_floors_down():
    assert contracts_for_risk_budget(max_loss_per_unit=300, risk_budget_dollars=1000) == 3
    assert contracts_for_risk_budget(max_loss_per_unit=300, risk_budget_dollars=299) == 0
    assert contracts_for_risk_budget(max_loss_per_unit=0, risk_budget_dollars=1000) == 0
