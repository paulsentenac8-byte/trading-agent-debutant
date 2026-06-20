from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from .runtime import utc_now_iso
from .scalars import to_float, to_int


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

CREATE TABLE IF NOT EXISTS signal_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    signal_date TEXT NOT NULL,
    symbol TEXT NOT NULL,
    entry_price REAL,
    score REAL,
    regime TEXT,
    selected_flag INTEGER DEFAULT 0,
    sector TEXT,
    trend_component REAL,
    momentum_component REAL,
    breakout_component REAL,
    pullback_component REAL,
    quality_component REAL,
    outcome_1d REAL,
    outcome_5d REAL,
    outcome_20d REAL,
    mfe_20d REAL,
    mae_20d REAL,
    updated_at TEXT,
    UNIQUE(run_id, symbol)
);
"""


@dataclass
class HistorySummary:
    runs: list[dict[str, Any]]
    recent_signals: list[dict[str, Any]]
    recent_orders: list[dict[str, Any]]
    run_timeseries: list[dict[str, Any]]
    signal_outcome_summary: dict[str, Any]
    best_symbols_20d: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LearningSummary:
    matured_signals: int
    selected_signals: int
    regime_stats: list[dict[str, Any]]
    symbol_stats: list[dict[str, Any]]
    setup_stats: list[dict[str, Any]]
    recommendations: list[str]

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


def _store_signal_memory(conn: sqlite3.Connection, run_id: int, regime: str, ranked: pd.DataFrame, trade_plan: pd.DataFrame) -> None:
    if ranked.empty:
        return

    selected_symbols = set(trade_plan["symbol"].astype(str).tolist()) if not trade_plan.empty and "symbol" in trade_plan.columns else set()
    rows: list[tuple[Any, ...]] = []

    for _, row in ranked.head(30).iterrows():
        rows.append(
            (
                run_id,
                utc_now_iso(),
                str(row.get("date", "")),
                str(row.get("symbol", "")),
                to_float(row.get("close")),
                to_float(row.get("score")),
                regime,
                1 if str(row.get("symbol", "")) in selected_symbols else 0,
                str(row.get("sector", "Unknown")),
                to_float(row.get("trend_component")),
                to_float(row.get("momentum_component")),
                to_float(row.get("breakout_component")),
                to_float(row.get("pullback_component")),
                to_float(row.get("quality_component")),
                utc_now_iso(),
            )
        )

    conn.executemany(
        """
        INSERT OR IGNORE INTO signal_memory (
            run_id, created_at, signal_date, symbol, entry_price, score, regime, selected_flag, sector,
            trend_component, momentum_component, breakout_component, pullback_component, quality_component, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )


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
                rows.append(
                    (
                        run_id,
                        str(row.get("symbol")),
                        to_float(row.get("score")),
                        to_float(row.get("close")),
                        str(row.get("reasons", "")),
                    )
                )
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
                        to_int(row.get("qty")),
                        to_float(row.get("close")),
                        to_float(row.get("stop_loss")),
                        to_float(row.get("take_profit")),
                        str(row.get("reasons", "")),
                    )
                )
            conn.executemany(
                "INSERT INTO proposed_orders_history (run_id, symbol, qty, reference_price, stop_loss, take_profit, rationale) VALUES (?, ?, ?, ?, ?, ?, ?)",
                rows,
            )

        _store_signal_memory(conn, run_id, regime, ranked, trade_plan)
        conn.commit()
        return run_id


