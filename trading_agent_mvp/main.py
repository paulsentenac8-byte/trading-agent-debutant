from __future__ import annotations

import argparse
import traceback
from pathlib import Path
from typing import Any

import pandas as pd

from src.attribution import build_attribution_summary
from src.audit import build_audit_manifest
from src.anomaly import detect_anomalies
from src.backtest import run_rotation_backtest
from src.breadth import build_breadth_context
from src.broker import BrokerOrder, IBKRManualApprovalBroker, ManualApprovalBroker
from src.broker_health import check_broker_health
from src.config import load_config
from src.data import download_ohlcv, filter_liquid_universe
from src.data_quality import build_data_quality_summary
from src.earnings import build_earnings_context
from src.features import add_features, latest_snapshot
from src.macro import build_macro_context
from src.analytics import build_performance_diagnostics
from src.exposure import build_exposure_summary
from src.journal import build_decision_journal
from src.killswitch import apply_kill_switch
from src.metarisk import MetaRiskSummary, apply_meta_risk_overlays
from src.monte_carlo import run_monte_carlo_analysis
from src.monitoring import build_monitoring_summary
from src.news import build_news_context
from src.regression import build_regression_checklist
from src.portfolio import apply_allocation_caps, can_take_long_risk, diversify_trade_plan
from src.pretrade import PreTradeSummary, apply_pretrade_controls
from src.readiness import build_readiness_summary
from src.reporting import (
    save_backtest_stats,
    save_dataframe_artifact,
    save_json_artifact,
    save_ranked_signals,
    save_report,
)
from src.risk import build_trade_plan
from src.runtime import exclusive_lock, utc_now_iso
from src.scalars import to_float, to_int
from src.sector import apply_sector_limits
from src.signals import MarketContext, infer_market_regime, rank_universe
from src.sensitivity import run_sensitivity_analysis
from src.storage import load_history_summary, store_pipeline_run
from src.stress import run_stress_tests
from src.validation import build_validation_summary
from src.walkforward import WalkForwardSummary, run_walkforward_analysis


RANKED_COLUMNS = [
    "symbol",
    "date",
    "score",
    "close",
    "rsi_14",
    "vol_20",
    "mom_20",
    "mom_60",
    "rel_strength_20",
    "atr_14",
    "avg_dollar_volume_20",
    "market_news_bias",
    "symbol_news_bias",
    "event_bias",
    "macro_bias",
    "breadth_bias",
    "trend_component",
    "momentum_component",
    "breakout_component",
    "pullback_component",
    "quality_component",
    "reasons",
]

