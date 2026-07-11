#!/usr/bin/env python3
"""CLI entrypoint: fetch price history, run a backtest (optionally with
walk-forward folds and/or sensitivity analysis), print a summary, and leave
everything in the ledger for the dashboard.

    python scripts/run_backtest.py --ticker SPY
    python scripts/run_backtest.py --ticker SPY --n-folds 3
    python scripts/run_backtest.py --ticker SPY --iv-sensitivity --execution-sensitivity

Requires network access to the price data vendor -- see README.md's "Known
issues" section if this environment's network policy blocks it.
"""
from __future__ import annotations

import argparse

from robinhood_bot.backtest.engine import BacktestConfig, run_backtest
from robinhood_bot.backtest.sensitivity import run_execution_sensitivity, run_iv_sensitivity
from robinhood_bot.backtest.walk_forward import run_walk_forward
from robinhood_bot.config import load_settings
from robinhood_bot.data.price_history import fetch_price_history
from robinhood_bot.ledger.store import Ledger
from robinhood_bot.logging_setup import configure_logging, get_logger
from robinhood_bot.monitoring.metrics import cagr, max_drawdown_pct, sharpe_ratio, summarize_equity_curve

log = get_logger(__name__)


def _print_summary(label: str, result) -> None:
    summary = summarize_equity_curve(result.equity_curve)
    if summary is None:
        print(f"{label}: no trading days in this run")
        return
    growth_rate = cagr(result.equity_curve)
    sharpe = sharpe_ratio(result.equity_curve)
    print(
        f"{label}: run_id={result.run_id} "
        f"final_equity=${summary.current_equity:,.2f} "
        f"max_drawdown={max_drawdown_pct(result.equity_curve):.2f}% "
        f"cagr={f'{growth_rate * 100:.2f}%' if growth_rate is not None else 'n/a'} "
        f"sharpe={f'{sharpe:.2f}' if sharpe is not None else 'n/a'}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--lookback-days", type=int, default=None,
                         help="Defaults to config/settings.yaml -> data.default_lookback_days")
    parser.add_argument("--starting-cash", type=float, default=100_000)
    parser.add_argument("--iv-rank-threshold", type=float, default=50.0)
    parser.add_argument("--dte-target", type=int, default=30)
    parser.add_argument("--spread-width", type=float, default=5.0)
    parser.add_argument("--n-folds", type=int, default=None, help="Run walk-forward validation with this many folds")
    parser.add_argument("--iv-sensitivity", action="store_true")
    parser.add_argument("--execution-sensitivity", action="store_true")
    args = parser.parse_args()

    settings = load_settings()
    configure_logging(settings.logging)

    lookback_days = args.lookback_days or settings.data.default_lookback_days
    price_df = fetch_price_history(args.ticker, lookback_days, settings.resolved_price_history_cache_dir)

    config = BacktestConfig(
        ticker=args.ticker,
        starting_cash=args.starting_cash,
        iv_rank_threshold=args.iv_rank_threshold,
        dte_target=args.dte_target,
        spread_width=args.spread_width,
    )

    ledger = Ledger(settings.resolved_ledger_db_path)
    try:
        if args.n_folds:
            results = run_walk_forward(price_df, config, settings.risk, ledger, n_folds=args.n_folds)
            for i, result in enumerate(results):
                _print_summary(f"fold {i}", result)
        else:
            result = run_backtest(price_df, config, settings.risk, ledger)
            _print_summary("backtest", result)

        if args.iv_sensitivity:
            for multiplier, result in run_iv_sensitivity(price_df, config, settings.risk, ledger).items():
                _print_summary(f"iv_sensitivity x{multiplier}", result)

        if args.execution_sensitivity:
            for name, result in run_execution_sensitivity(price_df, config, settings.risk, ledger).items():
                _print_summary(f"execution_sensitivity {name}", result)
    finally:
        ledger.close()

    print(f"\nView details: streamlit run dashboard/app.py  (ledger: {settings.resolved_ledger_db_path})")


if __name__ == "__main__":
    main()
