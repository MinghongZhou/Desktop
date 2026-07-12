#!/usr/bin/env python3
"""CLI entrypoint: long-running paper-trading daemon (Phase 7).

    python scripts/run_paper.py --ticker SPY

Runs shadow mode (simulated option pricing) against a live-refreshing
underlying price feed, one trading day per cycle. Can run as a long-lived
process (per the plan's original "standalone Python service" execution
model) or be re-invoked fresh once per day (e.g. by a Claude Code
Routine) -- broker/risk-engine state and the last processed trading day
are persisted to --state-file after every cycle and reloaded on startup,
so a fresh invocation resumes the same paper account instead of resetting
to a new one, and safely no-ops if re-run for a day it already processed.

Requires network access to the price data vendor (Alpaca by default, see
config/settings.yaml -> data.price_history_source) and, when that source
is "alpaca", ALPACA_API_KEY / ALPACA_API_SECRET env vars.
"""
from __future__ import annotations

import argparse
import uuid
from pathlib import Path

from robinhood_bot.backtest.engine import BacktestConfig
from robinhood_bot.broker.shadow import ShadowBrokerClient
from robinhood_bot.config import REPO_ROOT, load_settings
from robinhood_bot.data.factory import build_price_history_fetcher
from robinhood_bot.execution.paper_loop import run_paper_trading_daemon
from robinhood_bot.execution.state_persistence import load_state, save_state
from robinhood_bot.ledger.store import Ledger
from robinhood_bot.logging_setup import configure_logging, get_logger
from robinhood_bot.monitoring.alerts import LoggingAlerter, WebhookAlerter
from robinhood_bot.risk.engine import RiskEngine

log = get_logger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--lookback-days", type=int, default=None,
                         help="Defaults to config/settings.yaml -> data.default_lookback_days")
    parser.add_argument("--starting-cash", type=float, default=100_000)
    parser.add_argument("--iv-rank-threshold", type=float, default=50.0)
    parser.add_argument("--dte-target", type=int, default=30)
    parser.add_argument("--spread-width", type=float, default=5.0)
    parser.add_argument("--profit-target-pct", type=float, default=0.50)
    parser.add_argument("--stop-loss-multiple", type=float, default=2.0)
    parser.add_argument("--disable-early-exit", action="store_true")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--max-cycles", type=int, default=None,
                         help="Stop after this many trading days instead of running forever (useful for a bounded trial/demo run)")
    parser.add_argument("--state-file", default=None,
                         help="Path to persist broker/risk-engine state across process restarts "
                              "(e.g. successive Routine firings). Defaults to "
                              "data/paper_state/{run_id}.json. State is saved after every cycle "
                              "and loaded on startup if it already exists, so re-invoking this "
                              "script with the same --run-id/--state-file resumes rather than "
                              "resetting to a fresh account.")
    args = parser.parse_args()

    settings = load_settings()
    configure_logging(settings.logging)

    lookback_days = args.lookback_days or settings.data.default_lookback_days
    run_id = args.run_id or f"paper_{args.ticker}_{uuid.uuid4().hex[:8]}"

    config = BacktestConfig(
        ticker=args.ticker,
        starting_cash=args.starting_cash,
        iv_rank_threshold=args.iv_rank_threshold,
        dte_target=args.dte_target,
        spread_width=args.spread_width,
        profit_target_pct=args.profit_target_pct,
        stop_loss_multiple=args.stop_loss_multiple,
        enable_early_exit=not args.disable_early_exit,
    )

    fetch = build_price_history_fetcher(settings.data, settings.resolved_price_history_cache_dir)

    def fetch_price_df():
        return fetch(args.ticker, lookback_days, force_refresh=True)

    alerter = (
        WebhookAlerter(settings.alerting.webhook_url)
        if settings.alerting.enabled and settings.alerting.webhook_url
        else LoggingAlerter()
    )

    state_path = Path(args.state_file) if args.state_file else REPO_ROOT / "data" / "paper_state" / f"{run_id}.json"

    restored = load_state(state_path, settings.risk)
    if restored is not None:
        broker, risk_engine, initial_last_run_date = restored
        log.info("run_paper.resuming", run_id=run_id, state_file=str(state_path),
                  equity=broker.get_account().equity, last_run_date=str(initial_last_run_date))
        print(f"Resuming from saved state ({state_path}). Equity: ${broker.get_account().equity:,.2f}")
        if initial_last_run_date is not None:
            print(f"Last trading day already processed: {initial_last_run_date}")
    else:
        broker = ShadowBrokerClient(starting_cash=config.starting_cash)
        risk_engine = RiskEngine(settings.risk)
        initial_last_run_date = None
        log.info("run_paper.starting", ticker=args.ticker, run_id=run_id, starting_cash=config.starting_cash)
        print(f"Paper trading started. run_id={run_id}")

    ledger = Ledger(settings.resolved_ledger_db_path)
    print(f"View live: streamlit run dashboard/app.py  (filter to run_id={run_id})")

    def persist_state(last_run_date) -> None:
        save_state(state_path, broker, risk_engine, last_run_date)

    try:
        cycles = run_paper_trading_daemon(
            broker, risk_engine, ledger, run_id, config, fetch_price_df,
            alerter=alerter, max_cycles=args.max_cycles, on_cycle_complete=persist_state,
            initial_last_run_date=initial_last_run_date,
            wait_for_next_day=args.max_cycles is None,
        )
        if cycles == 0:
            print(f"Nothing to do -- today's trading day was already processed "
                  f"(last run: {initial_last_run_date}).")
        print(f"Completed {cycles} trading day(s). Final equity: ${broker.get_account().equity:,.2f}")
    finally:
        ledger.close()


if __name__ == "__main__":
    main()
