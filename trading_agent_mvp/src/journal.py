from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd

from .runtime import utc_now_iso


@dataclass
class DecisionJournal:
    created_at: str
    regime: str
    macro_bias: float
    news_bias: float
    breadth_bias: float
    top_ranked: list[dict[str, Any]]
    proposed_orders: list[dict[str, Any]]
    notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_decision_journal(
    ranked: pd.DataFrame,
    trade_plan: pd.DataFrame,
    regime: str,
    macro_bias: float,
    news_bias: float,
    breadth_bias: float,
) -> DecisionJournal:
    top_ranked = ranked.head(10).to_dict(orient="records") if not ranked.empty else []
    proposed_orders = trade_plan.to_dict(orient="records") if not trade_plan.empty else []
    notes = [
        "Le journal capture les meilleures idées et les ordres proposés au moment de l'analyse.",
        "Il aide à auditer pourquoi le système a voulu agir ou ne pas agir.",
    ]
    return DecisionJournal(
        created_at=utc_now_iso(),
        regime=regime,
        macro_bias=round(float(macro_bias), 4),
        news_bias=round(float(news_bias), 4),
        breadth_bias=round(float(breadth_bias), 4),
        top_ranked=top_ranked,
        proposed_orders=proposed_orders,
        notes=notes,
    )
