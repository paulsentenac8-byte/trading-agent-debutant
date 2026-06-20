from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd


@dataclass
class AnomalySummary:
    status: str
    flagged_orders: int
    flagged_signals: int
    messages: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def detect_anomalies(ranked: pd.DataFrame, trade_plan: pd.DataFrame) -> AnomalySummary:
    messages: list[str] = []
    flagged_orders = 0
    flagged_signals = 0

    if not ranked.empty:
        if "score" in ranked.columns:
            extreme_scores = ranked[(ranked["score"] > 9) | (ranked["score"] < -6)]
            if not extreme_scores.empty:
                flagged_signals += len(extreme_scores)
                messages.append(f"{len(extreme_scores)} signal(aux) avec score extrême détecté(s).")

        if "vol_20" in ranked.columns:
            extreme_vol = ranked[ranked["vol_20"] > 1.2]
            if not extreme_vol.empty:
                flagged_signals += len(extreme_vol)
                messages.append(f"{len(extreme_vol)} signal(aux) avec volatilité annualisée très élevée.")

    if not trade_plan.empty:
        if "stop_pct" in trade_plan.columns:
            wide_stops = trade_plan[trade_plan["stop_pct"] > 0.12]
            if not wide_stops.empty:
                flagged_orders += len(wide_stops)
                messages.append(f"{len(wide_stops)} ordre(s) avec stop trop large.")

        if "conviction_multiplier" in trade_plan.columns:
            odd_conviction = trade_plan[(trade_plan["conviction_multiplier"] < 0.5) | (trade_plan["conviction_multiplier"] > 1.5)]
            if not odd_conviction.empty:
                flagged_orders += len(odd_conviction)
                messages.append(f"{len(odd_conviction)} ordre(s) avec conviction inhabituelle.")

        if "risk_amount" in trade_plan.columns:
            nonpositive_risk = trade_plan[trade_plan["risk_amount"] <= 0]
            if not nonpositive_risk.empty:
                flagged_orders += len(nonpositive_risk)
                messages.append(f"{len(nonpositive_risk)} ordre(s) avec risque nul ou négatif.")

        if "allocation" in trade_plan.columns:
            negative_alloc = trade_plan[trade_plan["allocation"] <= 0]
            if not negative_alloc.empty:
                flagged_orders += len(negative_alloc)
                messages.append(f"{len(negative_alloc)} ordre(s) avec allocation invalide.")

    status = "ok" if not messages else "warning"
    return AnomalySummary(status=status, flagged_orders=flagged_orders, flagged_signals=flagged_signals, messages=messages or ["Aucune anomalie évidente détectée."])
