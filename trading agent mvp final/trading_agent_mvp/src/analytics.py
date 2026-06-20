from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class PerformanceDiagnostics:
    strategy_total_return: float
    benchmark_total_return: float
    excess_return: float
    strategy_annualized_return: float
    benchmark_annualized_return: float
    strategy_max_drawdown: float
    benchmark_max_drawdown: float
    information_ratio: float
    beta_proxy: float
    correlation_to_benchmark: float
    monthly_win_rate: float
    notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _max_drawdown(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    running_max = equity.cummax()
    dd = equity / running_max - 1
    return float(dd.min())


def _annualized_return(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    n_days = max((equity.index[-1] - equity.index[0]).days, 1)
    return float((equity.iloc[-1] / equity.iloc[0]) ** (365 / n_days) - 1)


def build_benchmark_equity(benchmark_df: pd.DataFrame, target_index: pd.Index) -> pd.Series:
    if benchmark_df.empty or target_index.empty:
        return pd.Series(dtype=float)
    returns = benchmark_df["Adj Close"].pct_change().reindex(target_index).fillna(0.0)
    equity = (1 + returns).cumprod()
    equity.iloc[0] = 1.0
    return equity


def build_performance_diagnostics(equity_curve: pd.Series, benchmark_df: pd.DataFrame) -> PerformanceDiagnostics:
    if equity_curve.empty:
        return PerformanceDiagnostics(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, ["Aucune courbe d'équité disponible."])

    benchmark_equity = build_benchmark_equity(benchmark_df, equity_curve.index)
    strategy_returns = equity_curve.pct_change().dropna()
    benchmark_returns = benchmark_equity.pct_change().dropna()
    aligned = pd.concat([strategy_returns.rename("strategy"), benchmark_returns.rename("benchmark")], axis=1).dropna()

    strat_total = float(equity_curve.iloc[-1] / equity_curve.iloc[0] - 1)
    bench_total = float(benchmark_equity.iloc[-1] / benchmark_equity.iloc[0] - 1) if not benchmark_equity.empty else 0.0
    strat_ann = _annualized_return(equity_curve)
    bench_ann = _annualized_return(benchmark_equity) if not benchmark_equity.empty else 0.0
    strat_mdd = _max_drawdown(equity_curve)
    bench_mdd = _max_drawdown(benchmark_equity) if not benchmark_equity.empty else 0.0

    if aligned.empty:
        info_ratio = 0.0
        beta_proxy = 0.0
        corr = 0.0
        monthly_win_rate = 0.0
    else:
        active = aligned["strategy"] - aligned["benchmark"]
        info_ratio = float((active.mean() / active.std()) * np.sqrt(252)) if float(active.std()) > 0 else 0.0
        beta_proxy = float(aligned["strategy"].cov(aligned["benchmark"]) / aligned["benchmark"].var()) if float(aligned["benchmark"].var()) > 0 else 0.0
        corr = float(aligned["strategy"].corr(aligned["benchmark"])) if len(aligned) > 2 else 0.0
        monthly = equity_curve.resample("ME").last().pct_change().dropna()
        monthly_win_rate = float((monthly > 0).mean()) if not monthly.empty else 0.0

    return PerformanceDiagnostics(
        strategy_total_return=round(strat_total, 4),
        benchmark_total_return=round(bench_total, 4),
        excess_return=round(strat_total - bench_total, 4),
        strategy_annualized_return=round(strat_ann, 4),
        benchmark_annualized_return=round(bench_ann, 4),
        strategy_max_drawdown=round(strat_mdd, 4),
        benchmark_max_drawdown=round(bench_mdd, 4),
        information_ratio=round(info_ratio, 4),
        beta_proxy=round(beta_proxy, 4),
        correlation_to_benchmark=round(corr, 4),
        monthly_win_rate=round(monthly_win_rate, 4),
        notes=[
            "Le benchmark sert à mesurer si le moteur apporte une valeur ajoutée relative.",
            "Le beta_proxy et l'information ratio sont des indicateurs simplifiés, pas une mesure institutionnelle exhaustive.",
        ],
    )
