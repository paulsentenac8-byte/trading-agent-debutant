from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import timedelta
from typing import Any

import numpy as np
import pandas as pd

from .config import EarningsConfig


@dataclass
class EarningsContext:
    summary: list[str]
    symbol_penalty: dict[str, float]
    calendar: list[dict[str, Any]]
    errors: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _coerce_event_rows(symbol: str, raw: pd.DataFrame) -> list[dict[str, Any]]:
    if raw is None or raw.empty:
        return []
    df = raw.copy()
    if not isinstance(df.index, pd.DatetimeIndex):
        try:
            df.index = pd.to_datetime(df.index, errors="coerce")
        except Exception:
            return []
    df = df[~df.index.isna()].sort_index()
    records: list[dict[str, Any]] = []
    for date, row in df.iterrows():
        eps_est = row.get("EPS Estimate") if hasattr(row, "get") else None
        reported_eps = row.get("Reported EPS") if hasattr(row, "get") else None
        surprise = row.get("Surprise(%)") if hasattr(row, "get") else None
        records.append(
            {
                "symbol": symbol,
                "earnings_date": pd.Timestamp(date).strftime("%Y-%m-%d"),
                "eps_estimate": None if pd.isna(eps_est) else float(eps_est),
                "reported_eps": None if pd.isna(reported_eps) else float(reported_eps),
                "surprise_pct": None if pd.isna(surprise) else float(surprise),
            }
        )
    return records


def fetch_symbol_earnings(symbol: str) -> list[dict[str, Any]]:
    try:
        import yfinance as yf
    except ImportError as exc:
        raise ImportError("yfinance n'est pas installé.") from exc

    ticker = yf.Ticker(symbol)

    try:
        if hasattr(ticker, "get_earnings_dates"):
            raw = ticker.get_earnings_dates(limit=12)
            if isinstance(raw, pd.DataFrame):
                return _coerce_event_rows(symbol, raw)
    except Exception:
        pass

    try:
        cal = getattr(ticker, "calendar", None)
        if isinstance(cal, pd.DataFrame) and not cal.empty:
            rows: list[dict[str, Any]] = []
            for col in cal.columns:
                dt = pd.to_datetime(col, errors="coerce")
                if pd.notna(dt):
                    rows.append(
                        {
                            "symbol": symbol,
                            "earnings_date": dt.strftime("%Y-%m-%d"),
                            "eps_estimate": None,
                            "reported_eps": None,
                            "surprise_pct": None,
                        }
                    )
            return rows
    except Exception:
        pass

    return []


def build_earnings_context(symbols: list[str], config: EarningsConfig) -> EarningsContext:
    if not config.enabled:
        return EarningsContext(["Earnings désactivés dans la configuration."], {}, [], [])

    now = pd.Timestamp.utcnow().normalize().tz_localize(None)
    horizon = now + timedelta(days=config.days_ahead)
    calendar: list[dict[str, Any]] = []
    symbol_penalty: dict[str, float] = {}
    errors: list[str] = []

    for symbol in symbols:
        try:
            records = fetch_symbol_earnings(symbol)
        except Exception as exc:  # pragma: no cover - dépend du réseau
            errors.append(f"{symbol}: {exc}")
            records = []

        future_events: list[dict[str, Any]] = []
        for record in records:
            event_date = pd.to_datetime(record.get("earnings_date"), errors="coerce")
            if pd.isna(event_date):
                continue
            event_date = pd.Timestamp(event_date).tz_localize(None)
            if now <= event_date <= horizon:
                days_to_event = int((event_date - now).days)
                enriched = dict(record)
                enriched["days_to_event"] = days_to_event
                future_events.append(enriched)

        future_events = sorted(future_events, key=lambda x: x["days_to_event"])
        calendar.extend(future_events)

        penalty = 0.0
        if future_events:
            days = int(future_events[0]["days_to_event"])
            if days <= config.penalty_days_high:
                penalty = -0.8
            elif days <= config.penalty_days_medium:
                penalty = -0.5
            else:
                penalty = -0.2
        symbol_penalty[symbol] = penalty

    calendar = sorted(calendar, key=lambda x: (x["days_to_event"], x["symbol"]))

    summary: list[str] = []
    if calendar:
        nearest = calendar[: min(len(calendar), 8)]
        summary.append(
            "Earnings proches: " + ", ".join(f"{item['symbol']} (J-{item['days_to_event']})" for item in nearest)
        )
    else:
        summary.append("Aucun earnings proche détecté sur l'horizon configuré.")

    risky = [f"{symbol} ({penalty:+.1f})" for symbol, penalty in symbol_penalty.items() if penalty < 0]
    if risky:
        summary.append("Pénalités events: " + ", ".join(risky[:10]))

    return EarningsContext(summary=summary, symbol_penalty=symbol_penalty, calendar=calendar, errors=errors)
