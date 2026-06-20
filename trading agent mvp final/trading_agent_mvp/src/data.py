from __future__ import annotations

import time
from datetime import datetime
from typing import Dict

import pandas as pd


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        if len(df.columns.levels) >= 2:
            level0 = [str(x).strip().title() for x in df.columns.get_level_values(0)]
            df.columns = level0
        else:
            df.columns = [str(c).strip().title() for c in df.columns]
    else:
        rename_map = {c: str(c).strip().title() for c in df.columns}
        df = df.rename(columns=rename_map)

    expected = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]
    for col in expected:
        if col not in df.columns and col != "Adj Close":
            raise ValueError(f"Colonne manquante dans les données: {col}")
    if "Adj Close" not in df.columns:
        df["Adj Close"] = df["Close"]
    out = df[["Open", "High", "Low", "Close", "Adj Close", "Volume"]].copy()
    out = out.loc[:, ~out.columns.duplicated()]
    return out.dropna()


def _download_one_symbol(symbol: str, start_date: str, end_date: str, retries: int = 3, sleep_seconds: float = 1.5) -> pd.DataFrame | None:
    try:
        import yfinance as yf
    except ImportError as exc:
        raise ImportError("yfinance n'est pas installé. Lance `pip install -r requirements.txt`.") from exc

    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            df = yf.download(symbol, start=start_date, end=end_date, auto_adjust=False, progress=False, threads=False)
            if df is None or df.empty:
                time.sleep(sleep_seconds)
                continue
            df = _normalize_columns(df)
            df.index = pd.to_datetime(df.index)
            df = df.sort_index()
            return df
        except Exception as exc:
            last_error = exc
            time.sleep(sleep_seconds)

    if last_error is not None:
        raise RuntimeError(f"Téléchargement impossible pour {symbol}: {last_error}")
    return None


def download_ohlcv(symbols: list[str], start_date: str, end_date: str | None = None) -> Dict[str, pd.DataFrame]:
    end_date = end_date or datetime.utcnow().strftime("%Y-%m-%d")
    result: Dict[str, pd.DataFrame] = {}

    for symbol in symbols:
        try:
            df = _download_one_symbol(symbol, start_date, end_date)
            if df is None or df.empty:
                continue
            result[symbol] = df
        except Exception:
            continue

    return result


def filter_liquid_universe(
    market_data: Dict[str, pd.DataFrame],
    min_price: float,
    min_avg_dollar_volume: float,
    lookback: int = 20,
) -> list[str]:
    eligible: list[str] = []

    for symbol, df in market_data.items():
        if len(df) < lookback:
            continue
        recent = df.tail(lookback).copy()
        last_price = float(recent["Adj Close"].iloc[-1])
        avg_dollar_volume = float((recent["Adj Close"] * recent["Volume"]).mean())
        if last_price >= min_price and avg_dollar_volume >= min_avg_dollar_volume:
            eligible.append(symbol)

    return eligible
