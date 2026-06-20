from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class MacroConfig:
    enabled: bool = True
    series: dict[str, str] = field(
        default_factory=lambda: {
            "cpi": "CPIAUCSL",
            "unemployment": "UNRATE",
            "fed_funds": "FEDFUNDS",
            "vix": "VIXCLS",
            "ten_year_yield": "DGS10",
            "yield_curve_10y_2y": "T10Y2Y",
        }
    )


@dataclass
class NewsConfig:
    enabled: bool = True
    max_articles_per_symbol: int = 8
    market_symbols: list[str] = field(default_factory=list)


@dataclass
class EarningsConfig:
    enabled: bool = True
    days_ahead: int = 14
    penalty_days_high: int = 3
    penalty_days_medium: int = 7


@dataclass
class BrokerConfig:
    mode: str = "manual"
    currency: str = "USD"
    exchange: str = "SMART"
    ibkr_host: str = "127.0.0.1"
    ibkr_port: int = 7497
    client_id: int = 7
    account: Optional[str] = None
    paper_only: bool = True


@dataclass
class StrategyConfig:
    min_score: float = 1.5
    use_breadth_filter: bool = True
    breadth_risk_off_threshold: float = -0.35
    breadth_full_risk_threshold: float = 0.25
    allow_long_only_in_bear: bool = False


@dataclass
class PortfolioConfig:
    max_pairwise_correlation: float = 0.8
    min_cash_buffer: float = 0.1
    rebalance_to_cash_in_bear: bool = True
    max_sector_positions: int = 2
    max_sector_allocation_pct: float = 0.35
    max_gross_exposure_pct: float = 0.9


@dataclass
class ValidationConfig:
    min_eligible_symbols: int = 5
    min_ranked_symbols: int = 3
    max_data_error_count: int = 10


@dataclass
class WalkForwardConfig:
    enabled: bool = True
    train_months: int = 12
    test_months: int = 3
    max_windows: int = 8


@dataclass
class PreTradeConfig:
    max_total_risk_pct: float = 0.04
    max_single_name_risk_pct: float = 0.015
    max_order_adv_fraction: float = 0.02
    max_stop_pct: float = 0.12


@dataclass
class MetaRiskConfig:
    enabled: bool = True
    min_health_score: int = 70
    min_walkforward_windows: int = 3
    min_walkforward_mean_sharpe: float = -0.1
    max_stress_loss_pct: float = 0.12
    hard_block_breadth_threshold: float = -0.55


@dataclass
class MonteCarloConfig:
    enabled: bool = True
    n_sims: int = 500
    horizon_days: int = 252
    random_seed: int = 42


@dataclass
class KillSwitchConfig:
    enabled: bool = True
    min_health_score: int = 55
    min_meta_confidence: int = 45
    max_prob_negative_return: float = 0.65
    max_stress_loss_pct: float = 0.18
    max_order_count: int = 8


@dataclass
class SensitivityConfig:
    enabled: bool = True
    min_score_step: float = 0.5
    max_positions_step: int = 2


@dataclass
class DataQualityConfig:
    min_history_bars: int = 220
    max_stale_days: int = 7
    min_coverage_ratio: float = 0.8


@dataclass
class DatabaseConfig:
    path: str = "data/trading_agent.sqlite"


@dataclass
class AppConfig:
    universe: list[str]
    benchmark: str
    start_date: str
    initial_capital: float
    max_positions: int
    risk_per_trade: float
    max_position_weight: float
    max_portfolio_drawdown: float
    min_avg_dollar_volume: float
    min_price: float
    rebalance_frequency: str
    transaction_cost_bps: float
    macro_bias: float = 0.0
    news_bias: float = 0.0
    regime_override: Optional[str] = None
    report_dir: str = "reports"
    macro: MacroConfig = field(default_factory=MacroConfig)
    news: NewsConfig = field(default_factory=NewsConfig)
    earnings: EarningsConfig = field(default_factory=EarningsConfig)
    broker: BrokerConfig = field(default_factory=BrokerConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    portfolio: PortfolioConfig = field(default_factory=PortfolioConfig)
    validation: ValidationConfig = field(default_factory=ValidationConfig)
    walkforward: WalkForwardConfig = field(default_factory=WalkForwardConfig)
    pretrade: PreTradeConfig = field(default_factory=PreTradeConfig)
    metarisk: MetaRiskConfig = field(default_factory=MetaRiskConfig)
    montecarlo: MonteCarloConfig = field(default_factory=MonteCarloConfig)
    killswitch: KillSwitchConfig = field(default_factory=KillSwitchConfig)
    sensitivity: SensitivityConfig = field(default_factory=SensitivityConfig)
    data_quality: DataQualityConfig = field(default_factory=DataQualityConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)


def load_config(path: str | Path) -> AppConfig:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    macro = MacroConfig(**raw.get("macro", {}))
    news = NewsConfig(**raw.get("news", {}))
    earnings = EarningsConfig(**raw.get("earnings", {}))
    broker = BrokerConfig(**raw.get("broker", {}))
    strategy = StrategyConfig(**raw.get("strategy", {}))
    portfolio = PortfolioConfig(**raw.get("portfolio", {}))
    validation = ValidationConfig(**raw.get("validation", {}))
    walkforward = WalkForwardConfig(**raw.get("walkforward", {}))
    pretrade = PreTradeConfig(**raw.get("pretrade", {}))
    metarisk = MetaRiskConfig(**raw.get("metarisk", {}))
    montecarlo = MonteCarloConfig(**raw.get("montecarlo", {}))
    killswitch = KillSwitchConfig(**raw.get("killswitch", {}))
    sensitivity = SensitivityConfig(**raw.get("sensitivity", {}))
    data_quality = DataQualityConfig(**raw.get("data_quality", {}))
    database = DatabaseConfig(**raw.get("database", {}))

    base: dict[str, Any] = {
        k: v
        for k, v in raw.items()
        if k not in {"macro", "news", "earnings", "broker", "strategy", "portfolio", "validation", "walkforward", "pretrade", "metarisk", "montecarlo", "killswitch", "sensitivity", "data_quality", "database"}
    }
    return AppConfig(
        **base,
        macro=macro,
        news=news,
        earnings=earnings,
        broker=broker,
        strategy=strategy,
        portfolio=portfolio,
        validation=validation,
        walkforward=walkforward,
        pretrade=pretrade,
        metarisk=metarisk,
        montecarlo=montecarlo,
        killswitch=killswitch,
        sensitivity=sensitivity,
        data_quality=data_quality,
        database=database,
    )
