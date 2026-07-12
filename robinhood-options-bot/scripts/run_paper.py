#!/usr/bin/env python3
"""CLI entrypoint: long-running paper-trading daemon (Phase 7).

    python scripts/run_paper.py --ticker SPY

Runs shadow mode (simulated option pricing) against a live-refreshing
underlying price feed, one trading day per cycle, forever -- intended to
run as a long-lived process (per the plan's "standalone Python service"
execution model), not re-invoked fresh via cron. Broker and risk-engine
state live in memory for the life of the process; killing and restarting
it starts a fresh account, since nothing here persists state to disk yet.

Requires network access to the price data vendor (Alpaca by default, see
config/settings.yaml -> data.price_history_source) and, when that source
is "alpaca", ALPACA_API_KEY / ALPACA_API_SECRET env vars.
"""
from __future__ import annotations

import argparse
import uuid

from robinhood_bot.backtest.engine import BacktestConfig
from robinhood_bot.broker.shadow import ShadowBrokerClient
from robinhood_bot.config import load_settings
from robinhood_bot.data.factory import build_price_history_fetcher
from robinhood_bot.execution.paper_loop import run_paper_trading_daemon
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

    broker = ShadowBrokerClient(starting_cash=config.starting_cash)
    risk_engine = RiskEngine(settings.risk)
    ledger = Ledger(settings.resolved_ledger_db_path)

    log.info("run_paper.starting", ticker=args.ticker, run_id=run_id, starting_cash=config.starting_cash)
    print(f"Paper trading started. run_id={run_id}")
    print(f"View live: streamlit run dashboard/app.py  (filter to run_id={run_id})")

    try:
        cycles = run_paper_trading_daemon(
            broker, risk_engine, ledger, run_id, config, fetch_price_df,
            alerter=alerter, max_cycles=args.max_cycles,
        )
        print(f"Completed {cycles} trading day(s). Final equity: ${broker.get_account().equity:,.2f}")
    finally:
        ledger.close()


if __name__ == "__main__":
    main()
