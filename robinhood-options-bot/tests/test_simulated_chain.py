from datetime import datetime, timezone

import pytest

from robinhood_bot.broker.base import OptionRight
from robinhood_bot.options_pricing.simulated_chain import (
    build_simulated_chain,
    find_contract_by_delta,
    generate_expirations,
    generate_strike_grid,
)


def test_generate_strike_grid_is_centered_on_spot():
    strikes = generate_strike_grid(spot=100, num_strikes=10, pct_step=0.02)
    assert min(strikes) < 100 < max(strikes)


def test_generate_expirations_offsets_from_as_of():
    as_of = datetime(2026, 1, 1, tzinfo=timezone.utc).date()
    expirations = generate_expirations(as_of, dte_targets=[30, 45])
    assert (expirations[1] - expirations[0]).days == 15
    assert all(e > as_of for e in expirations)


def test_build_simulated_chain_produces_both_rights_and_reasonable_deltas():
    as_of = datetime(2026, 1, 1, tzinfo=timezone.utc)
    chain = build_simulated_chain(
        underlying="TEST", spot=100, as_of=as_of, iv=0.3,
    )
    calls = [c for c in chain if c.right is OptionRight.CALL]
    puts = [c for c in chain if c.right is OptionRight.PUT]
    assert calls and puts
    assert all(0 <= c.delta <= 1.0 for c in calls)
    assert all(-1.0 <= p.delta <= 0 for p in puts)
    assert all(c.ask >= c.bid for c in chain)


def test_find_contract_by_delta_returns_closest_match():
    as_of = datetime(2026, 1, 1, tzinfo=timezone.utc)
    chain = build_simulated_chain(underlying="TEST", spot=100, as_of=as_of, iv=0.3)
    contract = find_contract_by_delta(chain, target_delta=-0.30, right=OptionRight.PUT)
    assert contract.right is OptionRight.PUT
    assert contract.delta == pytest.approx(-0.30, abs=0.15)


def test_find_contract_by_delta_raises_when_no_candidates():
    with pytest.raises(ValueError):
        find_contract_by_delta([], target_delta=-0.3, right=OptionRight.PUT)
