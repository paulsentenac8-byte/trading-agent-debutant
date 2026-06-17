from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from .runtime import utc_now_iso


SCHEMA = """
CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    regime TEXT,
    health_score INTEGER,
    readiness_score INTEGER,
    ranked_count INTEGER,
    orders_count INTEGER,
    report_json TEXT
);

CREATE TABLE IF NOT EXISTS ranked_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    symbol TEXT,
    score REAL,
    close REAL,
    reasons TEXT,
    FOREIGN KEY(run_id) REFERENCES pipeline_runs(run_id)
);

CREATE TABLE IF NOT EXISTS proposed_orders_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    symbol TEXT,
    qty INTEGER,
    reference_price REAL,
    stop_loss REAL,
    take_profit REAL,
    rationale TEXT,
    FOREIGN KEY(run_id) REFERENCES pipeline_runs(run_id)
);
"""


@dataclass
class HistorySummary:
    runs: list[dict[str, Any]]
    recent_signals: list[dict[str, Any]]
    recent_orders: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str | Path) -> None:
    with _connect(db_path) as conn:
        conn.executescript(SCHEMA)
        conn.commit()


def store_pipeline_run(
    db_path: str | Path,
    regime: str,
    health_score: int,
    readiness_score: int,
    ranked: pd.DataFrame,
    trade_plan: pd.DataFrame,
    report_payload: dict[str, Any],
) -> int:
    init_db(db_path)
    with _connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO pipeline_runs (created_at, regime, health_score, readiness_score, ranked_count, orders_count, report_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                utc_now_iso(),
                regime,
                int(health_score),
                int(readiness_score),
                int(len(ranked)),
                int(len(trade_plan)),
                json.dumps(report_payload, ensure_ascii=False),
            ),
        )
        run_id = int(cur.lastrowid)

        if not ranked.empty:
            rows = []
            for _, row in ranked.head(50).iterrows():
                rows.append((run_id, str(row.get("symbol")), float(row.get("score", 0.0)), float(row.get("close", 0.0)), str(row.get("reasons", ""))))
            conn.executemany(
                "INSERT INTO ranked_history (run_id, symbol, score, close, reasons) VALUES (?, ?, ?, ?, ?)",
                rows,
            )

        if not trade_plan.empty:
            rows = []
            for _, row in trade_plan.iterrows():
                rows.append(
                    (
                        run_id,
                        str(row.get("symbol")),
                        int(float(row.get("qty", 0))),
                        float(row.get("close", 0.0)),
                        float(row.get("stop_loss", 0.0)),
                        float(row.get("take_profit", 0.0)),
                        str(row.get("reasons", "")),
                    )
                )
            conn.executemany(
                "INSERT INTO proposed_orders_history (run_id, symbol, qty, reference_price, stop_loss, take_profit, rationale) VALUES (?, ?, ?, ?, ?, ?, ?)",
                rows,
            )

        conn.commit()
        return run_id


def load_history_summary(db_path: str | Path, run_limit: int = 20, item_limit: int = 50) -> HistorySummary:
    init_db(db_path)
    with _connect(db_path) as conn:
        runs = [dict(row) for row in conn.execute("SELECT run_id, created_at, regime, health_score, readiness_score, ranked_count, orders_count FROM pipeline_runs ORDER BY run_id DESC LIMIT ?", (run_limit,)).fetchall()]
        recent_signals = [dict(row) for row in conn.execute("SELECT run_id, symbol, score, close, reasons FROM ranked_history ORDER BY id DESC LIMIT ?", (item_limit,)).fetchall()]
        recent_orders = [dict(row) for row in conn.execute("SELECT run_id, symbol, qty, reference_price, stop_loss, take_profit, rationale FROM proposed_orders_history ORDER BY id DESC LIMIT ?", (item_limit,)).fetchall()]
    return HistorySummary(runs=runs, recent_signals=recent_signals, recent_orders=recent_orders)
