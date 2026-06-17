from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd

from .config import MonteCarloConfig


@dataclass
class MonteCarloSummary:
    enabled: bool
    simulations: int
    horizon_days: int
    mean_terminal_return: float
    p05_terminal_return: float
    p50_terminal_return: float
    p95_terminal_return: float
    mean_max_drawdown: float
    p95_max_drawdown: float
    prob_negative_return: float
    prob_drawdown_worse_than_20pct: float
    notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _max_drawdown_from_returns(returns: np.ndarray) -> float:
    equity = np.cumprod(1 + returns)
    running_max = np.maximum.accumulate(equity)
    drawdowns = equity / running_max - 1
    return float(drawdowns.min()) if len(drawdowns) > 0 else 0.0


def run_monte_carlo_analysis(equity_curve: pd.Series, config: MonteCarloConfig) -> MonteCarloSummary:
    if not config.enabled or equity_curve.empty:
        return MonteCarloSummary(False, 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, ["Monte Carlo désactivé ou courbe d'équité vide."])

    returns = equity_curve.pct_change().dropna()
    if len(returns) < 30:
        return MonteCarloSummary(False, 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, ["Pas assez de données pour Monte Carlo."])

    horizon = min(int(config.horizon_days), len(returns))
    returns_array = returns.to_numpy()
    rng = np.random.default_rng(config.random_seed)

    terminal_returns = []
    max_drawdowns = []
    for _ in range(int(config.n_sims)):
        sampled = rng.choice(returns_array, size=horizon, replace=True)
        terminal = float(np.prod(1 + sampled) - 1)
        mdd = _max_drawdown_from_returns(sampled)
        terminal_returns.append(terminal)
        max_drawdowns.append(mdd)

    terminal_arr = np.array(terminal_returns)
    mdd_arr = np.array(max_drawdowns)

    return MonteCarloSummary(
        enabled=True,
        simulations=int(config.n_sims),
        horizon_days=int(horizon),
        mean_terminal_return=round(float(np.mean(terminal_arr)), 4),
        p05_terminal_return=round(float(np.quantile(terminal_arr, 0.05)), 4),
        p50_terminal_return=round(float(np.quantile(terminal_arr, 0.50)), 4),
        p95_terminal_return=round(float(np.quantile(terminal_arr, 0.95)), 4),
        mean_max_drawdown=round(float(np.mean(mdd_arr)), 4),
        p95_max_drawdown=round(float(np.quantile(mdd_arr, 0.95)), 4),
        prob_negative_return=round(float(np.mean(terminal_arr < 0)), 4),
        prob_drawdown_worse_than_20pct=round(float(np.mean(mdd_arr <= -0.20)), 4),
        notes=[
            "Le Monte Carlo bootstrap les rendements historiques pour estimer une distribution de résultats plausibles.",
            "Ce n'est pas une prévision, mais un outil de robustesse et de sizing.",
        ],
    )
