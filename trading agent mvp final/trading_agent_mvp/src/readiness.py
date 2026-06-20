from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class ReadinessSummary:
    readiness_score: int
    status: str
    go_live_recommendation: str
    strengths: list[str]
    blockers: list[str]
    notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_readiness_summary(
    validation_summary: dict[str, Any],
    data_quality_summary: dict[str, Any],
    meta_risk_summary: dict[str, Any],
    kill_switch_summary: dict[str, Any],
    performance_diagnostics: dict[str, Any],
    sensitivity_summary: dict[str, Any],
    broker_health_summary: dict[str, Any],
    monte_carlo_summary: dict[str, Any],
) -> ReadinessSummary:
    score = 100
    strengths: list[str] = []
    blockers: list[str] = []

    health_score = int(validation_summary.get("health_score", 0))
    if health_score >= 80:
        strengths.append("Santé système élevée.")
    else:
        blockers.append("Santé système insuffisante pour une vraie production sereine.")
        score -= 15

    if data_quality_summary.get("status") == "ok":
        strengths.append("Qualité de données correcte.")
    else:
        blockers.append("Qualité de données non optimale.")
        score -= 12

    if int(meta_risk_summary.get("confidence_score", 0)) >= 70:
        strengths.append("Confiance meta-risk correcte.")
    else:
        blockers.append("Confiance meta-risk faible.")
        score -= 10

    if kill_switch_summary.get("blocked"):
        blockers.append("Kill switch activé: système non prêt à prendre du risque.")
        score -= 25
    else:
        strengths.append("Kill switch non déclenché.")

    if broker_health_summary.get("reachable"):
        strengths.append("Broker joignable depuis l'environnement d'exécution.")
    else:
        blockers.append("Broker non joignable actuellement.")
        score -= 8

    info_ratio = float(performance_diagnostics.get("information_ratio", 0.0))
    if info_ratio > 0:
        strengths.append("Information ratio positif.")
    else:
        blockers.append("Information ratio non positif sur l'échantillon observé.")
        score -= 8

    positive_sharpe_ratio = float(sensitivity_summary.get("positive_sharpe_ratio", 0.0))
    if positive_sharpe_ratio >= 0.55:
        strengths.append("Sensibilité paramétrique acceptable.")
    else:
        blockers.append("Stratégie possiblement trop fragile aux paramètres.")
        score -= 8

    prob_negative = float(monte_carlo_summary.get("prob_negative_return", 0.0)) if monte_carlo_summary.get("enabled") else 0.5
    if prob_negative <= 0.45:
        strengths.append("Monte Carlo relativement raisonnable.")
    else:
        blockers.append("Monte Carlo indique une probabilité de perte trop élevée.")
        score -= 10

    score = max(min(score, 100), 0)
    if score >= 85:
        status = "strong"
        go_live = "paper_to_small_live_possible"
    elif score >= 70:
        status = "acceptable"
        go_live = "paper_only_recommended"
    else:
        status = "weak"
        go_live = "do_not_go_live"

    return ReadinessSummary(
        readiness_score=score,
        status=status,
        go_live_recommendation=go_live,
        strengths=strengths,
        blockers=blockers,
        notes=[
            "Le readiness score ne remplace pas un jugement professionnel ou un test long en paper trading.",
            "Un bon score signifie seulement que le système est mieux structuré, pas qu'il sera rentable.",
        ],
    )
