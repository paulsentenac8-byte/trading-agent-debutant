from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np


@dataclass
class BreadthSnapshot:
    count: int
    pct_above_sma50: float
    pct_above_sma200: float
    avg_mom20: float
    avg_rel_strength20: float
    breadth_bias: float
    summary: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_breadth_context(snapshots: dict[str, dict[str, Any]]) -> BreadthSnapshot:
    if not snapshots:
        return BreadthSnapshot(
            count=0,
            pct_above_sma50=0.0,
            pct_above_sma200=0.0,
            avg_mom20=0.0,
            avg_rel_strength20=0.0,
            breadth_bias=0.0,
            summary=["Breadth indisponible: aucun snapshot exploitable."],
        )

    rows = list(snapshots.values())
    count = len(rows)
    pct_above_sma50 = float(np.mean([1.0 if r["close"] > r["sma_50"] else 0.0 for r in rows]))
    pct_above_sma200 = float(np.mean([1.0 if r["close"] > r["sma_200"] else 0.0 for r in rows]))
    avg_mom20 = float(np.mean([r["mom_20"] for r in rows]))
    avg_rel_strength20 = float(np.mean([r["rel_strength_20"] for r in rows]))

    bias = 0.0
    summary: list[str] = []

    if pct_above_sma50 >= 0.7:
        bias += 0.3
        summary.append("Breadth solide: plus de 70% des titres au-dessus de leur SMA50.")
    elif pct_above_sma50 <= 0.35:
        bias -= 0.45
        summary.append("Breadth faible: moins de 35% des titres au-dessus de leur SMA50.")
    else:
        summary.append("Breadth moyenne sur SMA50.")

    if pct_above_sma200 >= 0.65:
        bias += 0.25
        summary.append("Tendance de fond positive: beaucoup de titres au-dessus de la SMA200.")
    elif pct_above_sma200 <= 0.3:
        bias -= 0.4
        summary.append("Tendance de fond fragile: peu de titres au-dessus de la SMA200.")

    if avg_mom20 > 0:
        bias += 0.1
        summary.append("Momentum moyen 20j positif sur l'univers.")
    else:
        bias -= 0.1
        summary.append("Momentum moyen 20j négatif sur l'univers.")

    if avg_rel_strength20 > 0:
        bias += 0.05
    else:
        bias -= 0.05

    bias = float(np.clip(bias, -0.75, 0.75))

    return BreadthSnapshot(
        count=count,
        pct_above_sma50=round(pct_above_sma50, 4),
        pct_above_sma200=round(pct_above_sma200, 4),
        avg_mom20=round(avg_mom20, 4),
        avg_rel_strength20=round(avg_rel_strength20, 4),
        breadth_bias=round(bias, 4),
        summary=summary,
    )
