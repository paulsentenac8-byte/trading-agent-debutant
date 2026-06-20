from __future__ import annotations

from collections import defaultdict

import pandas as pd

SECTOR_MAP = {
    "SPY": "Broad Market",
    "QQQ": "Growth / Nasdaq",
    "IWM": "Small Caps",
    "DIA": "Dow / Industrials",
    "XLK": "Technology",
    "XLF": "Financials",
    "XLV": "Healthcare",
    "XLI": "Industrials",
    "XLE": "Energy",
    "XLP": "Consumer Staples",
    "AAPL": "Technology",
    "MSFT": "Technology",
    "NVDA": "Technology",
    "AMZN": "Consumer / Tech",
    "META": "Technology",
    "GOOGL": "Technology",
    "TSLA": "Consumer / Auto",
    "JPM": "Financials",
    "XOM": "Energy",
    "JNJ": "Healthcare",
}


def get_sector(symbol: str) -> str:
    return SECTOR_MAP.get(symbol.upper(), "Unknown")


def apply_sector_limits(trade_plan: pd.DataFrame, max_sector_positions: int = 2) -> pd.DataFrame:
    if trade_plan.empty:
        return trade_plan

    out = trade_plan.copy()
    out["sector"] = out["symbol"].map(get_sector)
    counts: defaultdict[str, int] = defaultdict(int)
    kept_rows = []

    for _, row in out.sort_values("score", ascending=False).iterrows():
        sector = str(row["sector"])
        if counts[sector] >= max_sector_positions:
            continue
        counts[sector] += 1
        kept_rows.append(row)

    if not kept_rows:
        return pd.DataFrame(columns=out.columns)

    result = pd.DataFrame(kept_rows).reset_index(drop=True)
    result["portfolio_note"] = result.get("portfolio_note", "")
    result["portfolio_note"] = result["portfolio_note"].astype(str) + " | limite sectorielle appliquée"
    return result
