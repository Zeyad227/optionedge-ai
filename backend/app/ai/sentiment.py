"""FinBERT news sentiment — lazy-loaded, cached by URL hash."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from functools import lru_cache

from app.schemas.models import NewsArticle, SentimentLabel

logger = logging.getLogger(__name__)

_pipeline = None
_failed = False

# In-process sentiment cache keyed by content hash (url_hash when available).
_sentiment_cache: dict[str, tuple[SentimentLabel, float]] = {}


def _get_pipeline():
    global _pipeline, _failed
    if _failed:
        return None
    if _pipeline is not None:
        return _pipeline
    try:
        from transformers import pipeline

        _pipeline = pipeline(
            "sentiment-analysis",
            model="ProsusAI/finbert",
            truncation=True,
            max_length=512,
        )
        return _pipeline
    except Exception as exc:  # noqa: BLE001
        logger.warning("FinBERT unavailable (%s); using lexicon fallback", exc)
        _failed = True
        return None


_BULL = {
    "beat",
    "surge",
    "rally",
    "upgrade",
    "growth",
    "record",
    "profit",
    "bullish",
    "strong",
    "outperform",
}
_BEAR = {
    "miss",
    "plunge",
    "fall",
    "downgrade",
    "loss",
    "weak",
    "bearish",
    "lawsuit",
    "cut",
    "recession",
}


def _lexicon(text: str) -> tuple[SentimentLabel, float]:
    words = set(text.lower().split())
    bull = len(words & _BULL)
    bear = len(words & _BEAR)
    if bull == bear:
        return "Neutral", 0.5
    if bull > bear:
        return "Bullish", min(0.5 + 0.1 * (bull - bear), 0.9)
    return "Bearish", min(0.5 + 0.1 * (bear - bull), 0.9)


def _classify_text_sync(text: str) -> tuple[SentimentLabel, float]:
    pipe = _get_pipeline()
    if pipe is None:
        return _lexicon(text)
    result = pipe(text[:512])[0]
    label = result["label"].lower()
    score = float(result["score"])
    mapping = {
        "positive": "Bullish",
        "negative": "Bearish",
        "neutral": "Neutral",
    }
    return mapping.get(label, "Neutral"), score  # type: ignore[return-value]


async def classify_text(text: str) -> tuple[SentimentLabel, float]:
    """Classify sentiment off the event loop (FinBERT is synchronous)."""
    return await asyncio.to_thread(_classify_text_sync, text)


def impact_score(
    sentiment_score: float,
    *,
    source: str,
    hours_ago: float | None,
) -> float:
    source_weight = {
        "Reuters Business": 1.0,
        "Federal Reserve": 1.0,
        "SEC Press": 0.95,
        "CNBC": 0.85,
        "MarketWatch": 0.8,
        "Yahoo Finance": 0.7,
        "finnhub": 0.75,
    }.get(source, 0.6)
    recency = 1.0
    if hours_ago is not None:
        recency = max(0.3, 1.0 - hours_ago / 72.0)
    return round(sentiment_score * source_weight * recency * 100, 1)


async def annotate_articles(articles: list[NewsArticle]) -> list[NewsArticle]:
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    for article in articles:
        cache_key = url_hash(article.url) if article.url else None
        if cache_key and cache_key in _sentiment_cache:
            label, score = _sentiment_cache[cache_key]
        else:
            text = f"{article.title}. {article.summary or ''}"
            label, score = await classify_text(text)
            if cache_key:
                _sentiment_cache[cache_key] = (label, score)
        article.sentiment = label
        article.sentiment_score = score
        hours = None
        if article.published_at:
            hours = (now - article.published_at).total_seconds() / 3600
        article.impact = impact_score(score, source=article.source, hours_ago=hours)
    return articles


@lru_cache(maxsize=4096)
def url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


def clear_sentiment_cache_for_tests() -> None:
    """Reset in-process sentiment cache — tests only."""
    _sentiment_cache.clear()
    url_hash.cache_clear()
