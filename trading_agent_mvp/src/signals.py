from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class MarketContext:
    macro_bias: float = 0.0
    news_bias: float = 0.0
    breadth_bias: float = 0.0
    regime: str | None = None
    symbol_news_bias: dict[str, float] = field(default_factory=dict)
    symbol_event_bias: dict[str, float] = field(default_factory=dict)


def infer_market_regime(benchmark_features: pd.DataFrame, override: str | None = None) -> str:
    if override:
        return override.lower()

    row = benchmark_features.iloc[-1]
    close = float(row["Adj Close"])
    sma_50 = float(row["sma_50"])
    sma_200 = float(row["sma_200"])
    vol_20 = float(row["vol_20"])
    drawdown_60 = float(row.get("drawdown_60", 0.0))
    mom_20 = float(row.get("mom_20", 0.0))

    if close > sma_50 > sma_200:
        if vol_20 < 0.22 and drawdown_60 > -0.06:
            return "bull_quiet"
        return "bull_volatile"

    if close < sma_50 < sma_200:
        if drawdown_60 <= -0.18 or vol_20 >= 0.45:
            return "riskoff"
        return "bear"

    if close > sma_200 and mom_20 >= 0:
        return "neutral_up"
    if close < sma_200 and drawdown_60 <= -0.1:
        return "correction"
    return "neutral"


