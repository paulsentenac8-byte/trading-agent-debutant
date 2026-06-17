from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .config import ValidationConfig


@dataclass
class ValidationSummary:
    status: str
    warnings: list[str]
    errors: list[str]
    health_score: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_validation_summary(
    config: ValidationConfig,
    initial_universe_count: int,
    eligible_count: int,
    ranked_count: int,
    macro_error_count: int,
    news_error_count: int,
    earnings_error_count: int,
    trade_count: int,
) -> ValidationSummary:
    warnings: list[str] = []
    errors: list[str] = []
    health_score = 100

    if eligible_count < config.min_eligible_symbols:
        warnings.append("Univers éligible réduit: peu de titres liquides ont passé le filtre.")
        health_score -= 10

    if ranked_count < config.min_ranked_symbols:
        warnings.append("Peu de signaux classés: le marché est peut-être peu favorable ou les données sont incomplètes.")
        health_score -= 10

    total_external_errors = macro_error_count + news_error_count + earnings_error_count
    if total_external_errors > 0:
        warnings.append(f"Certaines sources externes ont échoué ({total_external_errors} erreur(s)).")
        health_score -= min(total_external_errors * 3, 20)

    if total_external_errors >= config.max_data_error_count:
        errors.append("Trop d'erreurs de données externes: prudence élevée sur l'analyse du jour.")
        health_score -= 25

    if trade_count == 0:
        warnings.append("Aucun trade proposé: ce n'est pas forcément mauvais, cela peut refléter un filtre prudent.")
        health_score -= 5

    if initial_universe_count <= 0:
        errors.append("Univers initial vide.")
        health_score = 0

    status = "ok"
    if errors:
        status = "error"
    elif warnings:
        status = "warning"

    health_score = max(min(health_score, 100), 0)
    return ValidationSummary(status=status, warnings=warnings, errors=errors, health_score=health_score)
