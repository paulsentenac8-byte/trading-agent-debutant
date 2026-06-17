from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd

from .backtest import run_rotation_backtest
from .config import SensitivityConfig
from .signals import MarketContext


@dataclass
class SensitivitySummary:
    enabled: bool
    combinations_tested: int
    positive_return_ratio: float
    positive_sharpe_ratio: float
    median_annualized_return: float
    median_sharpe: float
    best_config: dict[str, Any]
    notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def run_sensitivity_analysis(
    market_data: dict[str, pd.DataFrame],
    benchmark_symbol: str,
    rebalance_frequency: str,
    transaction_cost_bps: float,
    context: MarketContext,
    regime_override: str | None,
    base_min_score: float,
    base_max_positions: int,
    config: SensitivityConfig,
) -> tuple[SensitivitySummary, pd.DataFrame]:
    if not config.enabled:
        return SensitivitySummary(False, 0, 0.0, 0.0, 0.0, 0.0, {}, ["Sensitivity analysis désactivée."]), pd.DataFrame()

    min_score_values = [max(0.5, base_min_score - config.min_score_step), base_min_score, base_min_score + config.min_score_step]
    max_pos_values = sorted(set([max(2, base_max_positions - config.max_positions_step), base_max_positions, base_max_positions + config.max_positions_step]))

    rows: list[dict[str, Any]] = []
    for min_score in min_score_values:
        for max_positions in max_pos_values:
            _, stats = run_rotation_backtest(
                market_data=market_data,
                benchmark_symbol=benchmark_symbol,
                max_positions=max_positions,
                rebalance_frequency=rebalance_frequency,
                transaction_cost_bps=transaction_cost_bps,
                context=context,
                regime_override=regime_override,
                min_score=min_score,
            )
            rows.append(
                {
                    "min_score": round(float(min_score), 4),
                    "max_positions": int(max_positions),
                    "annualized_return": float(stats.get("annualized_return", 0.0)),
                    "sharpe": float(stats.get("sharpe", 0.0)),
                    "max_drawdown": float(stats.get("max_drawdown", 0.0)),
                }
            )

    df = pd.DataFrame(rows)
    if df.empty:
        return SensitivitySummary(False, 0, 0.0, 0.0, 0.0, 0.0, {}, ["Aucune combinaison testée."]), df

    best = df.sort_values(["sharpe", "annualized_return"], ascending=False).iloc[0].to_dict()
    summary = SensitivitySummary(
        enabled=True,
        combinations_tested=int(len(df)),
        positive_return_ratio=round(float((df["annualized_return"] > 0).mean()), 4),
        positive_sharpe_ratio=round(float((df["sharpe"] > 0).mean()), 4),
        median_annualized_return=round(float(df["annualized_return"].median()), 4),
        median_sharpe=round(float(df["sharpe"].median()), 4),
        best_config={k: (round(v, 4) if isinstance(v, float) else v) for k, v in best.items()},
        notes=[
            "La sensibilité mesure si la stratégie reste correcte quand on bouge légèrement les paramètres.",
            "Une stratégie fragile change brutalement de qualité dès qu'on modifie un paramètre.",
        ],
    )
    return summary, df
