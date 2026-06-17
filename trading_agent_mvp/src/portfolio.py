from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def _build_correlation_matrix(feature_map: dict[str, pd.DataFrame], lookback: int = 60) -> pd.DataFrame:
    returns = {}
    for symbol, feats in feature_map.items():
        if "ret_1d" not in feats.columns:
            continue
        returns[symbol] = feats["ret_1d"].tail(lookback)
    if not returns:
        return pd.DataFrame()
    return pd.DataFrame(returns).corr()


def diversify_trade_plan(
    trade_plan: pd.DataFrame,
    feature_map: dict[str, pd.DataFrame],
    capital: float,
    max_positions: int,
    max_pairwise_correlation: float = 0.8,
    min_cash_buffer: float = 0.1,
) -> pd.DataFrame:
    if trade_plan.empty:
        return trade_plan

    corr = _build_correlation_matrix(feature_map)
    selected_rows: list[pd.Series] = []
    selected_symbols: list[str] = []

    for _, row in trade_plan.sort_values("score", ascending=False).iterrows():
        symbol = str(row["symbol"])
        if len(selected_rows) >= max_positions:
            break

        too_correlated = False
        if not corr.empty and symbol in corr.index:
            for chosen in selected_symbols:
                if chosen in corr.columns:
                    pair_corr = corr.loc[symbol, chosen]
                    if pd.notna(pair_corr) and pair_corr >= max_pairwise_correlation:
                        too_correlated = True
                        break
        if too_correlated:
            continue

        selected_rows.append(row)
        selected_symbols.append(symbol)

    if not selected_rows:
        return pd.DataFrame(columns=trade_plan.columns)

    out = pd.DataFrame(selected_rows).reset_index(drop=True)

    max_allocatable = capital * (1 - min_cash_buffer)
    total_allocation = float(out["allocation"].sum()) if "allocation" in out.columns else 0.0
    if total_allocation > 0 and total_allocation > max_allocatable:
        scale = max_allocatable / total_allocation
        out["qty"] = (out["qty"] * scale).astype(int)
        out["allocation"] = (out["qty"] * out["close"]).round(2)
        out["risk_amount"] = (out["qty"] * (out["close"] - out["stop_loss"])).round(2)
        out = out[out["qty"] > 0].reset_index(drop=True)

    out["portfolio_note"] = "Sélection filtrée par corrélation et buffer de cash"
    return out


def apply_allocation_caps(
    trade_plan: pd.DataFrame,
    capital: float,
    max_sector_allocation_pct: float = 0.35,
    max_gross_exposure_pct: float = 0.9,
) -> pd.DataFrame:
    if trade_plan.empty or capital <= 0:
        return trade_plan

    out = trade_plan.copy()

    if "sector" in out.columns:
        for sector, sector_df in out.groupby("sector"):
            sector_alloc = float(sector_df["allocation"].sum())
            sector_cap = capital * max_sector_allocation_pct
            if sector_alloc > sector_cap and sector_alloc > 0:
                scale = sector_cap / sector_alloc
                idx = sector_df.index
                out.loc[idx, "qty"] = np.floor(out.loc[idx, "qty"] * scale).astype(int)

    if "qty" in out.columns:
        out["allocation"] = (out["qty"] * out["close"]).round(2)
        out["risk_amount"] = (out["qty"] * (out["close"] - out["stop_loss"])).round(2)
        out = out[out["qty"] > 0].copy()

    gross_cap = capital * max_gross_exposure_pct
    gross_alloc = float(out["allocation"].sum()) if not out.empty else 0.0
    if gross_alloc > gross_cap and gross_alloc > 0:
        scale = gross_cap / gross_alloc
        out["qty"] = np.floor(out["qty"] * scale).astype(int)
        out["allocation"] = (out["qty"] * out["close"]).round(2)
        out["risk_amount"] = (out["qty"] * (out["close"] - out["stop_loss"])).round(2)
        out = out[out["qty"] > 0].copy()

    return out.reset_index(drop=True)


def can_take_long_risk(
    regime: str,
    breadth_bias: float,
    allow_long_only_in_bear: bool,
    breadth_risk_off_threshold: float = -0.35,
    rebalance_to_cash_in_bear: bool = True,
) -> bool:
    regime = (regime or "neutral").lower()
    if regime == "bear" and rebalance_to_cash_in_bear and not allow_long_only_in_bear:
        return False
    if breadth_bias <= breadth_risk_off_threshold:
        return False
    return True
