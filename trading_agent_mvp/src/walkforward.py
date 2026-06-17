from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd
from pandas.tseries.offsets import DateOffset

from .backtest import run_rotation_backtest
from .config import StrategyConfig
from .signals import MarketContext


@dataclass
class WalkForwardSummary:
    enabled: bool
    windows_tested: int
    best_parameter_frequency: dict[str, int]
    mean_oos_sharpe: float
    mean_oos_return: float
    median_oos_return: float
    notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _slice_market_data(market_data: dict[str, pd.DataFrame], start: pd.Timestamp, end: pd.Timestamp) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    for symbol, df in market_data.items():
        sliced = df.loc[(df.index >= start) & (df.index <= end)].copy()
        if not sliced.empty:
            out[symbol] = sliced
    return out


def run_walkforward_analysis(
    market_data: dict[str, pd.DataFrame],
    benchmark_symbol: str,
    rebalance_frequency: str,
    transaction_cost_bps: float,
    context: MarketContext,
    regime_override: str | None,
    strategy_config: StrategyConfig,
    max_positions_default: int,
    train_months: int = 12,
    test_months: int = 3,
    max_windows: int = 8,
) -> tuple[WalkForwardSummary, pd.DataFrame]:
    if benchmark_symbol not in market_data:
        return WalkForwardSummary(False, 0, {}, 0.0, 0.0, 0.0, ["Benchmark absent pour walk-forward."]), pd.DataFrame()

    benchmark_df = market_data[benchmark_symbol]
    if benchmark_df.empty:
        return WalkForwardSummary(False, 0, {}, 0.0, 0.0, 0.0, ["Benchmark vide pour walk-forward."]), pd.DataFrame()

    all_dates = benchmark_df.index.sort_values()
    start_date = pd.Timestamp(all_dates.min())
    end_date = pd.Timestamp(all_dates.max())

    score_grid = [max(strategy_config.min_score - 0.5, 0.5), strategy_config.min_score, strategy_config.min_score + 0.5]
    position_grid = sorted(set([max(2, max_positions_default - 2), max_positions_default, max_positions_default + 2]))

    windows: list[dict[str, Any]] = []
    current_train_start = start_date
    tested = 0

    while tested < max_windows:
        train_end = current_train_start + DateOffset(months=train_months)
        test_end = train_end + DateOffset(months=test_months)
        if test_end >= end_date:
            break

        train_data = _slice_market_data(market_data, current_train_start, train_end)
        test_data = _slice_market_data(market_data, train_end, test_end)

        best_params: tuple[float, int] | None = None
        best_train_sharpe = -999.0
        best_train_return = -999.0

        for min_score in score_grid:
            for max_positions in position_grid:
                _, train_stats = run_rotation_backtest(
                    market_data=train_data,
                    benchmark_symbol=benchmark_symbol,
                    max_positions=max_positions,
                    rebalance_frequency=rebalance_frequency,
                    transaction_cost_bps=transaction_cost_bps,
                    context=context,
                    regime_override=regime_override,
                    min_score=min_score,
                )
                sharpe = float(train_stats.get("sharpe", 0.0))
                ann_return = float(train_stats.get("annualized_return", 0.0))
                if sharpe > best_train_sharpe or (sharpe == best_train_sharpe and ann_return > best_train_return):
                    best_train_sharpe = sharpe
                    best_train_return = ann_return
                    best_params = (float(min_score), int(max_positions))

        if best_params is None:
            break

        oos_equity, oos_stats = run_rotation_backtest(
            market_data=test_data,
            benchmark_symbol=benchmark_symbol,
            max_positions=best_params[1],
            rebalance_frequency=rebalance_frequency,
            transaction_cost_bps=transaction_cost_bps,
            context=context,
            regime_override=regime_override,
            min_score=best_params[0],
        )

        windows.append(
            {
                "train_start": str(pd.Timestamp(current_train_start).date()),
                "train_end": str(pd.Timestamp(train_end).date()),
                "test_end": str(pd.Timestamp(test_end).date()),
                "best_min_score": best_params[0],
                "best_max_positions": best_params[1],
                "train_best_sharpe": round(best_train_sharpe, 4),
                "train_best_annualized_return": round(best_train_return, 4),
                "oos_total_return": round(float(oos_stats.get("total_return", 0.0)), 4),
                "oos_annualized_return": round(float(oos_stats.get("annualized_return", 0.0)), 4),
                "oos_sharpe": round(float(oos_stats.get("sharpe", 0.0)), 4),
                "oos_max_drawdown": round(float(oos_stats.get("max_drawdown", 0.0)), 4),
                "oos_days": int(len(oos_equity)),
            }
        )
        tested += 1
        current_train_start = current_train_start + DateOffset(months=test_months)

    windows_df = pd.DataFrame(windows)
    if windows_df.empty:
        return WalkForwardSummary(False, 0, {}, 0.0, 0.0, 0.0, ["Pas assez de données pour un walk-forward exploitable."]), windows_df

    param_counts = (
        windows_df.assign(param_key=windows_df["best_min_score"].astype(str) + "|" + windows_df["best_max_positions"].astype(str))["param_key"]
        .value_counts()
        .to_dict()
    )

    summary = WalkForwardSummary(
        enabled=True,
        windows_tested=int(len(windows_df)),
        best_parameter_frequency={str(k): int(v) for k, v in param_counts.items()},
        mean_oos_sharpe=round(float(windows_df["oos_sharpe"].mean()), 4),
        mean_oos_return=round(float(windows_df["oos_annualized_return"].mean()), 4),
        median_oos_return=round(float(windows_df["oos_annualized_return"].median()), 4),
        notes=[
            "Le walk-forward choisit les paramètres sur une fenêtre train puis les teste hors échantillon.",
            "Un bon résultat walk-forward est plus crédible qu'un simple backtest global.",
        ],
    )
    return summary, windows_df
