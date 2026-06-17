from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .features import add_features, latest_snapshot
from .signals import MarketContext, infer_market_regime, rank_universe


def _compute_stats(equity_curve: pd.Series) -> dict[str, Any]:
    if equity_curve.empty:
        return {
            "total_return": 0.0,
            "annualized_return": 0.0,
            "annualized_volatility": 0.0,
            "sharpe": 0.0,
            "max_drawdown": 0.0,
            "ending_equity": 1.0,
        }

    daily_returns = equity_curve.pct_change().dropna()
    total_return = float(equity_curve.iloc[-1] / equity_curve.iloc[0] - 1)
    n_days = max((equity_curve.index[-1] - equity_curve.index[0]).days, 1)
    annualized_return = float((equity_curve.iloc[-1] / equity_curve.iloc[0]) ** (365 / n_days) - 1)
    std = float(daily_returns.std()) if not daily_returns.empty else 0.0
    annualized_volatility = float(std * np.sqrt(252)) if not daily_returns.empty else 0.0
    sharpe = float((daily_returns.mean() / std) * np.sqrt(252)) if std > 0 else 0.0
    running_max = equity_curve.cummax()
    drawdown = equity_curve / running_max - 1
    max_drawdown = float(drawdown.min())

    return {
        "total_return": round(total_return, 4),
        "annualized_return": round(annualized_return, 4),
        "annualized_volatility": round(annualized_volatility, 4),
        "sharpe": round(sharpe, 4),
        "max_drawdown": round(max_drawdown, 4),
        "ending_equity": round(float(equity_curve.iloc[-1]), 4),
    }


def run_rotation_backtest(
    market_data: dict[str, pd.DataFrame],
    benchmark_symbol: str,
    max_positions: int,
    rebalance_frequency: str,
    transaction_cost_bps: float,
    context: MarketContext,
    regime_override: str | None = None,
    min_score: float = 1.5,
) -> tuple[pd.Series, dict[str, Any]]:
    if benchmark_symbol not in market_data:
        return pd.Series(dtype=float), _compute_stats(pd.Series(dtype=float))

    benchmark_raw = market_data[benchmark_symbol]
    benchmark_features = add_features(benchmark_raw, None)
    if benchmark_features.empty:
        return pd.Series(dtype=float), _compute_stats(pd.Series(dtype=float))

    feature_map: dict[str, pd.DataFrame] = {}
    for symbol, df in market_data.items():
        feats = add_features(df, benchmark_raw)
        if not feats.empty:
            feature_map[symbol] = feats

    rebalance_dates = benchmark_features.resample(rebalance_frequency).last().dropna().index
    rebalance_dates = [d for d in rebalance_dates if d in benchmark_features.index]
    if len(rebalance_dates) < 2:
        return pd.Series(dtype=float), _compute_stats(pd.Series(dtype=float))

    equity = 1.0
    records: list[dict[str, Any]] = []
    previous_selection: set[str] = set()

    for i in range(len(rebalance_dates) - 1):
        rebalance_date = rebalance_dates[i]
        next_rebalance_date = rebalance_dates[i + 1]

        snapshots: dict[str, dict[str, Any]] = {}
        for symbol, feats in feature_map.items():
            hist = feats.loc[:rebalance_date]
            if hist.empty:
                continue
            snapshots[symbol] = latest_snapshot(hist)

        regime = infer_market_regime(benchmark_features.loc[:rebalance_date], regime_override)
        period_context = MarketContext(
            macro_bias=context.macro_bias,
            news_bias=context.news_bias,
            regime=regime,
        )
        ranked = rank_universe(snapshots, period_context)
        selected = ranked[ranked["score"] >= min_score].head(max_positions)["symbol"].tolist() if not ranked.empty else []

        current_selection = set(selected)
        union = current_selection | previous_selection
        turnover = len(current_selection ^ previous_selection) / len(union) if union else 0.0
        period_dates = benchmark_features.loc[
            (benchmark_features.index > rebalance_date) & (benchmark_features.index <= next_rebalance_date)
        ].index

        for j, date in enumerate(period_dates):
            symbol_returns: list[float] = []
            for symbol in selected:
                feats = feature_map.get(symbol)
                if feats is None or date not in feats.index:
                    continue
                daily_ret = feats.loc[date, "ret_1d"]
                if pd.notna(daily_ret):
                    symbol_returns.append(float(daily_ret))

            avg_ret = float(np.mean(symbol_returns)) if symbol_returns else 0.0
            cost = (transaction_cost_bps / 10000.0) * turnover if j == 0 else 0.0
            equity *= 1 + avg_ret - cost
            records.append(
                {
                    "date": date,
                    "equity": equity,
                    "n_positions": len(selected),
                    "selection": ",".join(selected),
                }
            )

        previous_selection = current_selection

    equity_curve = pd.DataFrame(records).set_index("date")["equity"] if records else pd.Series(dtype=float)
    stats = _compute_stats(equity_curve)
    return equity_curve, stats
