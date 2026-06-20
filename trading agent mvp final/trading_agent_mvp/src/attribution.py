from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd


@dataclass
class AttributionSummary:
    n_positions: int
    weighted_factor_exposure: dict[str, float]
    top_symbols: list[dict[str, Any]]
    notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_attribution_summary(trade_plan: pd.DataFrame) -> AttributionSummary:
    if trade_plan.empty:
        return AttributionSummary(0, {}, [], ["Aucune position sélectionnée, pas d'attribution facteur."])

    weights = trade_plan["allocation"] / trade_plan["allocation"].sum() if trade_plan["allocation"].sum() > 0 else 0
    factors = [
        "trend_component",
        "momentum_component",
        "breakout_component",
        "pullback_component",
        "quality_component",
        "macro_bias",
        "breadth_bias",
        "symbol_news_bias",
        "event_bias",
    ]

    weighted_factor_exposure: dict[str, float] = {}
    for factor in factors:
        if factor in trade_plan.columns:
            weighted_factor_exposure[factor] = round(float((trade_plan[factor] * weights).sum()), 4)

    top_symbols = (
        trade_plan.sort_values("allocation", ascending=False)[["symbol", "score", "allocation", "sector"]]
        .head(5)
        .to_dict(orient="records")
        if "sector" in trade_plan.columns
        else trade_plan.sort_values("allocation", ascending=False)[["symbol", "score", "allocation"]].head(5).to_dict(orient="records")
    )

    return AttributionSummary(
        n_positions=int(len(trade_plan)),
        weighted_factor_exposure=weighted_factor_exposure,
        top_symbols=top_symbols,
        notes=[
            "L'attribution indique quels facteurs portent le portefeuille proposé.",
            "Elle aide à détecter si le portefeuille est surtout trend, momentum ou trop dépendant d'un contexte macro.",
        ],
    )
