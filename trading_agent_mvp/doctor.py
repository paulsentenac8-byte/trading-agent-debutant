from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "config.json"
REPORTS = ROOT / "reports"

REQUIRED_IMPORTS = [
    "pandas",
    "numpy",
    "streamlit",
    "yfinance",
]
OPTIONAL_IMPORTS = [
    "ib_insync",
    "streamlit_autorefresh",
]


def check_python() -> list[str]:
    msgs: list[str] = []
    major, minor = sys.version_info[:2]
    if (major, minor) < (3, 10):
        msgs.append(f"ERREUR: Python trop ancien ({major}.{minor}). Installe Python 3.11 ou 3.12.")
    else:
        msgs.append(f"OK: Python détecté ({major}.{minor}).")
    return msgs


def check_files() -> list[str]:
    msgs: list[str] = []
    needed = [
        ROOT / "interface_debutant.py",
        ROOT / "main.py",
        ROOT / "requirements.txt",
        ROOT / "lancer_assistant.py",
        CONFIG,
    ]
    for path in needed:
        if path.exists():
            msgs.append(f"OK: fichier présent -> {path.name}")
        else:
            msgs.append(f"ERREUR: fichier manquant -> {path.name}")
    return msgs


def check_imports() -> list[str]:
    msgs: list[str] = []
    for name in REQUIRED_IMPORTS:
        try:
            importlib.import_module(name)
            msgs.append(f"OK: bibliothèque installée -> {name}")
        except Exception:
            msgs.append(f"ERREUR: bibliothèque manquante -> {name}")
    for name in OPTIONAL_IMPORTS:
        try:
            importlib.import_module(name)
            msgs.append(f"OK: option disponible -> {name}")
        except Exception:
            msgs.append(f"INFO: option non installée -> {name}")
    return msgs


def check_config() -> list[str]:
    msgs: list[str] = []
    if not CONFIG.exists():
        return ["ERREUR: config.json introuvable."]
    try:
        data = json.loads(CONFIG.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"ERREUR: config.json illisible -> {exc}"]

    benchmark = data.get("benchmark")
    universe = data.get("universe", [])
    if benchmark:
        msgs.append(f"OK: benchmark configuré -> {benchmark}")
    else:
        msgs.append("ERREUR: benchmark absent dans config.json")

    if universe and isinstance(universe, list):
        msgs.append(f"OK: univers configuré -> {len(universe)} symboles")
    else:
        msgs.append("ERREUR: univers vide ou invalide dans config.json")

    paper_only = data.get("broker", {}).get("paper_only", True)
    msgs.append(f"INFO: mode broker actuel -> {'démo' if paper_only else 'réel'}")
    return msgs


def check_reports_dir() -> list[str]:
    msgs: list[str] = []
    try:
        REPORTS.mkdir(parents=True, exist_ok=True)
        test_file = REPORTS / ".write_test"
        test_file.write_text("ok", encoding="utf-8")
        test_file.unlink(missing_ok=True)
        msgs.append("OK: dossier reports accessible en écriture")
    except Exception as exc:
        msgs.append(f"ERREUR: impossible d'écrire dans reports -> {exc}")
    return msgs


def main() -> int:
    print("=== DIAGNOSTIC ASSISTANT TRADING ===")
    checks = [check_python, check_files, check_imports, check_config, check_reports_dir]
    messages: list[str] = []
    for check in checks:
        messages.extend(check())

    errors = [m for m in messages if m.startswith("ERREUR")]
    for msg in messages:
        print(msg)

    print("=== FIN DU DIAGNOSTIC ===")
    if errors:
        print(f"Diagnostic terminé avec {len(errors)} erreur(s).")
        return 1

    print("Diagnostic OK. Tu peux lancer l'interface.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
