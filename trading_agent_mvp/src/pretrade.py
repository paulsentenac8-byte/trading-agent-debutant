from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd

from .config import PreTradeConfig


@dataclass
class PreTradeSummary:
    input_orders: int
    output_orders: int
    total_risk_pct_after_controls: float
    notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _recompute_row_fields(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    out["allocation"] = (out["qty"] * out["close"]).round(2)
    out["risk_amount"] = (out["qty"] * (out["close"] - out["stop_loss"])).round(2)
    return out


def apply_pretrade_controls(trade_plan: pd.DataFrame, capital: float, config: PreTradeConfig) -> tuple[pd.DataFrame, PreTradeSummary]:
    if trade_plan.empty:
        return trade_plan, PreTradeSummary(0, 0, 0.0, ["Aucun ordre à contrôler."])

    out = trade_plan.copy()
    notes: list[str] = []
    input_orders = len(out)

    if "stop_pct" in out.columns:
        before = len(out)
        out = out[out["stop_pct"] <= config.max_stop_pct].copy()
        removed = before - len(out)
        if removed > 0:
            notes.append(f"{removed} ordre(s) retiré(s) car stop_pct > max_stop_pct.")

    if out.empty:
        return out, PreTradeSummary(input_orders, 0, 0.0, notes or ["Tous les ordres ont été rejetés par les contrôles pré-trade."])

    for idx, row in out.iterrows():
        close = float(row["close"])
        avg_dollar_volume = float(row.get("avg_dollar_volume_20", 0.0))
        qty = int(row["qty"])
        max_shares_by_adv = int((avg_dollar_volume * config.max_order_adv_fraction) / close) if close > 0 and avg_dollar_volume > 0 else qty
        if max_shares_by_adv > 0 and qty > max_shares_by_adv:
            out.at[idx, "qty"] = max_shares_by_adv
            notes.append(f"{row['symbol']}: quantité réduite par limite ADV.")

        single_name_risk = float(row.get("risk_amount", 0.0))
        max_single_name_risk_amount = capital * config.max_single_name_risk_pct
        if single_name_risk > max_single_name_risk_amount and single_name_risk > 0:
            scale = max_single_name_risk_amount / single_name_risk
            out.at[idx, "qty"] = int(max(int(out.at[idx, "qty"] * scale), 0))
            notes.append(f"{row['symbol']}: quantité réduite par limite de risque single-name.")

    out = _recompute_row_fields(out)
    out = out[out["qty"] > 0].copy()

    total_risk_amount = float(out["risk_amount"].sum()) if not out.empty else 0.0
    max_total_risk_amount = capital * config.max_total_risk_pct
    if total_risk_amount > max_total_risk_amount and total_risk_amount > 0:
        scale = max_total_risk_amount / total_risk_amount
        out["qty"] = (out["qty"] * scale).astype(int)
        out = _recompute_row_fields(out)
        out = out[out["qty"] > 0].copy()
        notes.append("Risque total réduit pour respecter la limite portefeuille pré-trade.")

    total_risk_pct = float(out["risk_amount"].sum() / capital) if not out.empty and capital > 0 else 0.0
    summary = PreTradeSummary(
        input_orders=input_orders,
        output_orders=len(out),
        total_risk_pct_after_controls=round(total_risk_pct, 4),
        notes=notes or ["Contrôles pré-trade passés sans ajustement majeur."],
    )
    return out.reset_index(drop=True), summary
