from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd


def compute_rsi(series: pd.Series, window: int = 14) -> pd.Series:
    delta = series.diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)
    avg_gain = gains.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    avg_loss = losses.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


def compute_atr(df: pd.DataFrame, window: int = 14) -> pd.Series:
    high_low = df["High"] - df["Low"]
    high_close = (df["High"] - df["Adj Close"].shift(1)).abs()
    low_close = (df["Low"] - df["Adj Close"].shift(1)).abs()
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return true_range.rolling(window).mean()


def _rolling_zscore(series: pd.Series, window: int = 20) -> pd.Series:
    mean = series.rolling(window).mean()
    std = series.rolling(window).std()
    return (series - mean) / std.replace(0, np.nan)


def add_features(df: pd.DataFrame, benchmark_df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    out = df.copy()
    px = out["Adj Close"]

    out["ret_1d"] = px.pct_change()
    out["sma_20"] = px.rolling(20).mean()
    out["sma_50"] = px.rolling(50).mean()
    out["sma_200"] = px.rolling(200).mean()
    out["mom_20"] = px.pct_change(20, fill_method=None)
    out["mom_60"] = px.pct_change(60, fill_method=None)
    out["mom_120"] = px.pct_change(120, fill_method=None)
    out["vol_20"] = out["ret_1d"].rolling(20).std() * np.sqrt(252)
    out["avg_dollar_volume_20"] = (px * out["Volume"]).rolling(20).mean()
    out["rsi_14"] = compute_rsi(px, 14)
    out["atr_14"] = compute_atr(out, 14)
    out["atr_pct_14"] = out["atr_14"] / px.replace(0, np.nan)
    out["breakout_20"] = px / px.rolling(20).max()
    out["breakout_60"] = px / px.rolling(60).max()
    out["dist_sma20_pct"] = px / out["sma_20"] - 1
    out["dist_sma50_pct"] = px / out["sma_50"] - 1
    out["dist_sma200_pct"] = px / out["sma_200"] - 1
    out["drawdown_20"] = px / px.rolling(20).max() - 1
    out["drawdown_60"] = px / px.rolling(60).max() - 1
    out["volume_ratio_20"] = out["Volume"] / out["Volume"].rolling(20).mean()
    out["price_zscore_20"] = _rolling_zscore(px, 20)
    out["sma50_slope_20"] = out["sma_50"].pct_change(20, fill_method=None)
    out["sma200_slope_20"] = out["sma_200"].pct_change(20, fill_method=None)

    if benchmark_df is not None and not benchmark_df.empty:
        bench = benchmark_df[["Adj Close"]].rename(columns={"Adj Close": "benchmark_close"}).copy()
        bench["benchmark_mom_20"] = bench["benchmark_close"].pct_change(20, fill_method=None)
        bench["benchmark_mom_60"] = bench["benchmark_close"].pct_change(60, fill_method=None)
        out = out.join(bench[["benchmark_mom_20", "benchmark_mom_60"]], how="left")
        out["benchmark_mom_20"] = out["benchmark_mom_20"].ffill()
        out["benchmark_mom_60"] = out["benchmark_mom_60"].ffill()
        out["rel_strength_20"] = out["mom_20"] - out["benchmark_mom_20"]
        out["rel_strength_60"] = out["mom_60"] - out["benchmark_mom_60"]
    else:
        out["benchmark_mom_20"] = 0.0
        out["benchmark_mom_60"] = 0.0
        out["rel_strength_20"] = 0.0
        out["rel_strength_60"] = 0.0

    out = out.replace([np.inf, -np.inf], np.nan)
    return out.dropna()


def latest_snapshot(df: pd.DataFrame) -> dict:
    row = df.iloc[-1]
    return {
        "date": str(df.index[-1].date()),
        "close": float(row["Adj Close"]),
        "sma_20": float(row["sma_20"]),
        "sma_50": float(row["sma_50"]),
        "sma_200": float(row["sma_200"]),
        "mom_20": float(row["mom_20"]),
        "mom_60": float(row["mom_60"]),
        "mom_120": float(row["mom_120"]),
        "vol_20": float(row["vol_20"]),
        "avg_dollar_volume_20": float(row["avg_dollar_volume_20"]),
        "rsi_14": float(row["rsi_14"]),
        "atr_14": float(row["atr_14"]),
        "atr_pct_14": float(row["atr_pct_14"]),
        "breakout_20": float(row["breakout_20"]),
        "breakout_60": float(row["breakout_60"]),
        "rel_strength_20": float(row["rel_strength_20"]),
        "rel_strength_60": float(row["rel_strength_60"]),
        "dist_sma20_pct": float(row["dist_sma20_pct"]),
        "dist_sma50_pct": float(row["dist_sma50_pct"]),
        "dist_sma200_pct": float(row["dist_sma200_pct"]),
        "drawdown_20": float(row["drawdown_20"]),
        "drawdown_60": float(row["drawdown_60"]),
        "volume_ratio_20": float(row["volume_ratio_20"]),
        "price_zscore_20": float(row["price_zscore_20"]),
        "sma50_slope_20": float(row["sma50_slope_20"]),
        "sma200_slope_20": float(row["sma200_slope_20"]),
    }
