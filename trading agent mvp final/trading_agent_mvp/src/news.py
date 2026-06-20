from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from .config import NewsConfig

POSITIVE_WORDS = {
    "beat", "beats", "bullish", "buyback", "expansion", "growth", "growths", "profit", "profits",
    "record", "strong", "surge", "upgrade", "upgrades", "raised", "raise", "outperform", "ai", "partnership",
}
NEGATIVE_WORDS = {
    "antitrust", "bearish", "cuts", "cut", "decline", "downgrade", "fraud", "investigation", "lawsuit",
    "layoffs", "miss", "misses", "probe", "recall", "selloff", "tariff", "warning", "weak",
}


@dataclass
class NewsContext:
    market_bias: float
    summary: list[str]
    symbol_bias: dict[str, float]
    symbol_summary: list[dict[str, Any]]
    articles: list[dict[str, Any]]
    errors: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _headline_sentiment_score(text: str) -> float:
    tokens = [token.strip(".,:;!?()[]{}\"'").lower() for token in text.split()]
    pos = sum(1 for t in tokens if t in POSITIVE_WORDS)
    neg = sum(1 for t in tokens if t in NEGATIVE_WORDS)
    if not tokens:
        return 0.0
    raw = (pos - neg) / max(len(tokens) ** 0.5, 1)
    return float(np.clip(raw, -1.0, 1.0))


def _extract_title(item: dict[str, Any]) -> str:
    if "title" in item and item["title"]:
        return str(item["title"])
    content = item.get("content")
    if isinstance(content, dict):
        if content.get("title"):
            return str(content["title"])
    return ""


def _extract_provider(item: dict[str, Any]) -> str:
    if item.get("publisher"):
        return str(item["publisher"])
    content = item.get("content")
    if isinstance(content, dict):
        if content.get("provider"):
            provider = content.get("provider")
            if isinstance(provider, dict) and provider.get("displayName"):
                return str(provider["displayName"])
            return str(provider)
    return ""


def _extract_link(item: dict[str, Any]) -> str:
    for key in ("link", "canonicalUrl", "url"):
        val = item.get(key)
        if isinstance(val, str):
            return val
        if isinstance(val, dict) and val.get("url"):
            return str(val["url"])
    content = item.get("content")
    if isinstance(content, dict):
        canonical = content.get("canonicalUrl")
        if isinstance(canonical, dict) and canonical.get("url"):
            return str(canonical["url"])
    return ""


def _extract_published_at(item: dict[str, Any]) -> str:
    ts = item.get("providerPublishTime")
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    content = item.get("content")
    if isinstance(content, dict):
        pub = content.get("pubDate")
        if pub:
            return str(pub)
    return ""


def fetch_symbol_news(symbol: str, max_items: int) -> list[dict[str, Any]]:
    try:
        import yfinance as yf
    except ImportError as exc:
        raise ImportError("yfinance n'est pas installé.") from exc

    ticker = yf.Ticker(symbol)
    items: list[dict[str, Any]] = []

    try:
        if hasattr(ticker, "get_news"):
            fetched = ticker.get_news(count=max_items)
            if isinstance(fetched, list):
                items = fetched[:max_items]
    except Exception:
        items = []

    if not items:
        try:
            news_attr = getattr(ticker, "news", [])
            if isinstance(news_attr, list):
                items = news_attr[:max_items]
        except Exception:
            items = []

    return items[:max_items]


def build_news_context(symbols: list[str], config: NewsConfig, benchmark: str) -> NewsContext:
    if not config.enabled:
        return NewsContext(0.0, ["News désactivées dans la configuration."], {}, [], [], [])

    market_symbols = config.market_symbols or [benchmark]
    article_records: list[dict[str, Any]] = []
    symbol_summary: list[dict[str, Any]] = []
    symbol_bias: dict[str, float] = {}
    errors: list[str] = []

    for symbol in symbols:
        try:
            raw_items = fetch_symbol_news(symbol, config.max_articles_per_symbol)
        except Exception as exc:  # pragma: no cover - dépend du réseau
            errors.append(f"{symbol}: {exc}")
            raw_items = []

        scored: list[float] = []
        seen_titles: set[str] = set()
        for item in raw_items:
            title = _extract_title(item).strip()
            if not title or title in seen_titles:
                continue
            seen_titles.add(title)
            score = _headline_sentiment_score(title)
            scored.append(score)
            article_records.append(
                {
                    "symbol": symbol,
                    "published_at": _extract_published_at(item),
                    "provider": _extract_provider(item),
                    "title": title,
                    "sentiment": round(score, 4),
                    "url": _extract_link(item),
                }
            )

        avg_sentiment = float(np.mean(scored)) if scored else 0.0
        bias = float(np.clip(avg_sentiment * 0.6, -0.6, 0.6))
        symbol_bias[symbol] = round(bias, 4)
        symbol_summary.append(
            {
                "symbol": symbol,
                "articles": len(scored),
                "avg_sentiment": round(avg_sentiment, 4),
                "symbol_bias": round(bias, 4),
            }
        )

    summary_df = pd.DataFrame(symbol_summary)
    market_df = summary_df[summary_df["symbol"].isin(market_symbols)] if not summary_df.empty else pd.DataFrame()
    market_bias = float(np.clip(market_df["symbol_bias"].mean() if not market_df.empty else 0.0, -0.5, 0.5))

    summary: list[str] = []
    if not summary_df.empty:
        best = summary_df.sort_values("symbol_bias", ascending=False).head(3)
        worst = summary_df.sort_values("symbol_bias", ascending=True).head(3)
        summary.append("Top news bias: " + ", ".join(f"{row.symbol} ({row.symbol_bias:+.2f})" for row in best.itertuples()))
        summary.append("Bottom news bias: " + ", ".join(f"{row.symbol} ({row.symbol_bias:+.2f})" for row in worst.itertuples()))
    else:
        summary.append("Aucune news exploitable récupérée.")

    return NewsContext(
        market_bias=round(market_bias, 4),
        summary=summary,
        symbol_bias=symbol_bias,
        symbol_summary=symbol_summary,
        articles=article_records,
        errors=errors,
    )
