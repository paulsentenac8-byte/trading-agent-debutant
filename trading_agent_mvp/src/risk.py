from __future__ import annotations

import math

import pandas as pd


def estimate_stop_pct(close: float, atr_14: float) -> float:
    if close <= 0:
        return 0.08
    atr_stop = (2.2 * atr_14) / close if atr_14 > 0 else 0.06
    return float(min(max(atr_stop, 0.035), 0.12))


def conviction_multiplier(score: float, min_score: float) -> float:
    if score <= min_score:
        return 0.7
    if score >= min_score + 3.0:
        return 1.2
    scaled = 0.7 + ((score - min_score) / 3.0) * 0.5
    return float(min(max(scaled, 0.7), 1.2))


def position_size(
    capital: float,
    entry_price: float,
    stop_pct: float,
    risk_per_trade: float,
    max_position_weight: float,
    conviction: float = 1.0,
) -> int:
    if capital <= 0 or entry_price <= 0 or stop_pct <= 0:
        return 0

    risk_budget = capital * risk_per_trade * conviction
    max_position_value = capital * max_position_weight * conviction
    shares_by_risk = risk_budget / (entry_price * stop_pct)
    shares_by_weight = max_position_value / entry_price
    qty = math.floor(min(shares_by_risk, shares_by_weight))
    return max(qty, 0)


def build_trade_plan(
    ranked: pd.DataFrame,
    capital: float,
    max_positions: int,
    risk_per_trade: float,
    max_position_weight: float,
    min_score: float = 1.5,
) -> pd.DataFrame:
    if ranked.empty:
        return pd.DataFrame()

    selected = ranked[ranked["score"] >= min_score].head(max_positions * 2).copy()
    if selected.empty:
        return pd.DataFrame()

    qty_list = []
    stop_pct_list = []
    stop_loss_list = []
    take_profit_list = []
    allocation_list = []
    conviction_list = []
    risk_amount_list = []

    for _, row in selected.iterrows():
        close = float(row["close"])
        atr_14 = float(row["atr_14"])
        score = float(row["score"])
        stop_pct = estimate_stop_pct(close, atr_14)
        conviction = conviction_multiplier(score, min_score)
        qty = position_size(
            capital=capital,
            entry_price=close,
            stop_pct=stop_pct,
            risk_per_trade=risk_per_trade,
            max_position_weight=max_position_weight,
            conviction=conviction,
        )
        stop_loss = close * (1 - stop_pct)
        take_profit = close * (1 + stop_pct * 2.2)
        allocation = qty * close
        risk_amount = qty * (close - stop_loss)

        qty_list.append(qty)
        stop_pct_list.append(round(stop_pct, 4))
        stop_loss_list.append(round(stop_loss, 4))
        take_profit_list.append(round(take_profit, 4))
        allocation_list.append(round(allocation, 2))
        conviction_list.append(round(conviction, 4))
        risk_amount_list.append(round(risk_amount, 2))

    selected["qty"] = qty_list
    selected["stop_pct"] = stop_pct_list
    selected["stop_loss"] = stop_loss_list
    selected["take_profit"] = take_profit_list
    selected["allocation"] = allocation_list
    selected["conviction_multiplier"] = conviction_list
    selected["risk_amount"] = risk_amount_list

    selected = selected[selected["qty"] > 0].copy()
    return selected.reset_index(drop=True)