def update_signal_outcomes(db_path: str | Path, market_data: dict[str, pd.DataFrame]) -> int:
    init_db(db_path)
    updated = 0

    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, symbol, signal_date, entry_price, outcome_1d, outcome_5d, outcome_20d
            FROM signal_memory
            """
        ).fetchall()

        for row in rows:
            symbol = str(row["symbol"])
            if symbol not in market_data:
                continue
            df = market_data[symbol]
            if df.empty:
                continue

            signal_date = pd.Timestamp(str(row["signal_date"]))
            idx = df.index.get_indexer([signal_date], method="nearest")
            if len(idx) == 0 or idx[0] < 0:
                continue
            loc = int(idx[0])
            entry = to_float(row["entry_price"])
            if entry <= 0:
                continue

            closes = df["Adj Close"].reset_index(drop=True)
            outcome_1d = row["outcome_1d"]
            outcome_5d = row["outcome_5d"]
            outcome_20d = row["outcome_20d"]
            mfe_20d = None
            mae_20d = None

            if outcome_1d is None and loc + 1 < len(closes):
                outcome_1d = to_float(closes.iloc[loc + 1]) / entry - 1
            if outcome_5d is None and loc + 5 < len(closes):
                outcome_5d = to_float(closes.iloc[loc + 5]) / entry - 1
            if outcome_20d is None and loc + 20 < len(closes):
                future = closes.iloc[loc + 1 : loc + 21]
                if len(future) > 0:
                    outcome_20d = to_float(closes.iloc[loc + 20]) / entry - 1
                    mfe_20d = float(future.max() / entry - 1)
                    mae_20d = float(future.min() / entry - 1)

            conn.execute(
                """
                UPDATE signal_memory
                SET outcome_1d = COALESCE(?, outcome_1d),
                    outcome_5d = COALESCE(?, outcome_5d),
                    outcome_20d = COALESCE(?, outcome_20d),
                    mfe_20d = COALESCE(?, mfe_20d),
                    mae_20d = COALESCE(?, mae_20d),
                    updated_at = ?
                WHERE id = ?
                """,
                (outcome_1d, outcome_5d, outcome_20d, mfe_20d, mae_20d, utc_now_iso(), int(row["id"])),
            )
            updated += 1

        conn.commit()
    return updated


def _signal_outcome_summary(conn: sqlite3.Connection) -> dict[str, Any]:
    rows = conn.execute(
        """
        SELECT outcome_1d, outcome_5d, outcome_20d, mfe_20d, mae_20d
        FROM signal_memory
        WHERE outcome_20d IS NOT NULL
        """
    ).fetchall()
    if not rows:
        return {
            "matured_signals": 0,
            "mean_return_1d": None,
            "mean_return_5d": None,
            "mean_return_20d": None,
            "win_rate_5d": None,
            "win_rate_20d": None,
            "mean_mfe_20d": None,
            "mean_mae_20d": None,
        }

    df = pd.DataFrame(rows, columns=["outcome_1d", "outcome_5d", "outcome_20d", "mfe_20d", "mae_20d"])
    return {
        "matured_signals": int(len(df)),
        "mean_return_1d": round(float(df["outcome_1d"].mean()), 4),
        "mean_return_5d": round(float(df["outcome_5d"].mean()), 4),
        "mean_return_20d": round(float(df["outcome_20d"].mean()), 4),
        "win_rate_5d": round(float((df["outcome_5d"] > 0).mean()), 4),
        "win_rate_20d": round(float((df["outcome_20d"] > 0).mean()), 4),
        "mean_mfe_20d": round(float(df["mfe_20d"].mean()), 4),
        "mean_mae_20d": round(float(df["mae_20d"].mean()), 4),
    }


def load_history_summary(db_path: str | Path, run_limit: int = 30, item_limit: int = 80) -> HistorySummary:
    init_db(db_path)
    with _connect(db_path) as conn:
        runs = [dict(row) for row in conn.execute("SELECT run_id, created_at, regime, health_score, readiness_score, ranked_count, orders_count FROM pipeline_runs ORDER BY run_id DESC LIMIT ?", (run_limit,)).fetchall()]
        recent_signals = [dict(row) for row in conn.execute("SELECT run_id, symbol, score, close, reasons FROM ranked_history ORDER BY id DESC LIMIT ?", (item_limit,)).fetchall()]
        recent_orders = [dict(row) for row in conn.execute("SELECT run_id, symbol, qty, reference_price, stop_loss, take_profit, rationale FROM proposed_orders_history ORDER BY id DESC LIMIT ?", (item_limit,)).fetchall()]
        run_timeseries = [dict(row) for row in conn.execute("SELECT run_id, created_at, regime, health_score, readiness_score, ranked_count, orders_count FROM pipeline_runs ORDER BY run_id ASC LIMIT ?", (run_limit,)).fetchall()]
        best_symbols_20d = [
            dict(row)
            for row in conn.execute(
                """
                SELECT symbol, ROUND(AVG(outcome_20d), 4) AS avg_outcome_20d, COUNT(*) AS observations
                FROM signal_memory
                WHERE outcome_20d IS NOT NULL
                GROUP BY symbol
                HAVING COUNT(*) >= 1
                ORDER BY avg_outcome_20d DESC
                LIMIT 10
                """
            ).fetchall()
        ]
        outcome_summary = _signal_outcome_summary(conn)
    return HistorySummary(
        runs=runs,
        recent_signals=recent_signals,
        recent_orders=recent_orders,
        run_timeseries=run_timeseries,
        signal_outcome_summary=outcome_summary,
        best_symbols_20d=best_symbols_20d,
    )


def load_learning_summary(db_path: str | Path) -> LearningSummary:
    init_db(db_path)
    with _connect(db_path) as conn:
        matured = conn.execute("SELECT * FROM signal_memory WHERE outcome_20d IS NOT NULL").fetchall()
        if not matured:
            return LearningSummary(0, 0, [], [], [], ["Pas assez d'historique mature pour générer des apprentissages."])

        regime_stats = [
            dict(row)
            for row in conn.execute(
                """
                SELECT regime, COUNT(*) AS observations,
                       ROUND(AVG(outcome_5d), 4) AS avg_outcome_5d,
                       ROUND(AVG(outcome_20d), 4) AS avg_outcome_20d,
                       ROUND(AVG(CASE WHEN outcome_20d > 0 THEN 1.0 ELSE 0.0 END), 4) AS win_rate_20d
                FROM signal_memory
                WHERE outcome_20d IS NOT NULL
                GROUP BY regime
                ORDER BY avg_outcome_20d DESC
                """
            ).fetchall()
        ]
        symbol_stats = [
            dict(row)
            for row in conn.execute(
                """
                SELECT symbol, COUNT(*) AS observations,
                       ROUND(AVG(outcome_20d), 4) AS avg_outcome_20d,
                       ROUND(AVG(CASE WHEN outcome_20d > 0 THEN 1.0 ELSE 0.0 END), 4) AS win_rate_20d
                FROM signal_memory
                WHERE outcome_20d IS NOT NULL
                GROUP BY symbol
                ORDER BY observations DESC, avg_outcome_20d DESC
                LIMIT 15
                """
            ).fetchall()
        ]
        setup_stats = [
            dict(row)
            for row in conn.execute(
                """
                SELECT selected_flag,
                       ROUND(AVG(trend_component), 4) AS avg_trend,
                       ROUND(AVG(momentum_component), 4) AS avg_momentum,
                       ROUND(AVG(breakout_component), 4) AS avg_breakout,
                       ROUND(AVG(pullback_component), 4) AS avg_pullback,
                       ROUND(AVG(quality_component), 4) AS avg_quality,
                       ROUND(AVG(outcome_20d), 4) AS avg_outcome_20d,
                       COUNT(*) AS observations
                FROM signal_memory
                WHERE outcome_20d IS NOT NULL
                GROUP BY selected_flag
                ORDER BY selected_flag DESC
                """
            ).fetchall()
        ]

        matured_count = int(len(matured))
        selected_count = int(
            conn.execute("SELECT COUNT(*) FROM signal_memory WHERE selected_flag = 1").fetchone()[0]
        )

    recommendations: list[str] = []
    if regime_stats:
        best_regime = regime_stats[0]
        recommendations.append(f"Régime le plus favorable observé: {best_regime['regime']} (avg 20d={best_regime['avg_outcome_20d']}).")
    if symbol_stats:
        best_symbol = symbol_stats[0]
        recommendations.append(f"Symbole le plus robuste observé: {best_symbol['symbol']} (avg 20d={best_symbol['avg_outcome_20d']}).")
    recommendations.append("Quand l'historique grossira, ces apprentissages deviendront beaucoup plus fiables.")

    return LearningSummary(
        matured_signals=matured_count,
        selected_signals=selected_count,
        regime_stats=regime_stats,
        symbol_stats=symbol_stats,
        setup_stats=setup_stats,
        recommendations=recommendations,
    )
