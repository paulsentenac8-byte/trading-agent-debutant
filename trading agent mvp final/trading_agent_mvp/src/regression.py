from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class RegressionChecklist:
    checks: dict[str, bool]
    status: str
    notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_regression_checklist(artifacts: dict[str, bool]) -> RegressionChecklist:
    required = {
        "pipeline_status": artifacts.get("pipeline_status", False),
        "ranked_signals": artifacts.get("ranked_signals", False),
        "risk_summary": artifacts.get("risk_summary", False),
        "stress_test_summary": artifacts.get("stress_test_summary", False),
        "walkforward_summary": artifacts.get("walkforward_summary", False),
        "monitoring_summary": artifacts.get("monitoring_summary", False),
        "audit_manifest": artifacts.get("audit_manifest", False),
    }
    status = "ok" if all(required.values()) else "warning"
    notes = [
        "Cette checklist vérifie que les artefacts essentiels du pipeline ont bien été générés.",
        "Elle sert de garde-fou simple contre une exécution partielle ou cassée.",
    ]
    return RegressionChecklist(checks=required, status=status, notes=notes)
