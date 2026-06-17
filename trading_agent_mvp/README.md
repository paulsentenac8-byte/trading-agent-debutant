# Trading Agent — quant pro v4 / production-grade retail

Base de trading orientée actions / ETF avec :
- score multi-stratégies,
- classification de régimes plus fine,
- breadth de marché,
- filtres macro / news / earnings,
- diversification par corrélation et secteur,
- caps d'allocation,
- contrôles pré-trade,
- meta-risk overlay,
- kill switch,
- stress tests,
- Monte Carlo,
- walk-forward analysis,
- sensibilité des paramètres,
- attribution facteurs,
- diagnostics de performance vs benchmark,
- qualité de données,
- mémoire / historique SQLite,
- journal de décision,
- audit manifest,
- santé broker / monitoring,
- interface web Streamlit,
- flux broker à validation humaine.

## Fichiers principaux
- `app.py` : entrée web
- `main.py` : pipeline quant principal
- `interface_debutant.py` : interface utilisateur
- `doctor.py` : diagnostic
- `submit_ibkr_orders.py` : préparation / soumission broker
- `render.yaml` : déploiement Render

## Modules quant principaux
- `src/signals.py`
- `src/features.py`
- `src/breadth.py`
- `src/portfolio.py`
- `src/sector.py`
- `src/pretrade.py`
- `src/metarisk.py`
- `src/killswitch.py`
- `src/stress.py`
- `src/monte_carlo.py`
- `src/walkforward.py`
- `src/sensitivity.py`
- `src/analytics.py`
- `src/attribution.py`
- `src/data_quality.py`
- `src/journal.py`
- `src/audit.py`
- `src/broker_health.py`
- `src/monitoring.py`
- `src/validation.py`

## Rapports produits
- `reports/ranked_signals.csv`
- `reports/orders_to_review.csv`
- `data/trading_agent.sqlite`
- `reports/risk_summary.json`
- `reports/exposure_summary.json`
- `reports/pretrade_summary.json`
- `reports/meta_risk_summary.json`
- `reports/kill_switch_summary.json`
- `reports/stress_test_summary.json`
- `reports/monte_carlo_summary.json`
- `reports/walkforward_summary.json`
- `reports/walkforward_windows.csv`
- `reports/sensitivity_summary.json`
- `reports/sensitivity_grid.csv`
- `reports/attribution_summary.json`
- `reports/performance_diagnostics.json`
- `reports/validation_summary.json`
- `reports/data_quality_summary.json`
- `reports/decision_journal.json`
- `reports/broker_health_summary.json`
- `reports/monitoring_summary.json`
- `reports/audit_manifest.json`
- `reports/breadth_context.json`
- `reports/pipeline_status.json`

## Important
Le projet est maintenant une **base quant retail très avancée et orientée production-grade**, mais pas un desk institutionnel complet et pas une garantie de gains.