ORDER_COLUMNS = [
    "symbol",
    "side",
    "qty",
    "order_type",
    "reference_price",
    "stop_loss",
    "take_profit",
    "rationale",
    "tif",
    "approved",
    "limit_price",
    "broker_status",
    "review_comment",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Trading Agent MVP")
    parser.add_argument("--config", default="config.json", help="Chemin vers le fichier de config JSON")
    return parser.parse_args()


def empty_ranked_df() -> pd.DataFrame:
    return pd.DataFrame(columns=RANKED_COLUMNS)


def empty_orders_df() -> pd.DataFrame:
    return pd.DataFrame(columns=ORDER_COLUMNS)


def summarize_risk(trade_plan: pd.DataFrame, capital: float, max_positions: int, risk_per_trade: float) -> dict[str, Any]:
    if trade_plan.empty:
        return {
            "n_orders": 0,
            "capital": round(float(capital), 2),
            "risk_per_trade": round(float(risk_per_trade), 4),
            "max_positions": int(max_positions),
            "estimated_total_allocation": 0.0,
            "estimated_cash_remaining": round(float(capital), 2),
            "estimated_total_risk_amount": 0.0,
            "average_stop_pct": 0.0,
            "notes": ["Aucun ordre proposé actuellement."],
        }

    total_allocation = float(trade_plan.get("allocation", pd.Series(dtype=float)).fillna(0).sum())
    average_stop_pct = float(trade_plan.get("stop_pct", pd.Series(dtype=float)).fillna(0).mean())
    total_risk_amount = float(trade_plan.get("risk_amount", pd.Series(dtype=float)).fillna(0).sum())
    cash_remaining = max(float(capital) - total_allocation, 0.0)

    return {
        "n_orders": int(len(trade_plan)),
        "capital": round(float(capital), 2),
        "risk_per_trade": round(float(risk_per_trade), 4),
        "max_positions": int(max_positions),
        "estimated_total_allocation": round(total_allocation, 2),
        "estimated_cash_remaining": round(cash_remaining, 2),
        "estimated_total_risk_amount": round(total_risk_amount, 2),
        "average_stop_pct": round(average_stop_pct, 4),
        "notes": [
            "Le montant de risque estimé dépend du prix d'exécution réel et des écarts de marché.",
            "Le système reste configuré pour attendre une validation humaine avant envoi broker.",
        ],
    }


def build_action_center(
    ranked: pd.DataFrame,
    trade_plan: pd.DataFrame,
    regime: str,
    macro_bias: float,
    market_news_bias: float,
    breadth_bias: float,
    paper_only: bool,
    validation_summary: dict[str, Any],
    meta_risk_summary: dict[str, Any],
    kill_switch_summary: dict[str, Any],
    readiness_summary: dict[str, Any],
) -> dict[str, Any]:
    warnings = (
        list(validation_summary.get("warnings", []))
        + list(meta_risk_summary.get("reasons", []))
        + list(kill_switch_summary.get("reasons", []))
        + list(readiness_summary.get("blockers", []))
    )
    if ranked.empty:
        return {
            "status": "no_analysis",
            "headline": "Aucune opportunité exploitable pour le moment.",
            "next_step": "Relancer l'analyse plus tard ou élargir l'univers.",
            "regime": regime,
            "paper_only": paper_only,
            "macro_bias": round(float(macro_bias), 4),
            "market_news_bias": round(float(market_news_bias), 4),
            "breadth_bias": round(float(breadth_bias), 4),
            "warnings": warnings,
            "top_symbols": [],
        }

    top_symbols = ranked.head(3)[["symbol", "score", "close"]].to_dict(orient="records")

    if trade_plan.empty:
        return {
            "status": "analysis_ready_no_orders",
            "headline": "Analyse terminée mais aucun trade n'a passé les filtres finaux.",
            "next_step": "Lire le rapport et attendre un meilleur contexte de marché.",
            "regime": regime,
            "paper_only": paper_only,
            "macro_bias": round(float(macro_bias), 4),
            "market_news_bias": round(float(market_news_bias), 4),
            "breadth_bias": round(float(breadth_bias), 4),
            "warnings": warnings,
            "top_symbols": top_symbols,
        }

    return {
        "status": "orders_ready",
        "headline": f"{len(trade_plan)} trade(s) sont prêts à être revus.",
        "next_step": "Va dans l'onglet d'autorisation, coche les trades voulus, puis envoie au broker démo.",
        "regime": regime,
        "paper_only": paper_only,
        "macro_bias": round(float(macro_bias), 4),
        "market_news_bias": round(float(market_news_bias), 4),
        "breadth_bias": round(float(breadth_bias), 4),
        "warnings": warnings,
        "top_symbols": top_symbols,
    }


def _default_walkforward_summary() -> WalkForwardSummary:
    return WalkForwardSummary(False, 0, {}, 0.0, 0.0, 0.0, ["Walk-forward désactivé."])


def _default_meta_summary(reason: str = "Meta-risk non appliqué.") -> MetaRiskSummary:
    return MetaRiskSummary(True, 1.0, 100, [reason])


def _save_empty_or_df(name: str, df: pd.DataFrame, report_dir: str) -> None:
    if df.empty:
        pd.DataFrame().to_csv(Path(report_dir) / name, index=False)
    else:
        save_dataframe_artifact(name, df, report_dir)


def run_pipeline(config_path: str) -> None:
    config = load_config(config_path)
    report_dir = Path(config.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    lock_path = report_dir / "pipeline.lock"

    with exclusive_lock(lock_path) as acquired:
        if not acquired:
            save_json_artifact(
                "pipeline_status.json",
                {
                    "state": "busy",
                    "message": "Une autre analyse est déjà en cours.",
                    "updated_at": utc_now_iso(),
                    "report_dir": str(report_dir),
                },
                str(report_dir),
            )
            print("Une autre analyse est déjà en cours.")
            return

        save_json_artifact(
            "pipeline_status.json",
            {
                "state": "running",
                "message": "Analyse en cours.",
                "started_at": utc_now_iso(),
                "report_dir": str(report_dir),
            },
            str(report_dir),
        )

        try:
            symbols = list(dict.fromkeys(config.universe + [config.benchmark]))
            market_data = download_ohlcv(symbols, start_date=config.start_date)
            if config.benchmark not in market_data:
                raise RuntimeError(f"Benchmark introuvable dans les données: {config.benchmark}")

            eligible_symbols = filter_liquid_universe(
                market_data,
                min_price=config.min_price,
                min_avg_dollar_volume=config.min_avg_dollar_volume,
            )
            data_quality_summary = build_data_quality_summary(
                requested_symbols=symbols,
                market_data=market_data,
                eligible_symbols=eligible_symbols,
                benchmark_symbol=config.benchmark,
                min_history_bars=config.data_quality.min_history_bars,
                max_stale_days=config.data_quality.max_stale_days,
                min_coverage_ratio=config.data_quality.min_coverage_ratio,
            )
            eligible_data = {s: market_data[s] for s in eligible_symbols if s in market_data}
            eligible_data[config.benchmark] = market_data[config.benchmark]

            macro_context = build_macro_context(config.macro)
            news_symbols = list(dict.fromkeys(eligible_symbols + [config.benchmark] + config.news.market_symbols))
            news_context = build_news_context(news_symbols, config.news, config.benchmark)
            earnings_context = build_earnings_context(eligible_symbols, config.earnings)

            benchmark_features = add_features(market_data[config.benchmark])
            regime = infer_market_regime(benchmark_features, config.regime_override)

            feature_map: dict[str, pd.DataFrame] = {}
            snapshots: dict[str, dict] = {}
            for symbol in eligible_symbols:
                feats = add_features(market_data[symbol], market_data[config.benchmark])
                if feats.empty:
                    continue
                feature_map[symbol] = feats
                snapshots[symbol] = latest_snapshot(feats)

            breadth_context = build_breadth_context(snapshots)
            effective_breadth_bias = breadth_context.breadth_bias if config.strategy.use_breadth_filter else 0.0

            context = MarketContext(
                macro_bias=config.macro_bias + macro_context.bias,
                news_bias=config.news_bias + news_context.market_bias,
                breadth_bias=effective_breadth_bias,
                regime=regime,
                symbol_news_bias=news_context.symbol_bias,
                symbol_event_bias=earnings_context.symbol_penalty,
            )

            ranked = rank_universe(snapshots, context)

            if not can_take_long_risk(
                regime=regime,
                breadth_bias=effective_breadth_bias,
                allow_long_only_in_bear=config.strategy.allow_long_only_in_bear,
                breadth_risk_off_threshold=config.strategy.breadth_risk_off_threshold,
                rebalance_to_cash_in_bear=config.portfolio.rebalance_to_cash_in_bear,
            ):
                trade_plan = pd.DataFrame(columns=ranked.columns)
                pretrade_summary = PreTradeSummary(0, 0, 0.0, ["Régime / breadth trop défavorable pour prendre du risque long."])
            else:
                trade_plan = build_trade_plan(
                    ranked=ranked,
                    capital=config.initial_capital,
                    max_positions=config.max_positions,
                    risk_per_trade=config.risk_per_trade,
                    max_position_weight=config.max_position_weight,
                    min_score=config.strategy.min_score,
                )
                trade_plan = diversify_trade_plan(
                    trade_plan=trade_plan,
                    feature_map=feature_map,
                    capital=config.initial_capital,
                    max_positions=config.max_positions,
                    max_pairwise_correlation=config.portfolio.max_pairwise_correlation,
                    min_cash_buffer=config.portfolio.min_cash_buffer,
                )
                trade_plan = apply_sector_limits(
                    trade_plan=trade_plan,
                    max_sector_positions=config.portfolio.max_sector_positions,
                ).head(config.max_positions)
                trade_plan = apply_allocation_caps(
                    trade_plan=trade_plan,
                    capital=config.initial_capital,
                    max_sector_allocation_pct=config.portfolio.max_sector_allocation_pct,
                    max_gross_exposure_pct=config.portfolio.max_gross_exposure_pct,
                )
                trade_plan, pretrade_summary = apply_pretrade_controls(
                    trade_plan=trade_plan,
                    capital=config.initial_capital,
                    config=config.pretrade,
                )

            equity_curve, stats = run_rotation_backtest(
                market_data=eligible_data,
                benchmark_symbol=config.benchmark,
                max_positions=config.max_positions,
                rebalance_frequency=config.rebalance_frequency,
                transaction_cost_bps=config.transaction_cost_bps,
                context=MarketContext(
                    macro_bias=config.macro_bias + macro_context.bias,
                    news_bias=config.news_bias + news_context.market_bias,
                    breadth_bias=effective_breadth_bias,
                ),
                regime_override=config.regime_override,
                min_score=config.strategy.min_score,
            )

            if not ranked.empty:
                save_ranked_signals(ranked, str(report_dir))
            else:
                empty_ranked_df().to_csv(report_dir / "ranked_signals.csv", index=False)

            save_backtest_stats(stats, str(report_dir))
            save_json_artifact("macro_context.json", macro_context.to_dict(), str(report_dir))
            save_json_artifact("news_context.json", news_context.to_dict(), str(report_dir))
            save_json_artifact("earnings_context.json", earnings_context.to_dict(), str(report_dir))
            save_json_artifact("breadth_context.json", breadth_context.to_dict(), str(report_dir))
            save_json_artifact("data_quality_summary.json", data_quality_summary.to_dict(), str(report_dir))
            save_json_artifact("pretrade_summary.json", pretrade_summary.to_dict(), str(report_dir))

            news_summary_df = pd.DataFrame(news_context.symbol_summary)
            if news_summary_df.empty:
                news_summary_df = pd.DataFrame(columns=["symbol", "articles", "avg_sentiment", "symbol_bias"])

            news_articles_df = pd.DataFrame(news_context.articles)
            if news_articles_df.empty:
                news_articles_df = pd.DataFrame(columns=["symbol", "published_at", "provider", "title", "sentiment", "url"])

            earnings_calendar_df = pd.DataFrame(earnings_context.calendar)
            if earnings_calendar_df.empty:
                earnings_calendar_df = pd.DataFrame(
                    columns=["symbol", "earnings_date", "eps_estimate", "reported_eps", "surprise_pct", "days_to_event"]
                )

            save_dataframe_artifact("news_summary.csv", news_summary_df, str(report_dir))
            save_dataframe_artifact("news_articles.csv", news_articles_df, str(report_dir))
            save_dataframe_artifact("earnings_calendar.csv", earnings_calendar_df, str(report_dir))

            if not equity_curve.empty:
                equity_curve.to_csv(report_dir / "equity_curve.csv", header=["equity"])
            else:
                pd.DataFrame(columns=["equity"]).to_csv(report_dir / "equity_curve.csv", index=False)

            walkforward_summary, walkforward_windows_df = (
                run_walkforward_analysis(
                    market_data=eligible_data,
                    benchmark_symbol=config.benchmark,
                    rebalance_frequency=config.rebalance_frequency,
                    transaction_cost_bps=config.transaction_cost_bps,
                    context=MarketContext(
                        macro_bias=config.macro_bias + macro_context.bias,
                        news_bias=config.news_bias + news_context.market_bias,
                        breadth_bias=effective_breadth_bias,
                    ),
                    regime_override=config.regime_override,
                    strategy_config=config.strategy,
                    max_positions_default=config.max_positions,
                    train_months=config.walkforward.train_months,
                    test_months=config.walkforward.test_months,
                    max_windows=config.walkforward.max_windows,
                )
                if config.walkforward.enabled
                else (_default_walkforward_summary(), pd.DataFrame())
            )
            save_json_artifact("walkforward_summary.json", walkforward_summary.to_dict(), str(report_dir))
            _save_empty_or_df("walkforward_windows.csv", walkforward_windows_df, str(report_dir))

            validation_summary = build_validation_summary(
                config=config.validation,
                initial_universe_count=len(symbols),
                eligible_count=len(eligible_symbols),
                ranked_count=len(ranked),
                macro_error_count=len(macro_context.errors),
                news_error_count=len(news_context.errors),
                earnings_error_count=len(earnings_context.errors),
                trade_count=len(trade_plan),
            )
            for warning in data_quality_summary.warnings:
                if warning not in validation_summary.warnings:
                    validation_summary.warnings.append(warning)
                    validation_summary.health_score = max(validation_summary.health_score - 3, 0)
            if data_quality_summary.status == "error":
                validation_summary.status = "error"
                if "Données de marché insuffisantes au niveau qualité." not in validation_summary.errors:
                    validation_summary.errors.append("Données de marché insuffisantes au niveau qualité.")
            elif validation_summary.status == "ok" and validation_summary.warnings:
                validation_summary.status = "warning"
            save_json_artifact("validation_summary.json", validation_summary.to_dict(), str(report_dir))

            performance_diagnostics = build_performance_diagnostics(equity_curve, market_data[config.benchmark])
            save_json_artifact("performance_diagnostics.json", performance_diagnostics.to_dict(), str(report_dir))

            sensitivity_summary, sensitivity_df = run_sensitivity_analysis(
                market_data=eligible_data,
                benchmark_symbol=config.benchmark,
                rebalance_frequency=config.rebalance_frequency,
                transaction_cost_bps=config.transaction_cost_bps,
                context=MarketContext(
                    macro_bias=config.macro_bias + macro_context.bias,
                    news_bias=config.news_bias + news_context.market_bias,
                    breadth_bias=effective_breadth_bias,
                ),
                regime_override=config.regime_override,
                base_min_score=config.strategy.min_score,
                base_max_positions=config.max_positions,
                config=config.sensitivity,
            )
            save_json_artifact("sensitivity_summary.json", sensitivity_summary.to_dict(), str(report_dir))
            _save_empty_or_df("sensitivity_grid.csv", sensitivity_df, str(report_dir))

            stress_summary_pre = run_stress_tests(trade_plan)

            if config.metarisk.enabled:
                trade_plan, meta_risk_summary = apply_meta_risk_overlays(
                    trade_plan=trade_plan,
                    config=config.metarisk,
                    regime=regime,
                    breadth_bias=effective_breadth_bias,
                    validation_summary=validation_summary.to_dict(),
                    stress_summary=stress_summary_pre.to_dict(),
                    walkforward_summary=walkforward_summary.to_dict(),
                )
            else:
                meta_risk_summary = _default_meta_summary("Meta-risk désactivé dans la configuration.")
            save_json_artifact("meta_risk_summary.json", meta_risk_summary.to_dict(), str(report_dir))

            risk_summary = summarize_risk(
                trade_plan=trade_plan,
                capital=config.initial_capital,
                max_positions=config.max_positions,
                risk_per_trade=config.risk_per_trade,
            )
            stress_summary = run_stress_tests(trade_plan)
            attribution_summary = build_attribution_summary(trade_plan)
            monte_carlo_summary = run_monte_carlo_analysis(equity_curve, config.montecarlo)

            if config.killswitch.enabled:
                trade_plan, kill_switch_summary = apply_kill_switch(
                    trade_plan=trade_plan,
                    config=config.killswitch,
                    validation_summary=validation_summary.to_dict(),
                    meta_risk_summary=meta_risk_summary.to_dict(),
                    monte_carlo_summary=monte_carlo_summary.to_dict(),
                    stress_summary=stress_summary.to_dict(),
                )
            else:
                kill_switch_summary = {"blocked": False, "severity": "none", "reasons": ["Kill switch désactivé."]}

            # Recompute post-kill-switch summaries if needed
            risk_summary = summarize_risk(
                trade_plan=trade_plan,
                capital=config.initial_capital,
                max_positions=config.max_positions,
                risk_per_trade=config.risk_per_trade,
            )
            stress_summary = run_stress_tests(trade_plan)
            attribution_summary = build_attribution_summary(trade_plan)
            exposure_summary = build_exposure_summary(trade_plan, config.initial_capital)
            decision_journal = build_decision_journal(
                ranked=ranked,
                trade_plan=trade_plan,
                regime=regime,
                macro_bias=context.macro_bias,
                news_bias=context.news_bias,
                breadth_bias=context.breadth_bias,
            )
            anomaly_summary = detect_anomalies(ranked, trade_plan)

            save_json_artifact("risk_summary.json", risk_summary, str(report_dir))
            save_json_artifact("stress_test_summary.json", stress_summary.to_dict(), str(report_dir))
            save_json_artifact("attribution_summary.json", attribution_summary.to_dict(), str(report_dir))
            save_json_artifact("exposure_summary.json", exposure_summary.to_dict(), str(report_dir))
            save_json_artifact("decision_journal.json", decision_journal.to_dict(), str(report_dir))
            save_json_artifact("anomaly_summary.json", anomaly_summary.to_dict(), str(report_dir))
            save_json_artifact("monte_carlo_summary.json", monte_carlo_summary.to_dict(), str(report_dir))
            save_json_artifact("kill_switch_summary.json", kill_switch_summary.to_dict() if hasattr(kill_switch_summary, 'to_dict') else kill_switch_summary, str(report_dir))

            broker_health_summary = check_broker_health(config.broker)
            save_json_artifact("broker_health_summary.json", broker_health_summary.to_dict(), str(report_dir))

            monitoring_summary = build_monitoring_summary(
                validation_summary=validation_summary.to_dict(),
                meta_risk_summary=meta_risk_summary.to_dict(),
                kill_switch_summary=kill_switch_summary.to_dict() if hasattr(kill_switch_summary, 'to_dict') else kill_switch_summary,
                broker_health_summary=broker_health_summary.to_dict(),
            )
            save_json_artifact("monitoring_summary.json", monitoring_summary.to_dict(), str(report_dir))

            readiness_summary = build_readiness_summary(
                validation_summary=validation_summary.to_dict(),
                data_quality_summary=data_quality_summary.to_dict(),
                meta_risk_summary=meta_risk_summary.to_dict(),
                kill_switch_summary=kill_switch_summary.to_dict() if hasattr(kill_switch_summary, 'to_dict') else kill_switch_summary,
                performance_diagnostics=performance_diagnostics.to_dict(),
                sensitivity_summary=sensitivity_summary.to_dict(),
                broker_health_summary=broker_health_summary.to_dict(),
                monte_carlo_summary=monte_carlo_summary.to_dict(),
            )
            save_json_artifact("readiness_summary.json", readiness_summary.to_dict(), str(report_dir))

            orders: list[BrokerOrder] = []
            if not trade_plan.empty:
                for _, row in trade_plan.iterrows():
                    orders.append(
                        BrokerOrder(
                            symbol=str(row.get("symbol")),
                            side="BUY",
                            qty=to_int(row.get("qty")),
                            order_type="LMT",
                            reference_price=to_float(row.get("close")),
                            stop_loss=to_float(row.get("stop_loss")),
                            take_profit=to_float(row.get("take_profit")),
                            rationale=str(row.get("reasons", "")),
                        )
                    )
                ManualApprovalBroker().submit_orders(orders, str(report_dir / "orders_to_review.csv"))
            else:
                empty_orders_df().to_csv(report_dir / "orders_to_review.csv", index=False)

            ibkr_broker = IBKRManualApprovalBroker(
                host=config.broker.ibkr_host,
                port=config.broker.ibkr_port,
                client_id=config.broker.client_id,
                account=config.broker.account,
                paper_only=config.broker.paper_only,
                currency=config.broker.currency,
                exchange=config.broker.exchange,
            )
            ibkr_broker.submit_approved_orders(
                review_csv=str(report_dir / "orders_to_review.csv"),
                payload_output_path=str(report_dir / "ibkr_order_payloads_preview.json"),
                dry_run=True,
            )

            action_center = build_action_center(
                ranked=ranked,
                trade_plan=trade_plan,
                regime=regime,
                macro_bias=context.macro_bias,
                market_news_bias=context.news_bias,
                breadth_bias=context.breadth_bias,
                paper_only=config.broker.paper_only,
                validation_summary=validation_summary.to_dict(),
                meta_risk_summary=meta_risk_summary.to_dict(),
                kill_switch_summary=kill_switch_summary.to_dict() if hasattr(kill_switch_summary, 'to_dict') else kill_switch_summary,
                readiness_summary=readiness_summary.to_dict(),
            )
            save_json_artifact("action_center.json", action_center, str(report_dir))

            # First-pass audit manifest on already generated artifacts
            audit_manifest = build_audit_manifest(
                config_path=config_path,
                artifact_paths=[
                    report_dir / "ranked_signals.csv",
                    report_dir / "orders_to_review.csv",
                    report_dir / "risk_summary.json",
                    report_dir / "stress_test_summary.json",
                    report_dir / "walkforward_summary.json",
                    report_dir / "validation_summary.json",
                    report_dir / "meta_risk_summary.json",
                    report_dir / "kill_switch_summary.json",
                    report_dir / "broker_health_summary.json",
                    report_dir / "monitoring_summary.json",
                    report_dir / "data_quality_summary.json",
                    report_dir / "decision_journal.json",
                    report_dir / "readiness_summary.json",
                ],
            )
            save_json_artifact("audit_manifest.json", audit_manifest.to_dict(), str(report_dir))

            regression_checklist = build_regression_checklist(
                {
                    "pipeline_status": True,
                    "ranked_signals": (report_dir / "ranked_signals.csv").exists(),
                    "risk_summary": (report_dir / "risk_summary.json").exists(),
                    "stress_test_summary": (report_dir / "stress_test_summary.json").exists(),
                    "walkforward_summary": (report_dir / "walkforward_summary.json").exists(),
                    "monitoring_summary": (report_dir / "monitoring_summary.json").exists(),
                    "audit_manifest": (report_dir / "audit_manifest.json").exists(),
                }
            )
            save_json_artifact("regression_checklist.json", regression_checklist.to_dict(), str(report_dir))

            # Final audit manifest now includes regression checklist existence too
            audit_manifest = build_audit_manifest(
                config_path=config_path,
                artifact_paths=[
                    report_dir / "ranked_signals.csv",
                    report_dir / "orders_to_review.csv",
                    report_dir / "risk_summary.json",
                    report_dir / "stress_test_summary.json",
                    report_dir / "walkforward_summary.json",
                    report_dir / "validation_summary.json",
                    report_dir / "meta_risk_summary.json",
                    report_dir / "kill_switch_summary.json",
                    report_dir / "broker_health_summary.json",
                    report_dir / "monitoring_summary.json",
                    report_dir / "data_quality_summary.json",
                    report_dir / "decision_journal.json",
                    report_dir / "readiness_summary.json",
                    report_dir / "regression_checklist.json",
                    report_dir / "audit_manifest.json",
                ],
            )
            save_json_artifact("audit_manifest.json", audit_manifest.to_dict(), str(report_dir))

            context_summary = (
                f"macro_bias_total={context.macro_bias:+.2f}, "
                f"market_news_bias_total={context.news_bias:+.2f}, "
                f"breadth_bias_total={context.breadth_bias:+.2f}, "
                f"regime={regime}"
            )
            save_report(
                report_dir=str(report_dir),
                benchmark=config.benchmark,
                regime=regime,
                context_summary=context_summary,
                eligible_symbols=eligible_symbols,
                ranked=ranked,
                trade_plan=trade_plan,
                backtest_stats=stats,
                macro_context=macro_context.to_dict(),
                news_summary=news_summary_df,
                earnings_calendar=earnings_calendar_df,
                breadth_context=breadth_context.to_dict(),
                validation_summary=validation_summary.to_dict(),
                risk_summary=risk_summary,
                stress_summary=stress_summary.to_dict(),
                walkforward_summary=walkforward_summary.to_dict(),
                monte_carlo_summary=monte_carlo_summary.to_dict(),
                attribution_summary=attribution_summary.to_dict(),
                pretrade_summary=pretrade_summary.to_dict(),
                meta_risk_summary=meta_risk_summary.to_dict(),
                kill_switch_summary=kill_switch_summary.to_dict() if hasattr(kill_switch_summary, 'to_dict') else kill_switch_summary,
                performance_diagnostics=performance_diagnostics.to_dict(),
                sensitivity_summary=sensitivity_summary.to_dict(),
                broker_health_summary=broker_health_summary.to_dict(),
                monitoring_summary=monitoring_summary.to_dict(),
                data_quality_summary=data_quality_summary.to_dict(),
                exposure_summary=exposure_summary.to_dict(),
                decision_journal=decision_journal.to_dict(),
                audit_manifest=audit_manifest.to_dict(),
                readiness_summary=readiness_summary.to_dict(),
                anomaly_summary=anomaly_summary.to_dict(),
                regression_checklist=regression_checklist.to_dict(),
            )

            history_run_id = store_pipeline_run(
                db_path=config.database.path,
                regime=regime,
                health_score=validation_summary.health_score,
                readiness_score=readiness_summary.readiness_score,
                ranked=ranked,
                trade_plan=trade_plan,
                report_payload={
                    "context_summary": context_summary,
                    "validation_status": validation_summary.status,
                    "meta_confidence": meta_risk_summary.confidence_score,
                    "kill_switch_blocked": kill_switch_summary.blocked if hasattr(kill_switch_summary, 'blocked') else bool(kill_switch_summary.get('blocked', False)),
                },
            )

            pipeline_status = {
                "state": "completed",
                "completed_at": utc_now_iso(),
                "initial_universe_count": len(symbols),
                "eligible_universe_count": len(eligible_symbols),
                "ranked_count": int(len(ranked)),
                "orders_count": int(len(trade_plan)),
                "approved_count": 0,
                "regime": regime,
                "macro_bias": macro_context.bias,
                "market_news_bias": news_context.market_bias,
                "breadth_bias": effective_breadth_bias,
                "paper_only": config.broker.paper_only,
                "validation_status": validation_summary.status,
                "health_score": validation_summary.health_score,
                "meta_risk_confidence": meta_risk_summary.confidence_score,
                "meta_exposure_multiplier": meta_risk_summary.exposure_multiplier,
                "kill_switch_blocked": kill_switch_summary.blocked if hasattr(kill_switch_summary, 'blocked') else bool(kill_switch_summary.get('blocked', False)),
                "data_quality_status": data_quality_summary.status,
                "data_coverage_ratio": data_quality_summary.coverage_ratio,
                "monitoring_alert_level": monitoring_summary.alert_level,
                "readiness_score": readiness_summary.readiness_score,
                "readiness_status": readiness_summary.status,
                "anomaly_count": anomaly_summary.flagged_orders + anomaly_summary.flagged_signals,
                "regression_status": regression_checklist.status,
                "history_run_id": history_run_id,
                "database_path": config.database.path,
                "report_dir": str(report_dir),
            }
            save_json_artifact("pipeline_status.json", pipeline_status, str(report_dir))

            print("Pipeline terminé.")
            print(f"- Univers initial: {len(symbols)} symboles")
            print(f"- Univers éligible: {len(eligible_symbols)} symboles")
            print(f"- Régime détecté: {regime}")
            print(f"- Macro bias calculé: {macro_context.bias:+.2f}")
            print(f"- Market news bias calculé: {news_context.market_bias:+.2f}")
            print(f"- Breadth bias calculé: {effective_breadth_bias:+.2f}")
            print(f"- Rapport: {report_dir / 'latest_report.md'}")
            print(f"- Ordres à valider: {report_dir / 'orders_to_review.csv'}")
            print(f"- Preview IBKR: {report_dir / 'ibkr_order_payloads_preview.json'}")
        except Exception as exc:
            save_json_artifact(
                "pipeline_status.json",
                {
                    "state": "failed",
                    "failed_at": utc_now_iso(),
                    "message": str(exc),
                    "traceback": traceback.format_exc(),
                    "report_dir": str(report_dir),
                },
                str(report_dir),
            )
            raise


def main() -> None:
    args = parse_args()
    run_pipeline(args.config)


if __name__ == "__main__":
    main()
