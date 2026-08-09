"""Scoring determinism, monotonicity, and explanation-to-factor consistency."""

from datetime import UTC, datetime, timedelta

from app.ai.explain import validate_explanation
from app.ai.scoring import score_symbol
from app.schemas.models import Candle, NewsArticle


def _candles(n=120):
    base = datetime(2024, 1, 2, tzinfo=UTC)
    price = 100.0
    out = []
    for i in range(n):
        c = price * 1.002
        out.append(
            Candle(
                timestamp=base + timedelta(days=i),
                open=price,
                high=c * 1.01,
                low=price * 0.99,
                close=c,
                volume=2_000_000,
            )
        )
        price = c
    return out


def test_score_is_deterministic():
    candles = _candles()
    a = score_symbol("TEST", candles, candle_source="fixture")
    b = score_symbol("TEST", candles, candle_source="fixture")
    assert a.action == b.action
    assert a.confidence == b.confidence
    assert [f.name for f in a.factors] == [f.name for f in b.factors]


def test_explanation_mentions_only_real_factors():
    result = score_symbol("TEST", _candles(), candle_source="fixture")
    validate_explanation(result.reasoning, result.factors, result.missing_factors)
    assert result.forecast_type == "probabilistic"
    assert "Not financial advice" in result.disclaimer or "not financial advice" in result.disclaimer.lower()


def test_missing_data_not_forced_neutral():
    short = _candles(10)
    result = score_symbol("TEST", short, candle_source="fixture")
    assert result.action == "Avoid"
    assert "insufficient_ohlcv_history" in result.missing_factors
    validate_explanation(result.reasoning, result.factors, result.missing_factors)


def test_bullish_news_increases_score_vs_baseline():
    candles = _candles()
    baseline = score_symbol("TEST", candles, candle_source="fixture")
    articles = [
        NewsArticle(
            title="Beat",
            url="https://example.com/a",
            source="fixture",
            sentiment="Bullish",
            impact=90,
        ),
        NewsArticle(
            title="Upgrade",
            url="https://example.com/b",
            source="fixture",
            sentiment="Bullish",
            impact=85,
        ),
    ]
    enriched = score_symbol(
        "TEST",
        candles,
        candle_source="fixture",
        news=articles,
        news_source="fixture-news",
    )
    assert enriched.confidence >= baseline.confidence
    assert "News sentiment" in [f.name for f in enriched.factors]


def test_support_resistance_are_factors_not_free_text():
    result = score_symbol("TEST", _candles(), candle_source="fixture")
    names = {f.name for f in result.factors}
    text = "\n".join(result.reasoning)
    if "Support levels" in names:
        assert "Nearby support:" not in text
        assert "Support levels:" in text
    if "Resistance levels" in names:
        assert "Nearby resistance:" not in text
        assert "Resistance levels:" in text
