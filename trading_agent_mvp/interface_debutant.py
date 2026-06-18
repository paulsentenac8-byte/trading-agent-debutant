from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from src.storage import load_history_summary, load_learning_summary

try:
    from streamlit_autorefresh import st_autorefresh
except Exception:  # pragma: no cover
    def st_autorefresh(*args: Any, **kwargs: Any) -> int:
        return 0


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"
REPORTS_DIR = ROOT / "reports"
APP_STATE_PATH = ROOT / "app_state.json"

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
    "reasons",
]


def inject_css() -> None:
    st.markdown(
        """
        <style>
        #MainMenu, footer, header {visibility: hidden;}
        .block-container {padding-top: 1rem; padding-bottom: 2rem; max-width: 1200px;}
        div.stButton > button {
            border-radius: 12px;
            padding: 0.7rem 1rem;
            font-weight: 700;
        }
        .hero {
            background: linear-gradient(135deg, #0f172a, #1e293b 60%, #1d4ed8);
            color: white;
            padding: 1.2rem 1.4rem;
            border-radius: 18px;
            margin-bottom: 1rem;
        }
        .hero h1 {margin: 0; font-size: 1.8rem;}
        .hero p {margin: 0.35rem 0 0 0; color: #dbeafe;}
        .step-card {
            border: 1px solid #dbe4ee;
            border-radius: 16px;
            padding: 0.9rem 1rem;
            background: white;
            min-height: 130px;
        }
        .step-done {border-left: 8px solid #16a34a;}
        .step-wait {border-left: 8px solid #f59e0b;}
        .pill {
            display: inline-block;
            padding: 0.3rem 0.7rem;
            border-radius: 999px;
            font-size: 0.85rem;
            font-weight: 700;
            margin-right: 0.4rem;
            margin-bottom: 0.4rem;
        }
        .pill-green {background: #dcfce7; color: #166534;}
        .pill-yellow {background: #fef3c7; color: #92400e;}
        .pill-blue {background: #dbeafe; color: #1d4ed8;}
        .trade-card {
            border: 1px solid #e5e7eb;
            border-radius: 16px;
            padding: 1rem;
            background: #ffffff;
            margin-bottom: 0.8rem;
        }
        .small-muted {color: #6b7280; font-size: 0.92rem;}
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(show_spinner=False)
def read_csv_safe(path_str: str) -> pd.DataFrame:
    path = Path(path_str)
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


@st.cache_data(show_spinner=False)
def read_json_safe(path_str: str) -> dict[str, Any]:
    path = Path(path_str)
    if not path.exists() or path.stat().st_size == 0:
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def run_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=str(ROOT), capture_output=True, text=True)


def clear_cache() -> None:
    st.cache_data.clear()


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def save_config(data: dict[str, Any]) -> None:
    CONFIG_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def default_app_state() -> dict[str, Any]:
    return {
        "autopilot": True,
        "refresh_minutes": 30,
        "auto_preview": True,
        "last_auto_attempt": None,
        "last_auto_success": None,
    }


def load_app_state() -> dict[str, Any]:
    if not APP_STATE_PATH.exists():
        return default_app_state()
    try:
        data = json.loads(APP_STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default_app_state()
    merged = default_app_state()
    merged.update(data)
    return merged


def save_app_state(state: dict[str, Any]) -> None:
    APP_STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def ensure_session_defaults() -> None:
    st.session_state.setdefault("last_run_stdout", "")
    st.session_state.setdefault("last_run_stderr", "")
    st.session_state.setdefault("last_submit_stdout", "")
    st.session_state.setdefault("last_submit_stderr", "")
    st.session_state.setdefault("last_doctor_stdout", "")
    st.session_state.setdefault("last_doctor_stderr", "")
    st.session_state.setdefault("bootstrap_done", False)


def to_iso_now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def parse_dt(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    try:
        ts = pd.to_datetime(value)
        if pd.isna(ts):
            return None
        if getattr(ts, "tzinfo", None) is not None:
            ts = ts.tz_convert(None)
        return ts.to_pydatetime()
    except Exception:
        return None


def minutes_since(value: Any) -> float | None:
    dt = parse_dt(value)
    if dt is None:
        return None
    return max((datetime.now() - dt).total_seconds() / 60.0, 0.0)


def humanize_age(value: Any) -> str:
    mins = minutes_since(value)
    if mins is None:
        return "jamais"
    if mins < 1:
        return "à l'instant"
    if mins < 60:
        return f"il y a {int(mins)} min"
    hours = mins / 60.0
    if hours < 24:
        return f"il y a {int(hours)} h"
    return f"il y a {int(hours // 24)} j"


def status_file_path() -> Path:
    return REPORTS_DIR / "pipeline_status.json"


def get_pipeline_status() -> dict[str, Any]:
    status = read_json_safe(str(status_file_path()))
    if status:
        return status
    report = REPORTS_DIR / "latest_report.md"
    if report.exists():
        return {"completed_at": datetime.fromtimestamp(report.stat().st_mtime).isoformat(timespec="seconds")}
    return {}


def should_auto_run(app_state: dict[str, Any], pipeline_status: dict[str, Any]) -> bool:
    if not app_state.get("autopilot", True):
        return False
    refresh_minutes = int(app_state.get("refresh_minutes", 30))
    last_completed_age = minutes_since(pipeline_status.get("completed_at"))
    last_attempt_age = minutes_since(app_state.get("last_auto_attempt"))

    if last_completed_age is None:
        return last_attempt_age is None or last_attempt_age >= refresh_minutes
    return last_completed_age >= refresh_minutes and (last_attempt_age is None or last_attempt_age >= refresh_minutes)


def normalize_orders(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=ORDER_COLUMNS)
    out = df.copy()
    for col in ORDER_COLUMNS:
        if col not in out.columns:
            out[col] = "" if col not in {"qty", "reference_price", "stop_loss", "take_profit", "limit_price"} else 0
    out = out[ORDER_COLUMNS]
    out["approved"] = out["approved"].astype(str).str.lower().isin(["true", "1", "yes", "y", "oui"])
    return out


def normalize_ranked(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=RANKED_COLUMNS)
    out = df.copy()
    for col in RANKED_COLUMNS:
        if col not in out.columns:
            out[col] = ""
    return out[RANKED_COLUMNS]


def save_orders(df: pd.DataFrame) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(REPORTS_DIR / "orders_to_review.csv", index=False)
    clear_cache()


def generate_preview() -> bool:
    result = run_command(
        [
            sys.executable,
            str(ROOT / "submit_ibkr_orders.py"),
            "--config",
            str(CONFIG_PATH),
            "--orders",
            str(REPORTS_DIR / "orders_to_review.csv"),
            "--dry-run",
        ]
    )
    st.session_state["last_submit_stdout"] = result.stdout or ""
    st.session_state["last_submit_stderr"] = result.stderr or ""
    clear_cache()
    return result.returncode == 0


def run_analysis_cycle(auto_preview: bool = True) -> bool:
    result = run_command([sys.executable, str(ROOT / "main.py"), "--config", str(CONFIG_PATH)])
    st.session_state["last_run_stdout"] = result.stdout or ""
    st.session_state["last_run_stderr"] = result.stderr or ""
    clear_cache()
    success = result.returncode == 0
    if success and auto_preview:
        success = generate_preview() and success
    return success


def submit_orders() -> bool:
    result = run_command(
        [
            sys.executable,
            str(ROOT / "submit_ibkr_orders.py"),
            "--config",
            str(CONFIG_PATH),
            "--orders",
            str(REPORTS_DIR / "orders_to_review.csv"),
            "--submit",
        ]
    )
    st.session_state["last_submit_stdout"] = result.stdout or ""
    st.session_state["last_submit_stderr"] = result.stderr or ""
    clear_cache()
    return result.returncode == 0


def run_doctor() -> bool:
    result = run_command([sys.executable, str(ROOT / "doctor.py")])
    st.session_state["last_doctor_stdout"] = result.stdout or ""
    st.session_state["last_doctor_stderr"] = result.stderr or ""
    return result.returncode == 0


def update_beginner_settings(capital: float, risk_level: str, paper_only: bool) -> None:
    cfg = load_config()
    cfg["initial_capital"] = float(capital)
    cfg.setdefault("broker", {})
    cfg["broker"]["paper_only"] = bool(paper_only)

    if risk_level == "Prudent":
        cfg["risk_per_trade"] = 0.005
        cfg["max_positions"] = 3
        cfg["max_position_weight"] = 0.10
    elif risk_level == "Équilibré":
        cfg["risk_per_trade"] = 0.01
        cfg["max_positions"] = 5
        cfg["max_position_weight"] = 0.20
    else:
        cfg["risk_per_trade"] = 0.015
        cfg["max_positions"] = 6
        cfg["max_position_weight"] = 0.25

    save_config(cfg)


def approval_key(index: int, symbol: str) -> str:
    return f"approve_{index}_{symbol}"


def init_approval_state(orders: pd.DataFrame) -> None:
    for idx, row in orders.reset_index(drop=True).iterrows():
        key = approval_key(idx, str(row["symbol"]))
        if key not in st.session_state:
            st.session_state[key] = bool(row["approved"])


def build_orders_from_session(orders: pd.DataFrame) -> pd.DataFrame:
    updated = orders.copy().reset_index(drop=True)
    for idx, row in updated.iterrows():
        updated.at[idx, "approved"] = bool(st.session_state.get(approval_key(idx, str(row["symbol"])), False))
    return updated


def set_bulk_approvals(orders: pd.DataFrame, mode: str) -> None:
    for idx, row in orders.reset_index(drop=True).iterrows():
        key = approval_key(idx, str(row["symbol"]))
        if mode == "all":
            st.session_state[key] = True
        elif mode == "none":
            st.session_state[key] = False
        elif mode == "top3":
            st.session_state[key] = idx < 3


def signal_strength(score: float) -> tuple[str, str]:
    if score >= 4:
        return "fort", "🟢"
    if score >= 2.5:
        return "correct", "🟡"
    return "faible", "🔴"


def show_step_card(title: str, done: bool, description: str) -> None:
    css_class = "step-done" if done else "step-wait"
    emoji = "✅" if done else "⏳"
    st.markdown(
        f"<div class='step-card {css_class}'><h4>{emoji} {title}</h4><p>{description}</p></div>",
        unsafe_allow_html=True,
    )


def show_hero(app_state: dict[str, Any], pipeline_status: dict[str, Any], cfg: dict[str, Any]) -> None:
    last_run = humanize_age(pipeline_status.get("completed_at"))
    mode = "Démo" if cfg.get("broker", {}).get("paper_only", True) else "Réel"
    autopilot = "Activé" if app_state.get("autopilot", True) else "Désactivé"
    st.markdown(
        f"""
        <div class='hero'>
            <h1>Assistant Trading Débutant — Premium</h1>
            <p>Le système analyse automatiquement le marché. Toi, tu n'as qu'à autoriser ou refuser les trades.</p>
            <div style='margin-top: 0.8rem;'>
                <span class='pill pill-green'>Dernière analyse : {last_run}</span>
                <span class='pill pill-blue'>Mode broker : {mode}</span>
                <span class='pill pill-yellow'>Pilote automatique : {autopilot}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def show_action_center(action_center: dict[str, Any], risk_summary: dict[str, Any], pipeline_status: dict[str, Any]) -> None:
    pipeline_state = pipeline_status.get("state", "unknown")
    if pipeline_state == "running":
        st.info("Analyse en cours. L'interface se mettra à jour quand le scan sera terminé.")
    elif pipeline_state == "busy":
        st.warning("Une autre analyse est déjà en cours. Attends quelques instants.")
    elif pipeline_state == "failed":
        st.error(f"La dernière analyse a échoué: {pipeline_status.get('message', 'erreur inconnue')}")

    headline = action_center.get("headline", "Aucune information disponible.")
    next_step = action_center.get("next_step", "Lance une analyse pour commencer.")
    status = action_center.get("status", "unknown")

    if status == "orders_ready":
        st.success(f"{headline} — Prochaine action: {next_step}")
    elif status == "analysis_ready_no_orders":
        st.info(f"{headline} — Prochaine action: {next_step}")
    else:
        st.warning(f"{headline} — Prochaine action: {next_step}")

    warnings = action_center.get("warnings", []) if isinstance(action_center, dict) else []
    if warnings:
        with st.expander("Voir les avertissements du jour"):
            for warning in warnings:
                st.warning(warning)

    cols = st.columns(4)
    cols[0].metric("Ordres proposés", risk_summary.get("n_orders", 0))
    cols[1].metric("Allocation estimée", f"${risk_summary.get('estimated_total_allocation', 0):,.0f}")
    cols[2].metric("Cash restant", f"${risk_summary.get('estimated_cash_remaining', 0):,.0f}")
    cols[3].metric("Risque estimé", f"${risk_summary.get('estimated_total_risk_amount', 0):,.0f}")


def maybe_bootstrap_and_autorun(app_state: dict[str, Any], pipeline_status: dict[str, Any]) -> None:
    refresh_minutes = int(app_state.get("refresh_minutes", 30))
    if app_state.get("autopilot", True):
        st_autorefresh(interval=refresh_minutes * 60 * 1000, key="assistant_refresh")

    if should_auto_run(app_state, pipeline_status):
        app_state["last_auto_attempt"] = to_iso_now()
        save_app_state(app_state)
        with st.spinner("Analyse automatique en cours..."):
            ok = run_analysis_cycle(auto_preview=bool(app_state.get("auto_preview", True)))
        if ok:
            app_state["last_auto_success"] = to_iso_now()
            save_app_state(app_state)
            st.success("Analyse automatique terminée.")
        else:
            save_app_state(app_state)
            st.error("L'analyse automatique a échoué. Vérifie les journaux dans l'onglet Détails.")
        st.rerun()


def main() -> None:
    st.set_page_config(page_title="Assistant Trading Débutant", layout="wide", initial_sidebar_state="expanded")
    ensure_session_defaults()
    inject_css()

    cfg = load_config()
    app_state = load_app_state()
    pipeline_status = get_pipeline_status()
    maybe_bootstrap_and_autorun(app_state, pipeline_status)

    cfg = load_config()
    app_state = load_app_state()
    pipeline_status = get_pipeline_status()

    report_md_path = REPORTS_DIR / "latest_report.md"
    ranked = normalize_ranked(read_csv_safe(str(REPORTS_DIR / "ranked_signals.csv")))
    orders = normalize_orders(read_csv_safe(str(REPORTS_DIR / "orders_to_review.csv")))
    backtest = read_json_safe(str(REPORTS_DIR / "backtest_stats.json"))
    macro = read_json_safe(str(REPORTS_DIR / "macro_context.json"))
    breadth = read_json_safe(str(REPORTS_DIR / "breadth_context.json"))
    news = read_csv_safe(str(REPORTS_DIR / "news_summary.csv"))
    earnings = read_csv_safe(str(REPORTS_DIR / "earnings_calendar.csv"))
    preview_payload = read_json_safe(str(REPORTS_DIR / "ibkr_order_payloads_preview.json"))
    submission_log = read_json_safe(str(REPORTS_DIR / "ibkr_submission_log.json"))
    action_center = read_json_safe(str(REPORTS_DIR / "action_center.json"))
    risk_summary = read_json_safe(str(REPORTS_DIR / "risk_summary.json"))
    validation_summary = read_json_safe(str(REPORTS_DIR / "validation_summary.json"))
    stress_summary = read_json_safe(str(REPORTS_DIR / "stress_test_summary.json"))
    walkforward_summary = read_json_safe(str(REPORTS_DIR / "walkforward_summary.json"))
    monte_carlo_summary = read_json_safe(str(REPORTS_DIR / "monte_carlo_summary.json"))
    attribution_summary = read_json_safe(str(REPORTS_DIR / "attribution_summary.json"))
    meta_risk_summary = read_json_safe(str(REPORTS_DIR / "meta_risk_summary.json"))
    pretrade_summary = read_json_safe(str(REPORTS_DIR / "pretrade_summary.json"))
    kill_switch_summary = read_json_safe(str(REPORTS_DIR / "kill_switch_summary.json"))
    performance_diagnostics = read_json_safe(str(REPORTS_DIR / "performance_diagnostics.json"))
    sensitivity_summary = read_json_safe(str(REPORTS_DIR / "sensitivity_summary.json"))
    broker_health_summary = read_json_safe(str(REPORTS_DIR / "broker_health_summary.json"))
    monitoring_summary = read_json_safe(str(REPORTS_DIR / "monitoring_summary.json"))
    readiness_summary = read_json_safe(str(REPORTS_DIR / "readiness_summary.json"))
    anomaly_summary = read_json_safe(str(REPORTS_DIR / "anomaly_summary.json"))
    regression_checklist = read_json_safe(str(REPORTS_DIR / "regression_checklist.json"))
    data_quality_summary = read_json_safe(str(REPORTS_DIR / "data_quality_summary.json"))
    exposure_summary = read_json_safe(str(REPORTS_DIR / "exposure_summary.json"))
    decision_journal = read_json_safe(str(REPORTS_DIR / "decision_journal.json"))
    db_path = cfg.get("database", {}).get("path", "data/trading_agent.sqlite") if cfg else "data/trading_agent.sqlite"
    history_summary = load_history_summary(db_path).to_dict()
    learning_summary = load_learning_summary(db_path).to_dict()

    show_hero(app_state, pipeline_status, cfg)
    show_action_center(action_center, risk_summary, pipeline_status)

    st.markdown("### Actions rapides")
    qa1, qa2, qa3 = st.columns(3)
    if qa1.button("Lancer tout maintenant", type="primary", use_container_width=True, key="top_run_now"):
        with st.spinner("Analyse + préparation broker en cours..."):
            ok = run_analysis_cycle(auto_preview=bool(app_state.get("auto_preview", True)))
        if ok:
            st.success("Analyse lancée depuis la page principale.")
        else:
            st.error("Le lancement a échoué. Regarde l'onglet Détails et aide.")
        st.rerun()
    if qa2.button("Préparer le broker", use_container_width=True, key="top_prepare_preview"):
        ok = generate_preview()
        if ok:
            st.success("Preview broker préparé.")
        else:
            st.error("Impossible de préparer le preview broker.")
        st.rerun()
    if qa3.button("Vérifier l'installation", use_container_width=True, key="top_run_doctor"):
        ok = run_doctor()
        if ok:
            st.success("Diagnostic OK.")
        else:
            st.error("Le diagnostic a trouvé un problème. Regarde l'onglet Détails et aide.")

    st.caption("Si tu ne vois pas la barre latérale, utilise ces boutons rapides au centre de la page.")

    with st.sidebar:
        st.header("Réglages simples")
        current_capital = float(cfg.get("initial_capital", 100000))
        capital = st.number_input("Capital de départ ($)", min_value=1000.0, max_value=10000000.0, value=current_capital, step=1000.0)

        current_rpt = float(cfg.get("risk_per_trade", 0.01))
        default_risk = "Équilibré"
        if current_rpt <= 0.005:
            default_risk = "Prudent"
        elif current_rpt >= 0.015:
            default_risk = "Dynamique"
        risk_level = st.selectbox("Profil de risque", ["Prudent", "Équilibré", "Dynamique"], index=["Prudent", "Équilibré", "Dynamique"].index(default_risk))

        paper_only = st.checkbox("Mode démo uniquement", value=bool(cfg.get("broker", {}).get("paper_only", True)))
        autopilot = st.checkbox("Pilote automatique", value=bool(app_state.get("autopilot", True)))
        refresh_minutes = st.slider("Rafraîchir toutes les X minutes", min_value=5, max_value=180, value=int(app_state.get("refresh_minutes", 30)), step=5)
        auto_preview = st.checkbox("Préparer automatiquement le broker après analyse", value=bool(app_state.get("auto_preview", True)))

        if st.button("Enregistrer mes réglages", use_container_width=True):
            update_beginner_settings(capital, risk_level, paper_only)
            app_state["autopilot"] = bool(autopilot)
            app_state["refresh_minutes"] = int(refresh_minutes)
            app_state["auto_preview"] = bool(auto_preview)
            save_app_state(app_state)
            st.success("Réglages enregistrés.")
            st.rerun()

        st.markdown("---")
        if st.button("Lancer tout maintenant", type="primary", use_container_width=True):
            with st.spinner("Analyse + préparation broker en cours..."):
                ok = run_analysis_cycle(auto_preview=bool(auto_preview))
            if ok:
                st.success("Tout est prêt.")
            else:
                st.error("Le lancement a échoué.")
            st.rerun()

        if st.button("Vérifier mon installation", use_container_width=True):
            ok = run_doctor()
            if ok:
                st.success("Installation vérifiée.")
            else:
                st.error("Le diagnostic a trouvé un problème. Regarde l'onglet Détails et aide.")

        st.caption("Astuce : laisse le pilote automatique activé pour n'avoir qu'à revenir autoriser les trades.")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Opportunités trouvées", int(len(ranked)))
    c2.metric("Trades à autoriser", int(len(orders)))
    c3.metric("Contexte macro", f"{float(macro.get('bias', 0.0)):+.2f}")
    c4.metric("Health score", validation_summary.get("health_score", "n/a"))

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Régime", pipeline_status.get("regime", "n/a"))
    c6.metric("Meta confiance", meta_risk_summary.get("confidence_score", "n/a"))
    c7.metric("Expo meta", meta_risk_summary.get("exposure_multiplier", "n/a"))
    c8.metric("MC proba perte", monte_carlo_summary.get("prob_negative_return", "n/a"))

    c9, c10, c11, c12 = st.columns(4)
    c9.metric("Kill switch", "ON" if kill_switch_summary.get("blocked") else "OFF")
    c10.metric("Info ratio", performance_diagnostics.get("information_ratio", "n/a"))
    c11.metric("Sensibilité +Sharpe", sensitivity_summary.get("positive_sharpe_ratio", "n/a"))
    c12.metric("Excès vs bench", performance_diagnostics.get("excess_return", "n/a"))

    c13, c14 = st.columns(2)
    c13.metric("Broker santé", "OK" if broker_health_summary.get("reachable") else "DOWN")
    c14.metric("Monitoring", monitoring_summary.get("alert_level", "n/a"))

    c15, c16 = st.columns(2)
    c15.metric("Readiness", readiness_summary.get("readiness_score", "n/a"))
    c16.metric("Anomalies", anomaly_summary.get("flagged_orders", 0) + anomaly_summary.get("flagged_signals", 0) if anomaly_summary else "n/a")

    c17, c18 = st.columns(2)
    c17.metric("Scans mémorisés", len(history_summary.get("runs", [])))
    c18.metric("Signaux mémorisés", len(history_summary.get("recent_signals", [])))

    c19, c20 = st.columns(2)
    c19.metric("Signaux maturés", learning_summary.get("matured_signals", 0))
    c20.metric("Win rate 20j", history_summary.get("signal_outcome_summary", {}).get("win_rate_20d", "n/a"))

    step1_done = bool(pipeline_status)
    step2_done = not ranked.empty
    step3_done = not orders.empty
    step4_done = bool(preview_payload)

    s1, s2, s3, s4 = st.columns(4)
    with s1:
        show_step_card("1. Analyse du marché", step1_done, "Le bot scanne automatiquement actions, macro, news et earnings.")
    with s2:
        show_step_card("2. Sélection des opportunités", step2_done, "Le système choisit les meilleures idées de trades et les classe.")
    with s3:
        show_step_card("3. Ton autorisation", step3_done, "Tu coches seulement les trades que tu acceptes.")
    with s4:
        show_step_card("4. Préparation broker", step4_done, "Le système prépare l'envoi au broker démo automatiquement.")

    tab1, tab2, tab3, tab4 = st.tabs(["Vue guidée", "Autoriser les trades", "Marché expliqué simplement", "Détails et aide"])

    with tab1:
        st.subheader("Les meilleures idées du moment")
        top_symbols = action_center.get("top_symbols", []) if isinstance(action_center, dict) else []
        if top_symbols:
            st.caption("Résumé rapide des 3 meilleures idées détectées")
            st.json(top_symbols)
        if ranked.empty:
            st.info("Aucune analyse disponible pour le moment. Utilise le bouton 'Lancer tout maintenant'.")
        else:
            for _, row in ranked.head(5).iterrows():
                score = float(row.get("score", 0.0))
                strength, emoji = signal_strength(score)
                with st.container(border=True):
                    st.markdown(f"### {emoji} {row['symbol']} — score {score:.2f}")
                    col_a, col_b, col_c = st.columns(3)
                    col_a.write(f"**Prix actuel** : {row.get('close', 'n/a')}")
                    col_b.write(f"**Momentum 20 jours** : {row.get('mom_20', 'n/a')}")
                    col_c.write(f"**Qualité estimée** : {strength}")
                    st.write("**Explication simple**")
                    st.write(str(row.get("reasons", "Pas d'explication disponible.")))

        st.markdown("---")
        st.subheader("Lecture ultra simple")
        if not orders.empty:
            st.success(f"Le système a préparé {len(orders)} trade(s) à examiner.")
        else:
            st.info("Aucun trade n'est proposé pour l'instant.")

        macro_bias = float(macro.get("bias", 0.0)) if macro else 0.0
        if macro_bias > 0.2:
            st.success("Le contexte global est plutôt favorable au risque.")
        elif macro_bias < -0.2:
            st.warning("Le contexte global est plutôt prudent. Le système restera plus sélectif.")
        else:
            st.info("Le contexte global est neutre.")

        if preview_payload:
            st.success("Le preview broker est déjà prêt. Il ne manque plus que ton autorisation éventuelle.")

    with tab2:
        st.subheader("Autoriser ou refuser les trades")
        st.write("Tu n'as qu'une seule vraie action à faire ici : dire OUI ou NON à chaque trade proposé.")

        if orders.empty:
            st.info("Aucun trade à autoriser pour le moment.")
        else:
            init_approval_state(orders)

            b1, b2, b3 = st.columns(3)
            if b1.button("Autoriser les 3 premiers", use_container_width=True):
                set_bulk_approvals(orders, "top3")
            if b2.button("Tout autoriser", use_container_width=True):
                set_bulk_approvals(orders, "all")
            if b3.button("Tout refuser", use_container_width=True):
                set_bulk_approvals(orders, "none")

            for idx, row in orders.reset_index(drop=True).iterrows():
                key = approval_key(idx, str(row["symbol"]))
                with st.container(border=True):
                    c_left, c_right = st.columns([2, 1])
                    with c_left:
                        st.checkbox(f"J'autorise le trade sur {row['symbol']}", key=key)
                        st.write(f"**Pourquoi ce trade ?** {row['rationale']}")
                    with c_right:
                        st.write(f"**Qté** : {row['qty']}")
                        st.write(f"**Prix** : {row['reference_price']}")
                        st.write(f"**Stop** : {row['stop_loss']}")
                        st.write(f"**Objectif** : {row['take_profit']}")

            c1, c2, c3 = st.columns(3)
            if c1.button("Enregistrer mes choix", use_container_width=True):
                updated = build_orders_from_session(orders)
                save_orders(updated)
                st.success("Tes choix ont été enregistrés.")
                st.rerun()

            if c2.button("Préparer le broker avec mes choix", use_container_width=True):
                updated = build_orders_from_session(orders)
                save_orders(updated)
                ok = generate_preview()
                if ok:
                    st.success("Le preview broker est prêt.")
                else:
                    st.error("Impossible de préparer le broker.")
                st.rerun()

            broker_demo = bool(load_config().get("broker", {}).get("paper_only", True))
            submit_label = "Envoyer au broker démo" if broker_demo else "Envoyer au broker"
            if c3.button(submit_label, use_container_width=True):
                updated = build_orders_from_session(orders)
                save_orders(updated)
                ok = submit_orders()
                if ok:
                    st.success("Ordres envoyés avec succès.")
                else:
                    st.error("Échec lors de l'envoi des ordres.")
                st.rerun()

            approved_count = int(build_orders_from_session(orders)["approved"].sum())
            st.metric("Trades autorisés par toi", approved_count)

            if preview_payload:
                with st.expander("Voir ce qui sera envoyé au broker"):
                    st.json(preview_payload)

    with tab3:
        st.subheader("Le marché expliqué sans jargon compliqué")
        st.markdown("### Macro")
        if macro:
            st.write(f"**Score macro global** : {float(macro.get('bias', 0.0)):+.2f}")
            for item in macro.get("summary", []):
                st.write(f"- {item}")
        else:
            st.info("Pas encore de lecture macro disponible.")

        st.markdown("### Breadth de marché")
        if breadth:
            st.json(breadth)
        else:
            st.info("Pas encore de résumé breadth disponible.")

        st.markdown("### Qualité des données")
        if data_quality_summary:
            st.json(data_quality_summary)
        else:
            st.info("Pas encore de résumé qualité de données.")

        st.markdown("### News")
        if not news.empty:
            st.dataframe(news.sort_values("symbol_bias", ascending=False), use_container_width=True, hide_index=True)
        else:
            st.info("Pas encore de résumé news disponible.")

        st.markdown("### Résultats d'entreprises proches")
        if not earnings.empty:
            st.dataframe(earnings.head(20), use_container_width=True, hide_index=True)
        else:
            st.info("Aucun résultat proche détecté.")

        st.markdown("### Validation / santé du système")
        if validation_summary:
            st.json(validation_summary)
        else:
            st.info("Pas encore de résumé de validation.")

        st.markdown("### Mémoire / apprentissage")
        if learning_summary:
            st.json(learning_summary)
        else:
            st.info("Pas encore de résumé d'apprentissage.")

        st.markdown("### Readiness")
        if readiness_summary:
            st.json(readiness_summary)
        else:
            st.info("Pas encore de résumé readiness.")

        st.markdown("### Meta-risk")
        if meta_risk_summary:
            st.json(meta_risk_summary)
        else:
            st.info("Pas encore de résumé meta-risk.")

        st.markdown("### Kill switch")
        if kill_switch_summary:
            st.json(kill_switch_summary)
        else:
            st.info("Pas encore de résumé kill switch.")

        st.markdown("### Diagnostics de performance")
        if performance_diagnostics:
            st.json(performance_diagnostics)
        else:
            st.info("Pas encore de diagnostic de performance.")

        st.markdown("### Santé broker / monitoring")
        if broker_health_summary:
            st.json(broker_health_summary)
        else:
            st.info("Pas encore de résumé broker.")
        if monitoring_summary:
            st.json(monitoring_summary)
        else:
            st.info("Pas encore de résumé monitoring.")

    with tab4:
        st.subheader("Détails et aide")
        st.markdown(
            """
### Comment utiliser l'assistant ?
1. Laisse le **pilote automatique** activé.
2. Le système scanne le marché tout seul.
3. Va dans **Autoriser les trades**.
4. Coche uniquement les trades que tu acceptes.
5. Clique sur **Envoyer au broker démo**.

### Recommandation
Au début, garde toujours le **mode démo uniquement**.
            """
        )

        if report_md_path.exists():
            with st.expander("Voir le rapport complet généré par le système"):
                st.markdown(report_md_path.read_text(encoding="utf-8"))

        with st.expander("Sortie du dernier lancement"):
            st.code(st.session_state.get("last_run_stdout", "") or "Aucune sortie disponible.")
            if st.session_state.get("last_run_stderr"):
                st.error(st.session_state["last_run_stderr"])

        with st.expander("Sortie du dernier envoi broker"):
            st.code(st.session_state.get("last_submit_stdout", "") or "Aucune sortie disponible.")
            if st.session_state.get("last_submit_stderr"):
                st.error(st.session_state["last_submit_stderr"])

        with st.expander("Diagnostic de l'installation"):
            st.code(st.session_state.get("last_doctor_stdout", "") or "Aucun diagnostic lancé depuis l'interface.")
            if st.session_state.get("last_doctor_stderr"):
                st.error(st.session_state["last_doctor_stderr"])

        if submission_log:
            with st.expander("Journal d'envoi broker"):
                st.json(submission_log)

        with st.expander("Résumé risque portefeuille"):
            st.json(risk_summary or {"info": "Aucun résumé risque disponible."})

        with st.expander("Exposition portefeuille"):
            st.json(exposure_summary or {"info": "Aucune exposition disponible."})

        with st.expander("Journal de décision"):
            st.json(decision_journal or {"info": "Aucun journal de décision disponible."})

        with st.expander("Mémoire / historique"):
            st.json(history_summary or {"info": "Aucun historique disponible."})

        with st.expander("Learning engine supervisé"):
            st.json(learning_summary or {"info": "Aucun apprentissage disponible."})

        with st.expander("Anomalies détectées"):
            st.json(anomaly_summary or {"info": "Aucun résumé d'anomalies disponible."})

        with st.expander("Contrôles pré-trade"):
            st.json(pretrade_summary or {"info": "Aucun résumé pré-trade disponible."})

        with st.expander("Meta-risk overlay"):
            st.json(meta_risk_summary or {"info": "Aucun résumé meta-risk disponible."})

        with st.expander("Stress tests portefeuille"):
            st.json(stress_summary or {"info": "Aucun stress test disponible."})

        with st.expander("Walk-forward quant pro"):
            st.json(walkforward_summary or {"info": "Aucun résumé walk-forward disponible."})

        with st.expander("Monte Carlo"):
            st.json(monte_carlo_summary or {"info": "Aucun résumé Monte Carlo disponible."})

        with st.expander("Attribution facteurs"):
            st.json(attribution_summary or {"info": "Aucune attribution disponible."})

        with st.expander("Sensibilité des paramètres"):
            st.json(sensitivity_summary or {"info": "Aucune sensibilité disponible."})

        with st.expander("Diagnostics de performance"):
            st.json(performance_diagnostics or {"info": "Aucun diagnostic de performance disponible."})

        with st.expander("Kill switch"):
            st.json(kill_switch_summary or {"info": "Aucun résumé kill switch disponible."})

        with st.expander("Santé broker / monitoring"):
            st.json({
                "broker_health_summary": broker_health_summary or {"info": "Aucun résumé broker disponible."},
                "monitoring_summary": monitoring_summary or {"info": "Aucun résumé monitoring disponible."},
                "readiness_summary": readiness_summary or {"info": "Aucun résumé readiness disponible."},
                "regression_checklist": regression_checklist or {"info": "Aucune checklist disponible."},
            })

        with st.expander("Paramètres automatiques actuels"):
            st.json({
                "config": cfg,
                "app_state": app_state,
                "pipeline_status": pipeline_status,
                "action_center": action_center,
                "validation_summary": validation_summary,
            })

    st.caption(f"Dernière consultation de l'interface : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
