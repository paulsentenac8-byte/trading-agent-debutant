from __future__ import annotations

import hashlib
import platform
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .runtime import hostname, utc_now_iso


@dataclass
class AuditManifest:
    generated_at: str
    host: str
    python_version: str
    platform: str
    config_sha256: str
    artifact_inventory: dict[str, bool]
    notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def sha256_file(path: str | Path) -> str:
    p = Path(path)
    if not p.exists():
        return "missing"
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def build_audit_manifest(config_path: str | Path, artifact_paths: list[str | Path]) -> AuditManifest:
    inventory: dict[str, bool] = {}
    for artifact in artifact_paths:
        p = Path(artifact)
        inventory[p.name] = p.exists() and p.stat().st_size >= 0

    return AuditManifest(
        generated_at=utc_now_iso(),
        host=hostname(),
        python_version=platform.python_version(),
        platform=platform.platform(),
        config_sha256=sha256_file(config_path),
        artifact_inventory=inventory,
        notes=[
            "Le manifest d'audit aide à tracer ce qui a été généré et avec quelle configuration.",
            "Le hash du fichier de config permet de relier une exécution à un set de paramètres précis.",
        ],
    )
