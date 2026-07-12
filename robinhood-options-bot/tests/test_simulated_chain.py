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


def test_zero_dte_chain_prices_later_in_day_cheaper_than_morning():
    """Regression guard: the general "at least 1 day" time-to-expiry floor
    would price a 0DTE chain identically regardless of what time of day
    it's built at -- wrong for a strategy that enters multiple times
    across the same expiration day. A same-day expiration must use actual
    hours remaining, so an afternoon build should show less extrinsic
    value (all else equal) than a morning build."""
    expiration = datetime(2026, 1, 5, tzinfo=timezone.utc).date()
    morning = datetime(2026, 1, 5, 14, 30, tzinfo=timezone.utc)   # ~9:30am ET
    afternoon = datetime(2026, 1, 5, 19, 45, tzinfo=timezone.utc)  # ~2:45pm ET, close to the 20:00 UTC close

    morning_chain = build_simulated_chain(
        underlying="TEST", spot=100, as_of=morning, iv=0.3, expirations=[expiration],
    )
    afternoon_chain = build_simulated_chain(
        underlying="TEST", spot=100, as_of=afternoon, iv=0.3, expirations=[expiration],
    )

    morning_call_atm = find_contract_by_delta(morning_chain, target_delta=0.50, right=OptionRight.CALL)
    afternoon_call_atm = find_contract_by_delta(afternoon_chain, target_delta=0.50, right=OptionRight.CALL)
    assert afternoon_call_atm.last < morning_call_atm.last


def test_zero_dte_chain_does_not_crash_seconds_before_close():
    as_of = datetime(2026, 1, 5, 19, 59, 59, tzinfo=timezone.utc)
    expiration = as_of.date()
    chain = build_simulated_chain(underlying="TEST", spot=100, as_of=as_of, iv=0.3, expirations=[expiration])
    assert all(c.last >= 0 for c in chain)
