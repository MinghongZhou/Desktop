"""Live observability dashboard: reads the shared ledger, nothing else.

Run with:
    streamlit run dashboard/app.py

Works for backtest, paper, and live runs alike -- pass a run_id via the
sidebar to filter to one run, or leave it blank to see everything.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from robinhood_bot.config import load_settings
from robinhood_bot.ledger.store import Ledger
from robinhood_bot.monitoring.metrics import cagr, max_drawdown_pct, sharpe_ratio, summarize_equity_curve

st.set_page_config(page_title="Robinhood Options Bot", layout="wide")

settings = load_settings()
ledger = Ledger(settings.resolved_ledger_db_path)

st.title("Robinhood Options Bot — Observability")

run_id = st.sidebar.text_input("Filter to run_id (blank = all runs)") or None

equity_rows = ledger.equity_curve(run_id=run_id)
summary = summarize_equity_curve(equity_rows)

col1, col2, col3, col4 = st.columns(4)
if summary:
    col1.metric("Current equity", f"${summary.current_equity:,.2f}")
    col2.metric("Peak equity", f"${summary.peak_equity:,.2f}")
    col3.metric("Drawdown from peak", f"{summary.drawdown_pct:.2f}%")
    col4.metric("Max drawdown (full curve)", f"{max_drawdown_pct(equity_rows):.2f}%")
else:
    st.info("No equity snapshots recorded yet for this run_id.")

if equity_rows:
    df = pd.DataFrame(equity_rows)
    df["ts"] = pd.to_datetime(df["ts"])
    st.line_chart(df.set_index("ts")["equity"])

    stats_col1, stats_col2 = st.columns(2)
    growth_rate = cagr(equity_rows)
    stats_col1.metric("CAGR (annualized)", f"{growth_rate * 100:.2f}%" if growth_rate is not None else "n/a")
    sharpe = sharpe_ratio(equity_rows)
    stats_col2.metric("Sharpe ratio", f"{sharpe:.2f}" if sharpe is not None else "n/a")

st.caption(
    "Backtest equity curves are built from simulated (Black-Scholes) option "
    "pricing, not replayed historical quotes -- see the project README."
)

st.subheader("Recent risk decisions")
decisions = ledger.recent_risk_decisions(run_id=run_id, limit=200)
if decisions:
    df_dec = pd.DataFrame(decisions)
    rejected = df_dec[df_dec["approved"] == 0]
    if not rejected.empty:
        st.warning(f"{len(rejected)} rejected trade(s) in the last {len(df_dec)} risk decisions.")
    st.dataframe(df_dec, width="stretch")
else:
    st.info("No risk decisions recorded yet.")

st.subheader("Recent orders")
orders = ledger.recent_orders(run_id=run_id, limit=200)
st.dataframe(pd.DataFrame(orders) if orders else pd.DataFrame(), width="stretch")

st.subheader("Recent signals")
signals = ledger.recent_signals(run_id=run_id, limit=200)
st.dataframe(pd.DataFrame(signals) if signals else pd.DataFrame(), width="stretch")