def _clip_score(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return float(np.clip(value, low, high))


def _strategy_weights(regime: str) -> dict[str, float]:
    regime = regime.lower()
    if regime == "bull_quiet":
        return {"trend": 0.34, "momentum": 0.26, "breakout": 0.18, "pullback": 0.10, "quality": 0.12}
    if regime == "bull_volatile":
        return {"trend": 0.28, "momentum": 0.22, "breakout": 0.12, "pullback": 0.20, "quality": 0.18}
    if regime == "neutral_up":
        return {"trend": 0.27, "momentum": 0.22, "breakout": 0.14, "pullback": 0.18, "quality": 0.19}
    if regime == "correction":
        return {"trend": 0.16, "momentum": 0.10, "breakout": 0.05, "pullback": 0.24, "quality": 0.20}
    if regime == "bear":
        return {"trend": 0.16, "momentum": 0.10, "breakout": 0.05, "pullback": 0.14, "quality": 0.20}
    if regime == "riskoff":
        return {"trend": 0.10, "momentum": 0.06, "breakout": 0.02, "pullback": 0.08, "quality": 0.22}
    return {"trend": 0.27, "momentum": 0.21, "breakout": 0.14, "pullback": 0.16, "quality": 0.14}


def _trend_component(snapshot: dict[str, Any]) -> tuple[float, list[str]]:
    close = snapshot["close"]
    sma_50 = snapshot["sma_50"]
    sma_200 = snapshot["sma_200"]
    sma50_slope_20 = snapshot["sma50_slope_20"]
    sma200_slope_20 = snapshot["sma200_slope_20"]
    score = 0.0
    reasons: list[str] = []

    if close > sma_50:
        score += 0.35
        reasons.append("prix > SMA50")
    if sma_50 > sma_200:
        score += 0.35
        reasons.append("SMA50 > SMA200")
    if sma50_slope_20 > 0:
        score += 0.2
        reasons.append("SMA50 en pente positive")
    if sma200_slope_20 > 0:
        score += 0.1
        reasons.append("SMA200 en pente positive")

    return _clip_score(score, -1.0, 1.0), reasons


def _momentum_component(snapshot: dict[str, Any]) -> tuple[float, list[str]]:
    mom_20 = snapshot["mom_20"]
    mom_60 = snapshot["mom_60"]
    mom_120 = snapshot["mom_120"]
    rel_strength_20 = snapshot["rel_strength_20"]
    rel_strength_60 = snapshot["rel_strength_60"]
    score = 0.0
    reasons: list[str] = []

    score += _clip_score(mom_20 * 5, -0.35, 0.35)
    score += _clip_score(mom_60 * 4, -0.3, 0.3)
    score += _clip_score(mom_120 * 3, -0.2, 0.2)
    score += _clip_score(rel_strength_20 * 6, -0.2, 0.2)
    score += _clip_score(rel_strength_60 * 5, -0.15, 0.15)

    if mom_20 > 0:
        reasons.append("momentum 20j positif")
    if mom_60 > 0:
        reasons.append("momentum 60j positif")
    if rel_strength_20 > 0:
        reasons.append("surperformance 20j vs benchmark")

    return _clip_score(score), reasons


def _breakout_component(snapshot: dict[str, Any]) -> tuple[float, list[str]]:
    breakout_20 = snapshot["breakout_20"]
    breakout_60 = snapshot["breakout_60"]
    volume_ratio_20 = snapshot["volume_ratio_20"]
    score = 0.0
    reasons: list[str] = []

    if breakout_20 >= 0.99:
        score += 0.35
        reasons.append("très proche du plus haut 20j")
    elif breakout_20 >= 0.97:
        score += 0.2
        reasons.append("proche du plus haut 20j")

    if breakout_60 >= 0.98:
        score += 0.25
        reasons.append("proche du plus haut 60j")

    if volume_ratio_20 >= 1.15:
        score += 0.15
        reasons.append("volume relatif supérieur à la moyenne")

    return _clip_score(score), reasons


def _pullback_component(snapshot: dict[str, Any], regime: str) -> tuple[float, list[str]]:
    rsi_14 = snapshot["rsi_14"]
    dist_sma20_pct = snapshot["dist_sma20_pct"]
    dist_sma50_pct = snapshot["dist_sma50_pct"]
    close = snapshot["close"]
    sma_50 = snapshot["sma_50"]
    score = 0.0
    reasons: list[str] = []

    if regime in {"bull_quiet", "bull_volatile"} and close > sma_50 and -0.03 <= dist_sma20_pct <= 0.02 and 40 <= rsi_14 <= 58:
        score += 0.45
        reasons.append("pullback propre dans tendance haussière")
    elif regime in {"neutral", "neutral_up"} and close > sma_50 and -0.04 <= dist_sma50_pct <= 0.03 and 38 <= rsi_14 <= 55:
        score += 0.25
        reasons.append("repli contrôlé en régime neutre")
    elif regime == "correction" and -0.06 <= dist_sma50_pct <= -0.01 and 30 <= rsi_14 <= 45:
        score += 0.12
        reasons.append("tentative de rebond technique en correction")

    return _clip_score(score), reasons


def _quality_component(snapshot: dict[str, Any]) -> tuple[float, list[str]]:
    vol_20 = snapshot["vol_20"]
    atr_pct_14 = snapshot["atr_pct_14"]
    avg_dollar_volume_20 = snapshot["avg_dollar_volume_20"]
    drawdown_20 = snapshot["drawdown_20"]
    score = 0.0
    reasons: list[str] = []

    if vol_20 < 0.25:
        score += 0.25
        reasons.append("volatilité modérée")
    elif vol_20 > 0.55:
        score -= 0.3
        reasons.append("volatilité élevée")

    if atr_pct_14 < 0.035:
        score += 0.15
        reasons.append("ATR relatif contenu")
    elif atr_pct_14 > 0.08:
        score -= 0.2
        reasons.append("ATR relatif élevé")

    if avg_dollar_volume_20 >= 1e8:
        score += 0.1
        reasons.append("très bonne liquidité")

    if drawdown_20 > -0.06:
        score += 0.1
        reasons.append("drawdown récent limité")

    return _clip_score(score), reasons


def score_snapshot(symbol: str, snapshot: dict[str, Any], context: MarketContext) -> dict[str, Any]:
    reasons: list[str] = []
    regime = (context.regime or "neutral").lower()
    weights = _strategy_weights(regime)

    trend_score, trend_reasons = _trend_component(snapshot)
    momentum_score, momentum_reasons = _momentum_component(snapshot)
    breakout_score, breakout_reasons = _breakout_component(snapshot)
    pullback_score, pullback_reasons = _pullback_component(snapshot, regime)
    quality_score, quality_reasons = _quality_component(snapshot)

    reasons.extend(trend_reasons + momentum_reasons + breakout_reasons + pullback_reasons + quality_reasons)

    ensemble_core = (
        trend_score * weights["trend"]
        + momentum_score * weights["momentum"]
        + breakout_score * weights["breakout"]
        + pullback_score * weights["pullback"]
        + quality_score * weights["quality"]
    ) * 5.5

    symbol_news_bias = float(context.symbol_news_bias.get(symbol, 0.0))
    symbol_event_bias = float(context.symbol_event_bias.get(symbol, 0.0))

    contextual = context.macro_bias + context.news_bias + context.breadth_bias + symbol_news_bias + symbol_event_bias

    if context.macro_bias != 0:
        reasons.append(f"biais macro={context.macro_bias:+.2f}")
    if context.news_bias != 0:
        reasons.append(f"biais news marché={context.news_bias:+.2f}")
    if context.breadth_bias != 0:
        reasons.append(f"biais breadth={context.breadth_bias:+.2f}")
    if symbol_news_bias != 0:
        reasons.append(f"biais news symbole={symbol_news_bias:+.2f}")
    if symbol_event_bias < 0:
        reasons.append(f"pénalité événement/earnings={symbol_event_bias:+.2f}")

    if regime == "bull_quiet":
        contextual += 0.4
        reasons.append("régime bull calme")
    elif regime == "bull_volatile":
        contextual += 0.2
        reasons.append("régime bull volatil")
    elif regime == "neutral_up":
        contextual += 0.1
        reasons.append("régime neutre haussier")
    elif regime == "bear":
        contextual -= 0.7
        reasons.append("régime bear")
    elif regime == "correction":
        contextual -= 0.45
        reasons.append("régime correction")
    elif regime == "riskoff":
        contextual -= 1.0
        reasons.append("régime risk-off")
    else:
        reasons.append("régime neutral")

    total_score = ensemble_core + contextual

    return {
        "symbol": symbol,
        "date": snapshot["date"],
        "score": round(float(total_score), 4),
        "close": round(float(snapshot["close"]), 4),
        "rsi_14": round(float(snapshot["rsi_14"]), 2),
        "vol_20": round(float(snapshot["vol_20"]), 4),
        "mom_20": round(float(snapshot["mom_20"]), 4),
        "mom_60": round(float(snapshot["mom_60"]), 4),
        "rel_strength_20": round(float(snapshot["rel_strength_20"]), 4),
        "atr_14": round(float(snapshot["atr_14"]), 4),
        "avg_dollar_volume_20": round(float(snapshot["avg_dollar_volume_20"]), 2),
        "market_news_bias": round(float(context.news_bias), 4),
        "symbol_news_bias": round(symbol_news_bias, 4),
        "event_bias": round(symbol_event_bias, 4),
        "macro_bias": round(float(context.macro_bias), 4),
        "breadth_bias": round(float(context.breadth_bias), 4),
        "trend_component": round(float(trend_score), 4),
        "momentum_component": round(float(momentum_score), 4),
        "breakout_component": round(float(breakout_score), 4),
        "pullback_component": round(float(pullback_score), 4),
        "quality_component": round(float(quality_score), 4),
        "reasons": "; ".join(dict.fromkeys(reasons)),
    }


def rank_universe(snapshots: dict[str, dict[str, Any]], context: MarketContext) -> pd.DataFrame:
    ranked = [score_snapshot(symbol, snap, context) for symbol, snap in snapshots.items()]
    df = pd.DataFrame(ranked)
    if df.empty:
        return df
    return df.sort_values(["score", "momentum_component", "trend_component", "rel_strength_20"], ascending=False).reset_index(drop=True)
