from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd


@dataclass
class ExposureSummary:
    gross_exposure_pct: float
    cash_buffer_pct: float
    sector_allocation: dict[str, float]
    largest_position_pct: float
    notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_exposure_summary(trade_plan: pd.DataFrame, capital: float) -> ExposureSummary:
    if trade_plan.empty or capital <= 0:
        return ExposureSummary(0.0, 1.0, {}, 0.0, ["Aucune exposition active proposée."])

    sector_alloc: dict[str, float] = {}
    if "sector" in trade_plan.columns:
        grouped = trade_plan.groupby("sector")["allocation"].sum() / capital
        sector_alloc = {str(k): round(float(v), 4) for k, v in grouped.items()}

    gross = float(trade_plan["allocation"].sum() / capital)
    cash_buffer = max(1 - gross, 0.0)
    largest_position = float((trade_plan["allocation"] / capital).max()) if not trade_plan.empty else 0.0

    return ExposureSummary(
        gross_exposure_pct=round(gross, 4),
        cash_buffer_pct=round(cash_buffer, 4),
        sector_allocation=sector_alloc,
        largest_position_pct=round(largest_position, 4),
        notes=[
            "Le gross exposure indique la part du capital réellement engagée.",
            "Les allocations sectorielles permettent de vérifier la concentration cachée.",
        ],
    )
