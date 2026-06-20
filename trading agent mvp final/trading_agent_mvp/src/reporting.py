from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


def ensure_report_dir(path: str) -> Path:
    report_dir = Path(path)
    report_dir.mkdir(parents=True, exist_ok=True)
    return report_dir


def save_ranked_signals(ranked: pd.DataFrame, report_dir: str) -> Path:
    path = ensure_report_dir(report_dir) / "ranked_signals.csv"
    ranked.to_csv(path, index=False)
    return path


def save_backtest_stats(stats: dict[str, Any], report_dir: str) -> Path:
    path = ensure_report_dir(report_dir) / "backtest_stats.json"
    path.write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def save_json_artifact(name: str, payload: dict[str, Any], report_dir: str) -> Path:
    path = ensure_report_dir(report_dir) / name
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def save_dataframe_artifact(name: str, df: pd.DataFrame, report_dir: str) -> Path:
    path = ensure_report_dir(report_dir) / name
    df.to_csv(path, index=False)
    return path


def save_report(
    report_dir: str,
    benchmark: str,
    regime: str,
    context_summary: str,
    eligible_symbols: list[str],
    ranked: pd.DataFrame,
    trade_plan: pd.DataFrame,
    backtest_stats: dict[str, Any],
    macro_context: dict[str, Any],
    news_summary: pd.DataFrame,
    earnings_calendar: pd.DataFrame,
    breadth_context: dict[str, Any],
    validation_summary: dict[str, Any],
    risk_summary: dict[str, Any],
    stress_summary: dict[str, Any],
    walkforward_summary: dict[str, Any],
    monte_carlo_summary: dict[str, Any],
    attribution_summary: dict[str, Any],
    pretrade_summary: dict[str, Any],
    meta_risk_summary: dict[str, Any],
    kill_switch_summary: dict[str, Any],
    performance_diagnostics: dict[str, Any],
    sensitivity_summary: dict[str, Any],
    broker_health_summary: dict[str, Any],
    monitoring_summary: dict[str, Any],
    data_quality_summary: dict[str, Any],
    exposure_summary: dict[str, Any],
    decision_journal: dict[str, Any],
    audit_manifest: dict[str, Any],
    readiness_summary: dict[str, Any],
    anomaly_summary: dict[str, Any],
    regression_checklist: dict[str, Any],
) -> Path:
    report_dir_path = ensure_report_dir(report_dir)
    path = report_dir_path / "latest_report.md"

    top_ranked_md = ranked.head(10).to_markdown(index=False) if not ranked.empty else "Aucun signal."
    trade_plan_md = trade_plan.to_markdown(index=False) if not trade_plan.empty else "Aucun ordre proposé."
    news_md = news_summary.head(12).to_markdown(index=False) if not news_summary.empty else "Aucune news exploitable."
    earnings_md = earnings_calendar.head(12).to_markdown(index=False) if not earnings_calendar.empty else "Aucun earnings proche."
    macro_summary = "\n".join(f"- {item}" for item in macro_context.get("summary", [])) or "- Contexte macro indisponible."
    breadth_summary = "\n".join(f"- {item}" for item in breadth_context.get("summary", [])) or "- Breadth indisponible."
    validation_warnings = "\n".join(f"- {item}" for item in validation_summary.get("warnings", [])) or "- Aucun avertissement majeur."
    validation_errors = "\n".join(f"- {item}" for item in validation_summary.get("errors", [])) or "- Aucune erreur critique."

    content = f"""# Rapport Trading Agent — Quant Pro

## Résumé
- Benchmark: `{benchmark}`
- Régime détecté: `{regime}`
- Contexte: {context_summary}
- Nombre de symboles éligibles: **{len(eligible_symbols)}**

## Macro
- Bias macro calculé: **{macro_context.get('bias', 0.0):+.2f}**
- As of: `{macro_context.get('as_of', 'n/a')}`
{macro_summary}

## Breadth de marché
- Bias breadth calculé: **{breadth_context.get('breadth_bias', 0.0):+.2f}**
- % au-dessus SMA50: **{breadth_context.get('pct_above_sma50', 0.0):.2%}**
- % au-dessus SMA200: **{breadth_context.get('pct_above_sma200', 0.0):.2%}**
{breadth_summary}

## Qualité des données
```json
{json.dumps(data_quality_summary, indent=2, ensure_ascii=False)}
```

## Validation / santé du système
- Statut: **{validation_summary.get('status', 'unknown')}**
- Health score: **{validation_summary.get('health_score', 0)}/100**
### Warnings
{validation_warnings}
### Erreurs
{validation_errors}

## Readiness
```json
{json.dumps(readiness_summary, indent=2, ensure_ascii=False)}
```

## Pré-trade risk controls
```json
{json.dumps(pretrade_summary, indent=2, ensure_ascii=False)}
```

## Meta-risk overlay
```json
{json.dumps(meta_risk_summary, indent=2, ensure_ascii=False)}
```

## Kill switch
```json
{json.dumps(kill_switch_summary, indent=2, ensure_ascii=False)}
```

## Diagnostics de performance
```json
{json.dumps(performance_diagnostics, indent=2, ensure_ascii=False)}
```

## Sensibilité des paramètres
```json
{json.dumps(sensitivity_summary, indent=2, ensure_ascii=False)}
```

## Santé broker
```json
{json.dumps(broker_health_summary, indent=2, ensure_ascii=False)}
```

## Monitoring
```json
{json.dumps(monitoring_summary, indent=2, ensure_ascii=False)}
```

## Exposition portefeuille
```json
{json.dumps(exposure_summary, indent=2, ensure_ascii=False)}
```

## Anomalies
```json
{json.dumps(anomaly_summary, indent=2, ensure_ascii=False)}
```

## Top signaux
{top_ranked_md}

## News / sentiment
{news_md}

## Earnings proches
{earnings_md}

## Ordres proposés à valider
{trade_plan_md}

## Attribution facteurs
```json
{json.dumps(attribution_summary, indent=2, ensure_ascii=False)}
```

## Journal de décision
```json
{json.dumps(decision_journal, indent=2, ensure_ascii=False)}
```

## Résumé risque portefeuille
```json
{json.dumps(risk_summary, indent=2, ensure_ascii=False)}
```

## Stress tests portefeuille
```json
{json.dumps(stress_summary, indent=2, ensure_ascii=False)}
```

## Walk-forward
```json
{json.dumps(walkforward_summary, indent=2, ensure_ascii=False)}
```

## Monte Carlo
```json
{json.dumps(monte_carlo_summary, indent=2, ensure_ascii=False)}
```

## Statistiques backtest
```json
{json.dumps(backtest_stats, indent=2, ensure_ascii=False)}
```

## Audit manifest
```json
{json.dumps(audit_manifest, indent=2, ensure_ascii=False)}
```

## Regression checklist
```json
{json.dumps(regression_checklist, indent=2, ensure_ascii=False)}
```

## Rappel
Ce rapport sert à la **recherche, la validation quant et au paper trading**. Les ordres générés doivent être **validés humainement** avant toute exécution réelle.
"""
    path.write_text(content, encoding="utf-8")
    return path
