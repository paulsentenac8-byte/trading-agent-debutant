from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd

from .config import MetaRiskConfig


@dataclass
class MetaRiskSummary:
    allow_trading: bool
    exposure_multiplier: float
    confidence_score: int
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _scale_trade_plan(trade_plan: pd.DataFrame, exposure_multiplier: float) -> pd.DataFrame:
    if trade_plan.empty:
        return trade_plan
    out = trade_plan.copy()
    out["qty"] = (out["qty"] * exposure_multiplier).astype(int)
    out["allocation"] = (out["qty"] * out["close"]).round(2)
    out["risk_amount"] = (out["qty"] * (out["close"] - out["stop_loss"])).round(2)
    out = out[out["qty"] > 0].copy().reset_index(drop=True)
    return out


def apply_meta_risk_overlays(
    trade_plan: pd.DataFrame,
    config: MetaRiskConfig,
    regime: str,
    breadth_bias: float,
    validation_summary: dict[str, Any],
    stress_summary: dict[str, Any],
    walkforward_summary: dict[str, Any] | None,
) -> tuple[pd.DataFrame, MetaRiskSummary]:
    if trade_plan.empty:
        return trade_plan, MetaRiskSummary(False, 0.0, 0, ["Aucun trade à gérer au niveau méta-risque."])

    reasons: list[str] = []
    exposure_multiplier = 1.0
    confidence_score = 100
    regime = (regime or "neutral").lower()

    health_score = int(validation_summary.get("health_score", 100))
    if health_score < config.min_health_score:
        exposure_multiplier *= 0.6
        confidence_score -= 20
        reasons.append("Health score faible: réduction de l'exposition.")

    if breadth_bias <= config.hard_block_breadth_threshold:
        return pd.DataFrame(columns=trade_plan.columns), MetaRiskSummary(False, 0.0, 0, ["Breadth trop négative: blocage complet des nouveaux trades."])
    if breadth_bias < 0:
        exposure_multiplier *= 0.8
        confidence_score -= 10
        reasons.append("Breadth négative: exposition réduite.")

    if regime in {"riskoff", "crash"}:
        return pd.DataFrame(columns=trade_plan.columns), MetaRiskSummary(False, 0.0, 0, [f"Régime {regime}: blocage complet des nouveaux trades."])
    if regime in {"bear", "correction"}:
        exposure_multiplier *= 0.6
        confidence_score -= 15
        reasons.append(f"Régime {regime}: exposition réduite.")
    elif regime == "bull_volatile":
        exposure_multiplier *= 0.85
        confidence_score -= 5
        reasons.append("Bull volatile: légère réduction de l'exposition.")

    if walkforward_summary:
        windows_tested = int(walkforward_summary.get("windows_tested", 0))
        mean_oos_sharpe = float(walkforward_summary.get("mean_oos_sharpe", 0.0))
        if windows_tested < config.min_walkforward_windows:
            exposure_multiplier *= 0.85
            confidence_score -= 10
            reasons.append("Walk-forward encore limité: exposition réduite.")
        if mean_oos_sharpe < config.min_walkforward_mean_sharpe:
            exposure_multiplier *= 0.7
            confidence_score -= 15
            reasons.append("Walk-forward faible: forte réduction de l'exposition.")

    scenarios = stress_summary.get("scenarios", []) if isinstance(stress_summary, dict) else []
    worst_loss_pct = 0.0
    for scenario in scenarios:
        worst_loss_pct = min(worst_loss_pct, float(scenario.get("portfolio_return_pct", 0.0)))
    if abs(worst_loss_pct) > config.max_stress_loss_pct:
        exposure_multiplier *= 0.7
        confidence_score -= 15
        reasons.append("Stress tests sévères: exposition réduite.")

    exposure_multiplier = max(min(exposure_multiplier, 1.0), 0.0)
    confidence_score = max(min(confidence_score, 100), 0)

    if exposure_multiplier < 0.2:
        return pd.DataFrame(columns=trade_plan.columns), MetaRiskSummary(False, 0.0, confidence_score, reasons + ["Exposition finale trop faible: aucun nouveau trade autorisé."])

    adjusted = _scale_trade_plan(trade_plan, exposure_multiplier)
    return adjusted, MetaRiskSummary(True, round(exposure_multiplier, 4), confidence_score, reasons or ["Aucun ajustement méta-risque significatif."])
