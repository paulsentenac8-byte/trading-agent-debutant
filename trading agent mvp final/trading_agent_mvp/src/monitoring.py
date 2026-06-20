from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class MonitoringSummary:
    status: str
    alert_level: str
    messages: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_monitoring_summary(
    validation_summary: dict[str, Any],
    meta_risk_summary: dict[str, Any],
    kill_switch_summary: dict[str, Any],
    broker_health_summary: dict[str, Any],
) -> MonitoringSummary:
    messages: list[str] = []
    alert_level = "info"
    status = "ok"

    if validation_summary.get("status") == "error":
        status = "degraded"
        alert_level = "warning"
        messages.append("Validation en erreur: prudence élevée.")
    elif validation_summary.get("status") == "warning":
        messages.append("Validation avec avertissements.")

    if int(meta_risk_summary.get("confidence_score", 100)) < 60:
        status = "degraded"
        alert_level = "warning"
        messages.append("Confiance meta-risk faible.")

    if kill_switch_summary.get("blocked"):
        status = "blocked"
        alert_level = "critical"
        messages.append("Kill switch activé: nouveaux ordres bloqués.")

    if not broker_health_summary.get("reachable", False):
        messages.append("Broker non accessible actuellement.")
        if alert_level == "info":
            alert_level = "warning"

    if not messages:
        messages.append("Monitoring nominal.")

    return MonitoringSummary(status=status, alert_level=alert_level, messages=messages)
