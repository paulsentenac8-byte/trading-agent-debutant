from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd

from .config import MacroConfig


@dataclass
class MacroSnapshot:
    as_of: str
    bias: float
    summary: list[str]
    latest_values: dict[str, float]
    derived_metrics: dict[str, float]
    errors: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def fetch_fred_series(series_id: str) -> pd.Series:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    df = pd.read_csv(url)
    if "DATE" not in df.columns or series_id not in df.columns:
        raise ValueError(f"Format inattendu FRED pour {series_id}")
    df["DATE"] = pd.to_datetime(df["DATE"], errors="coerce")
    df[series_id] = pd.to_numeric(df[series_id], errors="coerce")
    series = df.set_index("DATE")[series_id].dropna().sort_index()
    if series.empty:
        raise ValueError(f"Série vide pour {series_id}")
    return series


def _series_value_n_periods_ago(series: pd.Series, n: int) -> float | None:
    clean = series.dropna()
    if len(clean) <= n:
        return None
    return float(clean.iloc[-(n + 1)])


def build_macro_context(config: MacroConfig) -> MacroSnapshot:
    if not config.enabled:
        return MacroSnapshot(
            as_of=pd.Timestamp.utcnow().strftime("%Y-%m-%d"),
            bias=0.0,
            summary=["Macro désactivée dans la configuration."],
            latest_values={},
            derived_metrics={},
            errors=[],
        )

    errors: list[str] = []
    series_map: dict[str, pd.Series] = {}

    for name, series_id in config.series.items():
        try:
            series_map[name] = fetch_fred_series(series_id)
        except Exception as exc:  # pragma: no cover - dépend du réseau
            errors.append(f"{name}: {exc}")

    bias = 0.0
    summary: list[str] = []
    latest_values: dict[str, float] = {}
    derived_metrics: dict[str, float] = {}
    as_of_dates: list[pd.Timestamp] = []

    for name, series in series_map.items():
        latest_values[name] = round(float(series.iloc[-1]), 4)
        as_of_dates.append(pd.Timestamp(series.index[-1]))

    vix = series_map.get("vix")
    if vix is not None and not vix.empty:
        vix_latest = float(vix.iloc[-1])
        derived_metrics["vix_latest"] = round(vix_latest, 4)
        if vix_latest >= 28:
            bias -= 0.7
            summary.append("VIX très élevé: régime risk-off.")
        elif vix_latest >= 22:
            bias -= 0.4
            summary.append("VIX élevé: prudence sur le risque.")
        elif vix_latest <= 17:
            bias += 0.2
            summary.append("VIX contenu: stress marché modéré.")

    yc = series_map.get("yield_curve_10y_2y")
    if yc is not None and not yc.empty:
        yc_latest = float(yc.iloc[-1])
        derived_metrics["yield_curve_10y_2y_latest"] = round(yc_latest, 4)
        if yc_latest < 0:
            bias -= 0.2
            summary.append("Courbe 10Y-2Y inversée: vigilance macro.")
        else:
            bias += 0.05
            summary.append("Courbe 10Y-2Y positive.")

    unemployment = series_map.get("unemployment")
    if unemployment is not None and not unemployment.empty:
        old = _series_value_n_periods_ago(unemployment, 3)
        if old is not None:
            delta = float(unemployment.iloc[-1] - old)
            derived_metrics["unemployment_3m_delta"] = round(delta, 4)
            if delta >= 0.3:
                bias -= 0.35
                summary.append("Hausse du chômage sur 3 mois: pression macro négative.")
            elif delta <= -0.2:
                bias += 0.1
                summary.append("Chômage en amélioration sur 3 mois.")

    cpi = series_map.get("cpi")
    if cpi is not None and len(cpi.dropna()) >= 18:
        cpi_yoy = cpi.pct_change(12) * 100
        cpi_yoy = cpi_yoy.dropna()
        if not cpi_yoy.empty:
            latest_cpi_yoy = float(cpi_yoy.iloc[-1])
            derived_metrics["cpi_yoy"] = round(latest_cpi_yoy, 4)
            old_cpi_yoy = _series_value_n_periods_ago(cpi_yoy, 6)
            if old_cpi_yoy is not None:
                if latest_cpi_yoy < old_cpi_yoy:
                    bias += 0.1
                    summary.append("Inflation en ralentissement relatif.")
                else:
                    bias -= 0.1
                    summary.append("Inflation en ré-accélération relative.")

    fed = series_map.get("fed_funds")
    if fed is not None and not fed.empty:
        old = _series_value_n_periods_ago(fed, 6)
        if old is not None:
            delta = float(fed.iloc[-1] - old)
            derived_metrics["fed_funds_6m_delta"] = round(delta, 4)
            if delta >= 0.25:
                bias -= 0.2
                summary.append("Hausse récente des Fed Funds: conditions financières plus strictes.")
            elif delta <= -0.25:
                bias += 0.1
                summary.append("Détente récente des Fed Funds.")

    ten_year = series_map.get("ten_year_yield")
    if ten_year is not None and not ten_year.empty:
        latest_10y = float(ten_year.iloc[-1])
        derived_metrics["ten_year_yield_latest"] = round(latest_10y, 4)
        if latest_10y >= 4.75:
            bias -= 0.15
            summary.append("Taux 10 ans élevé: valorisations plus sous pression.")

    if not summary:
        summary.append("Contexte macro neutre ou données insuffisantes.")

    bias = float(np.clip(bias, -1.5, 1.5))
    as_of = max(as_of_dates).strftime("%Y-%m-%d") if as_of_dates else pd.Timestamp.utcnow().strftime("%Y-%m-%d")

    return MacroSnapshot(
        as_of=as_of,
        bias=round(bias, 4),
        summary=summary,
        latest_values=latest_values,
        derived_metrics=derived_metrics,
        errors=errors,
    )
