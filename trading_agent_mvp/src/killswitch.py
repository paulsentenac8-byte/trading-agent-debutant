from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd

from .config import KillSwitchConfig


@dataclass
class KillSwitchSummary:
    blocked: bool
    severity: str
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def apply_kill_switch(
    trade_plan: pd.DataFrame,
    config: KillSwitchConfig,
    validation_summary: dict[str, Any],
    meta_risk_summary: dict[str, Any],
    monte_carlo_summary: dict[str, Any],
    stress_summary: dict[str, Any],
) -> tuple[pd.DataFrame, KillSwitchSummary]:
    reasons: list[str] = []
    blocked = False
    severity = "none"

    health_score = int(validation_summary.get("health_score", 100))
    if health_score < config.min_health_score:
        blocked = True
        severity = "high"
        reasons.append("Health score sous le seuil du kill switch.")

    meta_confidence = int(meta_risk_summary.get("confidence_score", 100))
    if meta_confidence < config.min_meta_confidence:
        blocked = True
        severity = "high"
        reasons.append("Confiance meta-risk sous le seuil minimal.")

    prob_negative = float(monte_carlo_summary.get("prob_negative_return", 0.0))
    if monte_carlo_summary.get("enabled") and prob_negative > config.max_prob_negative_return:
        blocked = True
        severity = "high"
        reasons.append("Monte Carlo trop défavorable: probabilité de rendement négatif trop élevée.")

    stress_scenarios = stress_summary.get("scenarios", []) if isinstance(stress_summary, dict) else []
    worst_case_pct = 0.0
    for scenario in stress_scenarios:
        worst_case_pct = min(worst_case_pct, float(scenario.get("portfolio_return_pct", 0.0)))
    if abs(worst_case_pct) > config.max_stress_loss_pct:
        blocked = True
        severity = "high"
        reasons.append("Stress test trop sévère au regard du seuil du kill switch.")

    if not trade_plan.empty and len(trade_plan) > config.max_order_count:
        blocked = True
        severity = "medium" if severity == "none" else severity
        reasons.append("Trop d'ordres proposés en même temps.")

    if blocked:
        return pd.DataFrame(columns=trade_plan.columns), KillSwitchSummary(True, severity, reasons)

    return trade_plan, KillSwitchSummary(False, severity, reasons or ["Kill switch non déclenché."])
