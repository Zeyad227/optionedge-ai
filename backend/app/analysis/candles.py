"""Candlestick pattern recognition — deterministic OHLC rules."""

from __future__ import annotations

from app.schemas.models import Candle


def _body(c: Candle) -> float:
    return abs(c.close - c.open)


def _range(c: Candle) -> float:
    return max(c.high - c.low, 1e-9)


def _bullish(c: Candle) -> bool:
    return c.close > c.open


def _prior_trend(candles: list[Candle], lookback: int = 5) -> str:
    """Classify the move immediately before the pattern bar."""
    if len(candles) < lookback + 1:
        return "unknown"
    window = candles[-(lookback + 1) : -1]
    if not window:
        return "unknown"
    start = window[0].close
    end = window[-1].close
    if start <= 0:
        return "unknown"
    change = (end - start) / start
    if change > 0.01:
        return "up"
    if change < -0.01:
        return "down"
    return "range"


def detect_candles(candles: list[Candle]) -> list[dict]:
    if len(candles) < 3:
        return []
    a, b, c = candles[-3], candles[-2], candles[-1]
    found: list[dict] = []
    trend = _prior_trend(candles)

    # Doji — indecision; no trend prerequisite.
    if _body(c) / _range(c) < 0.1:
        found.append({"name": "Doji", "direction": "neutral"})

    # Hammer / Shooting star — require opposing prior trend.
    upper = c.high - max(c.open, c.close)
    lower = min(c.open, c.close) - c.low
    if lower > 2 * _body(c) and upper < _body(c) and trend in {"down", "range"}:
        found.append({"name": "Hammer", "direction": "bullish"})
    if upper > 2 * _body(c) and lower < _body(c) and trend in {"up", "range"}:
        found.append({"name": "Shooting Star", "direction": "bearish"})

    # Engulfing — confirm against prior bar's direction.
    if _bullish(c) and not _bullish(b) and c.open <= b.close and c.close >= b.open:
        if trend in {"down", "range"}:
            found.append({"name": "Bullish Engulfing", "direction": "bullish"})
    if not _bullish(c) and _bullish(b) and c.open >= b.close and c.close <= b.open:
        if trend in {"up", "range"}:
            found.append({"name": "Bearish Engulfing", "direction": "bearish"})

    # Morning / Evening star — require sustained move into the pattern.
    if (
        not _bullish(a)
        and _body(b) / _range(b) < 0.3
        and _bullish(c)
        and c.close > (a.open + a.close) / 2
        and trend in {"down", "range"}
    ):
        found.append({"name": "Morning Star", "direction": "bullish"})
    if (
        _bullish(a)
        and _body(b) / _range(b) < 0.3
        and not _bullish(c)
        and c.close < (a.open + a.close) / 2
        and trend in {"up", "range"}
    ):
        found.append({"name": "Evening Star", "direction": "bearish"})

    return found
