"""Long-running paper-trading daemon: shadow mode against a live-updating
price feed, one trading day per cycle.

Deliberately shadow-only -- see `run_live_trading_day`'s docstring in
backtest/engine.py. This is Phase 7's "run shadow mode against live market
data for a defined trial period," not real-broker execution. Runs as a
long-lived process per the plan's execution-model decision (a daemon, not
a cron job re-invoked fresh each day), so broker and risk-engine state
persists naturally in memory across trading days without needing to
serialize/restore anything between runs.

Price fetching, sleeping, and the clock are all injected so this is fully
testable without real time or network access -- see
tests/test_paper_loop.py. `scripts/run_paper.py` wires up the real ones.
"""
from __future__ import annotations

import time
from datetime import date, datetime, timezone
from typing import Callable

import pandas as pd

from robinhood_bot.backtest.engine import BacktestConfig, run_live_trading_day
from robinhood_bot.broker.shadow import ShadowBrokerClient
from robinhood_bot.ledger.store import Ledger
from robinhood_bot.logging_setup import get_logger
from robinhood_bot.monitoring.alerts import Alerter, alert_on_risk_decision
from robinhood_bot.risk.engine import RiskEngine

log = get_logger(__name__)


def run_paper_trading_daemon(
    broker: ShadowBrokerClient,
    risk_engine: RiskEngine,
    ledger: Ledger,
    run_id: str,
    config: BacktestConfig,
    fetch_price_df: Callable[[], pd.DataFrame],
    *,
    alerter: Alerter | None = None,
    sleep_seconds: float = 24 * 60 * 60,
    sleep_fn: Callable[[float], None] = time.sleep,
    clock_fn: Callable[[], date] = lambda: datetime.now(timezone.utc).date(),
    max_cycles: int | None = None,
    on_cycle_complete: Callable[[date], None] | None = None,
    initial_last_run_date: date | None = None,
    wait_for_next_day: bool = True,
) -> int:
    """Runs one trading day per cycle, forever (or `max_cycles` times, for
    tests/bounded runs). Each cycle: refetch price history through today,
    run exactly one trading day, alert if that day produced a new
    halt-worthy risk decision, invoke `on_cycle_complete(today)` (e.g. to
    persist broker/risk-engine state and the processed date to disk -- see
    state_persistence.py), then sleep until the next cycle. Skips
    re-running if `clock_fn()` returns a date that's already been
    processed -- either seen earlier in this loop, or passed in via
    `initial_last_run_date` from a previous process's persisted state --
    protecting against waking early / restarting mid-day / a fresh
    process being re-invoked for a day it already ran.

    `wait_for_next_day` controls what happens on a skip: True (the
    long-lived-process default) sleeps and checks again, since the real
    clock will eventually advance. False returns immediately instead --
    for a process meant to run once and exit (e.g. one Routine firing per
    day), sleeping in-process until a new calendar date is pointless and,
    with the default 24h sleep_seconds, means it just hangs.

    Returns the number of cycles actually run.
    """
    last_run_date: date | None = initial_last_run_date
    cycles_run = 0
    while max_cycles is None or cycles_run < max_cycles:
        today = clock_fn()
        if today != last_run_date:
            price_df = fetch_price_df()
            _run_one_cycle(broker, risk_engine, ledger, run_id, config, price_df, alerter)
            last_run_date = today
            cycles_run += 1
            log.info("paper_loop.cycle_complete", run_id=run_id, as_of=str(today), cycle=cycles_run)
            if on_cycle_complete is not None:
                on_cycle_complete(today)
        elif not wait_for_next_day:
            log.info("paper_loop.already_up_to_date", run_id=run_id, as_of=str(today))
            break
        if max_cycles is not None and cycles_run >= max_cycles:
            break
        sleep_fn(sleep_seconds)
    return cycles_run


def _run_one_cycle(
    broker: ShadowBrokerClient,
    risk_engine: RiskEngine,
    ledger: Ledger,
    run_id: str,
    config: BacktestConfig,
    price_df: pd.DataFrame,
    alerter: Alerter | None,
) -> None:
    before = ledger.recent_risk_decisions(run_id=run_id, limit=1)
    last_id_before = before[0]["id"] if before else None

    run_live_trading_day(broker, risk_engine, ledger, run_id, config, price_df, mode="paper")

    if alerter is None:
        return
    after = ledger.recent_risk_decisions(run_id=run_id, limit=1)
    if after and after[0]["id"] != last_id_before:
        decision = after[0]
        alert_on_risk_decision(alerter, bool(decision["approved"]), decision["reason"])
