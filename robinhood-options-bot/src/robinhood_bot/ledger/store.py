"""Append-only ledger: the source of truth every observability layer reads from.

Backtest, paper, and live runs all write to this same schema (distinguished
by `mode` and `run_id`), so comparing live results against backtest
expectations in Phase 7 is a query against this table, not a guess.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from robinhood_bot.broker.base import OrderResult

_SCHEMA = """
CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    run_id TEXT NOT NULL,
    mode TEXT NOT NULL,
    ticker TEXT NOT NULL,
    trend TEXT NOT NULL,
    iv_rank REAL,
    recommended_strategy TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS risk_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    run_id TEXT NOT NULL,
    mode TEXT NOT NULL,
    strategy_tag TEXT NOT NULL,
    approved INTEGER NOT NULL,
    reason TEXT,
    suggested_quantity INTEGER,
    max_loss_per_unit REAL
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    run_id TEXT NOT NULL,
    mode TEXT NOT NULL,
    broker_order_id TEXT,
    strategy_tag TEXT NOT NULL,
    legs_json TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    status TEXT NOT NULL,
    fill_price REAL,
    reason TEXT
);

CREATE TABLE IF NOT EXISTS equity_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    run_id TEXT NOT NULL,
    mode TEXT NOT NULL,
    equity REAL NOT NULL,
    cash REAL NOT NULL
);
"""

_TABLES = {"signals", "risk_decisions", "orders", "equity_snapshots"}


class Ledger:
    def __init__(self, db_path: str | Path):
        db_path = Path(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # -- write side --

    def record_signal(self, run_id: str, mode: str, ticker: str, trend: str,
                       iv_rank: float | None, recommended_strategy: str) -> None:
        self._conn.execute(
            "INSERT INTO signals (ts, run_id, mode, ticker, trend, iv_rank, recommended_strategy) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (_now(), run_id, mode, ticker, trend, iv_rank, recommended_strategy),
        )
        self._conn.commit()

    def record_risk_decision(self, run_id: str, mode: str, strategy_tag: str,
                              approved: bool, reason: str | None,
                              suggested_quantity: int, max_loss_per_unit: float | None) -> None:
        self._conn.execute(
            "INSERT INTO risk_decisions (ts, run_id, mode, strategy_tag, approved, reason, "
            "suggested_quantity, max_loss_per_unit) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (_now(), run_id, mode, strategy_tag, int(approved), reason,
             suggested_quantity, max_loss_per_unit),
        )
        self._conn.commit()

    def record_order(self, run_id: str, mode: str, order_result: "OrderResult") -> None:
        order = order_result.order
        legs_json = json.dumps([
            {
                "occ_symbol": leg.contract.occ_symbol,
                "side": leg.side.value,
                "quantity": leg.quantity,
            }
            for leg in order.legs
        ])
        self._conn.execute(
            "INSERT INTO orders (ts, run_id, mode, broker_order_id, strategy_tag, legs_json, "
            "quantity, status, fill_price, reason) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (_now(), run_id, mode, order.order_id, order.strategy_tag, legs_json,
             sum(leg.quantity for leg in order.legs), order_result.status.value,
             order_result.fill_price, order_result.reason),
        )
        self._conn.commit()

    def record_equity_snapshot(self, run_id: str, mode: str, equity: float, cash: float) -> None:
        self._conn.execute(
            "INSERT INTO equity_snapshots (ts, run_id, mode, equity, cash) VALUES (?, ?, ?, ?, ?)",
            (_now(), run_id, mode, equity, cash),
        )
        self._conn.commit()

    # -- read side, used by the dashboard and (later) backtest reports --

    def recent_orders(self, run_id: str | None = None, limit: int = 50) -> list[dict]:
        return self._select("orders", run_id, limit)

    def recent_risk_decisions(self, run_id: str | None = None, limit: int = 50) -> list[dict]:
        return self._select("risk_decisions", run_id, limit)

    def recent_signals(self, run_id: str | None = None, limit: int = 50) -> list[dict]:
        return self._select("signals", run_id, limit)

    def equity_curve(self, run_id: str | None = None) -> list[dict]:
        return self._select("equity_snapshots", run_id, limit=None, order="ts ASC")

    def _select(self, table: str, run_id: str | None, limit: int | None,
                order: str = "ts DESC") -> list[dict]:
        assert table in _TABLES, f"unknown ledger table {table!r}"
        query = f"SELECT * FROM {table}"  # nosec: table is from the fixed _TABLES set above, never external input
        params: tuple = ()
        if run_id is not None:
            query += " WHERE run_id = ?"
            params = (run_id,)
        query += f" ORDER BY {order}"
        if limit is not None:
            query += " LIMIT ?"
            params += (limit,)
        cursor = self._conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
