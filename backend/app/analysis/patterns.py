"""Chart pattern detection — pivots, S/R, breakouts, classic patterns."""

from __future__ import annotations

from app.schemas.models import Candle


def _pivots(candles: list[Candle], left: int = 3, right: int = 3) -> tuple[list[int], list[int]]:
    highs: list[int] = []
    lows: list[int] = []
    for i in range(left, len(candles) - right):
        window = candles[i - left : i + right + 1]
        if candles[i].high == max(c.high for c in window):
            highs.append(i)
        if candles[i].low == min(c.low for c in window):
            lows.append(i)
    return highs, lows


def support_resistance(candles: list[Candle], *, tol: float = 0.01) -> dict:
    highs, lows = _pivots(candles)
    levels: list[float] = [candles[i].high for i in highs] + [candles[i].low for i in lows]
    if not levels:
        return {"support": [], "resistance": []}

    levels = sorted(levels)
    clusters: list[list[float]] = [[levels[0]]]
    for lvl in levels[1:]:
        if abs(lvl - clusters[-1][-1]) / clusters[-1][-1] <= tol:
            clusters[-1].append(lvl)
        else:
            clusters.append([lvl])

    compressed = [sum(c) / len(c) for c in clusters if len(c) >= 2]
    price = candles[-1].close
    support = sorted([x for x in compressed if x < price], reverse=True)[:3]
    resistance = sorted([x for x in compressed if x > price])[:3]
    return {"support": support, "resistance": resistance}


def detect_breakout(candles: list[Candle], levels: dict) -> dict | None:
    if len(candles) < 5:
        return None
    price = candles[-1].close
    prev = candles[-2].close
    vol = candles[-1].volume
    avg_vol = sum(c.volume for c in candles[-20:]) / min(20, len(candles))
    for r in levels.get("resistance") or []:
        if prev <= r < price and vol > avg_vol * 1.2:
            return {"name": "Breakout", "direction": "bullish", "level": r}
        if prev > r >= price:
            return {"name": "Fake Breakout", "direction": "bearish", "level": r}
    for s in levels.get("support") or []:
        if prev >= s > price and vol > avg_vol * 1.2:
            return {"name": "Breakdown", "direction": "bearish", "level": s}
        if prev < s <= price:
            return {"name": "Fake Breakdown", "direction": "bullish", "level": s}
    return None


def detect_double_top_bottom(candles: list[Candle]) -> list[dict]:
    highs, lows = _pivots(candles)
    found: list[dict] = []
    for i in range(1, len(highs)):
        a, b = highs[i - 1], highs[i]
        pa, pb = candles[a].high, candles[b].high
        if abs(pa - pb) / pa < 0.02 and b - a >= 5:
            found.append({"name": "Double Top", "direction": "bearish"})
            break
    for i in range(1, len(lows)):
        a, b = lows[i - 1], lows[i]
        pa, pb = candles[a].low, candles[b].low
        if abs(pa - pb) / pa < 0.02 and b - a >= 5:
            found.append({"name": "Double Bottom", "direction": "bullish"})
            break
    return found


def _slope(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    n = len(values)
    xs = list(range(n))
    x_mean = (n - 1) / 2
    y_mean = sum(values) / n
    num = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, values, strict=True))
    den = sum((x - x_mean) ** 2 for x in xs) or 1.0
    return num / den


def detect_triangle_flag(candles: list[Candle]) -> dict | None:
    """
    Classify compression after an impulse as triangle vs flag.

    Triangle: converging highs/lows (opposite signed slopes).
    Flag: roughly parallel channel (same-signed slopes) after a sharp impulse.
    """
    if len(candles) < 30:
        return None
    early = candles[-30:-15]
    late = candles[-15:]
    early_range = max(c.high for c in early) - min(c.low for c in early)
    late_range = max(c.high for c in late) - min(c.low for c in late)
    if early_range <= 0 or late_range / early_range >= 0.55:
        return None

    late_highs = [c.high for c in late]
    late_lows = [c.low for c in late]
    high_slope = _slope(late_highs)
    low_slope = _slope(late_lows)
    scale = (sum(late_highs) + sum(late_lows)) / (2 * len(late)) or 1.0
    high_norm = high_slope / scale
    low_norm = low_slope / scale

    # Parallel channel (same sign, similar magnitude) after impulse → flag
    same_sign = high_norm * low_norm > 0
    similar = abs(abs(high_norm) - abs(low_norm)) < 0.01
    impulse = abs(early[-1].close - early[0].close) / early[0].close > 0.04
    if same_sign and similar and impulse:
        direction = "bullish" if early[-1].close > early[0].close else "bearish"
        return {"name": "Flag", "direction": direction}

    # Converging boundaries → triangle
    if high_norm < 0 and low_norm > 0:
        return {"name": "Symmetrical Triangle", "direction": "neutral"}
    if high_norm < 0 and abs(low_norm) <= abs(high_norm) * 0.35:
        return {"name": "Descending Triangle", "direction": "bearish"}
    if low_norm > 0 and abs(high_norm) <= abs(low_norm) * 0.35:
        return {"name": "Ascending Triangle", "direction": "bullish"}
    return {"name": "Triangle", "direction": "neutral"}


def detect_patterns(candles: list[Candle]) -> dict:
    levels = support_resistance(candles)
    patterns: list[dict] = []
    patterns.extend(detect_double_top_bottom(candles))
    br = detect_breakout(candles, levels)
    if br:
        patterns.append(br)
    tf = detect_triangle_flag(candles)
    if tf:
        patterns.append(tf)

    return {"levels": levels, "patterns": patterns}
