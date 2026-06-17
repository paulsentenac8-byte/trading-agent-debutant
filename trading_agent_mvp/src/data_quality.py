from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd

from .runtime import utc_now_iso


@dataclass
class DataQualitySummary:
    checked_at: str
    universe_count: int
    downloaded_count: int
    eligible_count: int
    coverage_ratio: float
    benchmark_present: bool
    stale_symbols: list[str]
    short_history_symbols: list[str]
    status: str
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_data_quality_summary(
    requested_symbols: list[str],
    market_data: dict[str, pd.DataFrame],
    eligible_symbols: list[str],
    benchmark_symbol: str,
    min_history_bars: int = 220,
    max_stale_days: int = 7,
) -> DataQualitySummary:
    warnings: list[str] = []
    stale_symbols: list[str] = []
    short_history_symbols: list[str] = []

    now = pd.Timestamp.utcnow().tz_localize(None)

    for symbol, df in market_data.items():
        if df.empty:
            short_history_symbols.append(symbol)
            continue
        if len(df) < min_history_bars:
            short_history_symbols.append(symbol)
        last_dt = pd.Timestamp(df.index[-1]).tz_localize(None) if getattr(df.index[-1], "tzinfo", None) is not None else pd.Timestamp(df.index[-1])
        if (now - last_dt).days > max_stale_days:
            stale_symbols.append(symbol)

    coverage_ratio = float(len(market_data) / len(requested_symbols)) if requested_symbols else 0.0
    benchmark_present = benchmark_symbol in market_data

    if coverage_ratio < 0.8:
        warnings.append("Couverture de données faible: moins de 80% des symboles demandés téléchargés.")
    if stale_symbols:
        warnings.append(f"Données potentiellement anciennes pour {len(stale_symbols)} symbole(s).")
    if short_history_symbols:
        warnings.append(f"Historique insuffisant pour {len(short_history_symbols)} symbole(s).")
    if not benchmark_present:
        warnings.append("Benchmark absent des données téléchargées.")

    status = "ok"
    if warnings:
        status = "warning"
    if not benchmark_present:
        status = "error"

    return DataQualitySummary(
        checked_at=utc_now_iso(),
        universe_count=len(requested_symbols),
        downloaded_count=len(market_data),
        eligible_count=len(eligible_symbols),
        coverage_ratio=round(coverage_ratio, 4),
        benchmark_present=benchmark_present,
        stale_symbols=stale_symbols,
        short_history_symbols=short_history_symbols,
        status=status,
        warnings=warnings,
    )
