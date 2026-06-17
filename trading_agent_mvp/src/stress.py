from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd


@dataclass
class StressSummary:
    portfolio_value: float
    total_risk_amount: float
    scenarios: list[dict[str, Any]]
    notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def run_stress_tests(trade_plan: pd.DataFrame) -> StressSummary:
    if trade_plan.empty:
        return StressSummary(
            portfolio_value=0.0,
            total_risk_amount=0.0,
            scenarios=[],
            notes=["Aucun trade actif proposé, pas de stress test portefeuille."],
        )

    portfolio_value = float((trade_plan["qty"] * trade_plan["close"]).sum())
    total_risk_amount = float(trade_plan.get("risk_amount", pd.Series(dtype=float)).fillna(0).sum())

    shock_scenarios = [
        ("soft_selloff_-3pct", -0.03),
        ("riskoff_-5pct", -0.05),
        ("hard_selloff_-8pct", -0.08),
        ("crash_day_-12pct", -0.12),
    ]

    scenarios: list[dict[str, Any]] = []
    for name, shock in shock_scenarios:
        pnl = float((trade_plan["qty"] * trade_plan["close"] * shock).sum())
        scenarios.append(
            {
                "name": name,
                "portfolio_pnl": round(pnl, 2),
                "portfolio_return_pct": round(shock, 4),
            }
        )

    scenarios.append(
        {
            "name": "gap_to_stop_estimate",
            "portfolio_pnl": round(-total_risk_amount, 2),
            "portfolio_return_pct": round((-total_risk_amount / portfolio_value) if portfolio_value > 0 else 0.0, 4),
        }
    )

    largest_position = trade_plan.sort_values("allocation", ascending=False).iloc[0]
    single_name_pnl = -0.15 * float(largest_position["allocation"])
    scenarios.append(
        {
            "name": f"single_name_gap_-15pct_{largest_position['symbol']}",
            "portfolio_pnl": round(single_name_pnl, 2),
            "portfolio_return_pct": round(single_name_pnl / portfolio_value if portfolio_value > 0 else 0.0, 4),
        }
    )

    return StressSummary(
        portfolio_value=round(portfolio_value, 2),
        total_risk_amount=round(total_risk_amount, 2),
        scenarios=scenarios,
        notes=[
            "Ces scénarios sont des stress tests simples, pas des prévisions.",
            "Ils servent à estimer la vulnérabilité instantanée du portefeuille proposé.",
        ],
    )
