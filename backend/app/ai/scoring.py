"""Deterministic factor scoring — explanations come from the factor list itself.

Three kinds of evidence are kept strictly apart, because conflating them makes
the aggregate score meaningless:

``directional``
    Signed votes on which way price is more likely to go. Only these are summed,
    and only these count toward the denominator.
``modulator``
    Unsigned readings such as ADX or IV rank. Trend *strength* is not trend
    *direction*, and volatility level says nothing about direction either, so
    these adjust conviction and strategy — never the sign of the score.
``context``
    Reported so the reader can see it (support levels, indecision candles).
    Never touches the arithmetic.

Mean-reversion readings are also gated on the prevailing regime: an RSI of 2 in
a relentless downtrend is confirmation that sellers are in control, not an
invitation to buy the dip.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.ai.explain import explain
from app.analysis.candles import detect_candles
from app.analysis.indicators import compute_all
from app.analysis.greeks import probability_itm_from_delta
from app.analysis.options_metrics import chain_summary, suggest_contract
from app.analysis.patterns import detect_patterns
from app.schemas.models import (
    Candle,
    ConfidenceComponent,
    Factor,
    NewsArticle,
    OptionContract,
    SignalResponse,
)

MIN_HISTORY_BARS = 50

# Wilder's conventional threshold for "a trend is present".
ADX_TRENDING = 25.0
ADX_CHOPPY = 15.0

BUY_THRESHOLD = 0.25
SELL_THRESHOLD = -0.25

# Below this share of available inputs we decline to take a directional side
# rather than extrapolating from a handful of indicators.
MIN_COVERAGE_FOR_DIRECTION = 0.45

# Confidence is a heuristic blend, not a probability. These caps keep it from
# ever reading like a calibrated win rate.
CONFIDENCE_FLOOR = 5.0
CONFIDENCE_CEILING = 90.0
STRENGTH_POINTS = 65.0
COVERAGE_POINTS = 25.0


def _factor(
    name: str,
    observed: str,
    direction: str,
    weight: float,
    contribution: float,
    source: str,
    *,
    role: str = "directional",
) -> Factor:
    return Factor(
        name=name,
        observed=observed,
        direction=direction,  # type: ignore[arg-type]
        weight=weight,
        contribution=contribution,
        source=source,
        role=role,  # type: ignore[arg-type]
    )


def _trend_regime(ind: dict) -> str:
    """Classify the prevailing regime from EMA structure plus directional movement."""
    ema_9, ema_20, ema_50 = ind.get("ema_9"), ind.get("ema_20"), ind.get("ema_50")
    if None in (ema_9, ema_20, ema_50):
        return "unknown"

    adx = ind.get("adx")
    di_plus, di_minus = ind.get("di_plus"), ind.get("di_minus")
    trending = adx is not None and adx >= ADX_TRENDING
    di_bullish = di_plus is not None and di_minus is not None and di_plus > di_minus
    di_bearish = di_plus is not None and di_minus is not None and di_minus > di_plus

    if ema_9 > ema_20 > ema_50 and (trending or di_bullish):
        return "uptrend"
    if ema_9 < ema_20 < ema_50 and (trending or di_bearish):
        return "downtrend"
    return "range"


def _ema_factor(ind: dict, source: str) -> Factor:
    ema_9, ema_20, ema_50 = ind["ema_9"], ind["ema_20"], ind["ema_50"]
    if ema_9 > ema_20 > ema_50:
        return _factor(
            "EMA stack",
            f"EMA9 {ema_9:.2f} > EMA20 {ema_20:.2f} > EMA50 {ema_50:.2f}",
            "bullish",
            1.2,
            1.2,
            source,
        )
    if ema_9 < ema_20 < ema_50:
        return _factor(
            "EMA stack",
            f"EMA9 {ema_9:.2f} < EMA20 {ema_20:.2f} < EMA50 {ema_50:.2f}",
            "bearish",
            1.2,
            -1.2,
            source,
        )
    return _factor("EMA stack", "Mixed / compressing EMAs", "neutral", 0.6, 0.0, source)


def _rsi_factor(rsi: float, regime: str, source: str) -> Factor:
    """RSI read through the regime.

    Overbought/oversold only mean "reversal" inside a range. Inside a trend the
    same reading means the trend is strong, which is why the signs flip here.
    """
    if regime == "downtrend":
        if rsi < 30:
            return _factor(
                "RSI",
                f"{rsi:.1f} oversold, but inside a downtrend (continuation, not a reversal)",
                "bearish",
                1.0,
                -0.4,
                source,
            )
        if rsi > 70:
            return _factor(
                "RSI",
                f"{rsi:.1f} overbought against a downtrend (downtrend losing grip)",
                "bullish",
                1.0,
                0.6,
                source,
            )
    elif regime == "uptrend":
        if rsi > 70:
            return _factor(
                "RSI",
                f"{rsi:.1f} overbought, but inside an uptrend (momentum, not a top)",
                "bullish",
                1.0,
                0.4,
                source,
            )
        if rsi < 30:
            return _factor(
                "RSI",
                f"{rsi:.1f} oversold against an uptrend (uptrend cracking)",
                "bearish",
                1.0,
                -0.6,
                source,
            )
    else:
        if rsi < 30:
            return _factor("RSI", f"{rsi:.1f} oversold in a range", "bullish", 1.0, 1.0, source)
        if rsi > 70:
            return _factor("RSI", f"{rsi:.1f} overbought in a range", "bearish", 1.0, -1.0, source)

    if rsi >= 50:
        return _factor("RSI", f"{rsi:.1f} above midline", "bullish", 0.5, 0.4, source)
    return _factor("RSI", f"{rsi:.1f} below midline", "bearish", 0.5, -0.4, source)


def _macd_factor(macd: float, signal: float, hist: float | None, source: str) -> Factor:
    """MACD crossover, qualified by which side of zero it happens on.

    A cross up while both lines sit far below zero is decelerating downside, not
    a bull signal, so it earns a fraction of the weight.
    """
    h = hist or 0.0
    if macd > signal and h > 0:
        if macd > 0:
            return _factor(
                "MACD",
                f"bullish crossover above zero (hist {h:.3f})",
                "bullish",
                1.0,
                1.0,
                source,
            )
        return _factor(
            "MACD",
            f"crossover below zero line — downside momentum easing (hist {h:.3f})",
            "bullish",
            1.0,
            0.4,
            source,
        )
    if macd < signal and h < 0:
        if macd < 0:
            return _factor(
                "MACD",
                f"bearish crossover below zero (hist {h:.3f})",
                "bearish",
                1.0,
                -1.0,
                source,
            )
        return _factor(
            "MACD",
            f"crossover above zero line — upside momentum fading (hist {h:.3f})",
            "bearish",
            1.0,
            -0.4,
            source,
        )
    return _factor("MACD", "flat / transitioning", "neutral", 0.4, 0.0, source)


def _volume_factor(rv: float, last: Candle, source: str) -> Factor:
    """Volume confirms whichever way the bar closed; on its own it has no sign."""
    if rv >= 1.5:
        if last.close > last.open:
            return _factor(
                "Relative volume",
                f"{rv:.2f}x average on an up bar (buyers confirming)",
                "bullish",
                0.8,
                0.6,
                source,
            )
        if last.close < last.open:
            return _factor(
                "Relative volume",
                f"{rv:.2f}x average on a down bar (sellers confirming)",
                "bearish",
                0.8,
                -0.6,
                source,
            )
        return _factor(
            "Relative volume",
            f"{rv:.2f}x average on a flat close (heavy but undecided)",
            "neutral",
            0.0,
            0.0,
            source,
            role="modulator",
        )
    if rv <= 0.6:
        return _factor(
            "Relative volume",
            f"{rv:.2f}x average — thin participation, lower conviction",
            "neutral",
            0.0,
            0.0,
            source,
            role="modulator",
        )
    return _factor(
        "Relative volume",
        f"{rv:.2f}x average (normal)",
        "neutral",
        0.0,
        0.0,
        source,
        role="modulator",
    )


def _insufficient_history(symbol: str, sources: set[str]) -> SignalResponse:
    missing = ["insufficient_ohlcv_history"]
    return SignalResponse(
        symbol=symbol.upper(),
        action="Avoid",
        trend="Sideways",
        confidence=10.0,
        trend_regime="unknown",
        data_coverage=0.0,
        missing_factors=missing,
        reasoning=explain("Avoid", 10.0, [], missing),
        generated_at=datetime.now(UTC),
        sources=sorted(sources),
    )


def score_symbol(
    symbol: str,
    candles: list[Candle],
    *,
    candle_source: str,
    contracts: list[OptionContract] | None = None,
    options_source: str | None = None,
    news: list[NewsArticle] | None = None,
    news_source: str | None = None,
    iv_rank: float | None = None,
    iv_stats: dict | None = None,
    insider_cluster: dict | None = None,
) -> SignalResponse:
    factors: list[Factor] = []
    missing: list[str] = []
    sources: set[str] = {candle_source}

    if len(candles) < MIN_HISTORY_BARS:
        return _insufficient_history(symbol, sources)

    ind = compute_all(candles)
    price = ind["close"]
    regime = _trend_regime(ind)
    last = candles[-1]

    if None not in (ind["ema_9"], ind["ema_20"], ind["ema_50"]):
        factors.append(_ema_factor(ind, candle_source))
    else:
        missing.append("ema_stack")

    if ind["rsi"] is not None:
        factors.append(_rsi_factor(ind["rsi"], regime, candle_source))
    else:
        missing.append("rsi")

    if ind["macd"] is not None and ind["macd_signal"] is not None:
        factors.append(
            _macd_factor(ind["macd"], ind["macd_signal"], ind["macd_hist"], candle_source)
        )
    else:
        missing.append("macd")

    # ADX sizes conviction; it is unsigned and must not tilt the score.
    if ind["adx"] is not None:
        adx = ind["adx"]
        if adx >= ADX_TRENDING:
            observed = f"{adx:.1f} — trending, raises conviction in the directional read"
        elif adx < ADX_CHOPPY:
            observed = f"{adx:.1f} — choppy, lowers conviction in the directional read"
        else:
            observed = f"{adx:.1f} — mild trend"
        factors.append(
            _factor("ADX", observed, "neutral", 0.0, 0.0, candle_source, role="modulator")
        )
    else:
        missing.append("adx")

    if ind.get("relative_volume") is not None:
        factors.append(_volume_factor(ind["relative_volume"], last, candle_source))
    else:
        missing.append("relative_volume")

    pattern_info = detect_patterns(candles)
    levels = pattern_info["levels"]
    if levels.get("support"):
        factors.append(
            _factor(
                "Support levels",
                ", ".join(f"{x:.2f}" for x in levels["support"][:2]),
                "neutral",
                0.0,
                0.0,
                candle_source,
                role="context",
            )
        )
    if levels.get("resistance"):
        factors.append(
            _factor(
                "Resistance levels",
                ", ".join(f"{x:.2f}" for x in levels["resistance"][:2]),
                "neutral",
                0.0,
                0.0,
                candle_source,
                role="context",
            )
        )

    for p in pattern_info["patterns"]:
        direction = p["direction"]
        if direction == "bullish":
            factors.append(
                _factor(f"Pattern: {p['name']}", p["name"], "bullish", 0.7, 0.7, candle_source)
            )
        elif direction == "bearish":
            factors.append(
                _factor(f"Pattern: {p['name']}", p["name"], "bearish", 0.7, -0.7, candle_source)
            )
        else:
            factors.append(
                _factor(
                    f"Pattern: {p['name']}",
                    p["name"],
                    "neutral",
                    0.0,
                    0.0,
                    candle_source,
                    role="context",
                )
            )

    for c in detect_candles(candles):
        if c["direction"] == "bullish":
            factors.append(
                _factor(f"Candle: {c['name']}", c["name"], "bullish", 0.5, 0.5, candle_source)
            )
        elif c["direction"] == "bearish":
            factors.append(
                _factor(f"Candle: {c['name']}", c["name"], "bearish", 0.5, -0.5, candle_source)
            )
        else:
            # A doji is indecision by definition — it cannot cast a directional vote.
            factors.append(
                _factor(
                    f"Candle: {c['name']}",
                    c["name"],
                    "neutral",
                    0.0,
                    0.0,
                    candle_source,
                    role="context",
                )
            )

    if news:
        if news_source:
            sources.add(news_source)
        scored = [n for n in news if n.sentiment]
        if scored:
            bull = sum(1 for n in scored if n.sentiment == "Bullish")
            bear = sum(1 for n in scored if n.sentiment == "Bearish")
            avg_impact = sum(n.impact or 0 for n in scored) / len(scored)
            observed = f"{bull} bullish / {bear} bearish (avg impact {avg_impact:.0f})"
            if bull > bear:
                factors.append(
                    _factor("News sentiment", observed, "bullish", 1.0, 0.8, news_source or "news")
                )
            elif bear > bull:
                factors.append(
                    _factor("News sentiment", observed, "bearish", 1.0, -0.8, news_source or "news")
                )
            else:
                factors.append(
                    _factor(
                        "News sentiment",
                        "Mixed / neutral coverage",
                        "neutral",
                        0.5,
                        0.0,
                        news_source or "news",
                    )
                )
        else:
            missing.append("news_sentiment")
    else:
        missing.append("news")

    if insider_cluster:
        direction = insider_cluster["direction"].lower()
        if direction == "bullish":
            factors.append(
                _factor(
                    "Insider cluster",
                    insider_cluster["label"],
                    "bullish",
                    0.9,
                    0.9,
                    "sec-edgar",
                )
            )
        elif direction == "bearish":
            factors.append(
                _factor(
                    "Insider cluster",
                    insider_cluster["label"],
                    "bearish",
                    0.9,
                    -0.9,
                    "sec-edgar",
                )
            )
        else:
            factors.append(
                _factor(
                    "Insider cluster",
                    insider_cluster["label"],
                    "neutral",
                    0.0,
                    0.0,
                    "sec-edgar",
                    role="context",
                )
            )
        sources.add("sec-edgar")
    else:
        missing.append("insider_cluster")

    suggested = None
    if contracts:
        if options_source:
            sources.add(options_source)
        summary = chain_summary(contracts, price)
        pcr = summary.get("put_call_ratio")
        expiry_note = summary.get("front_expiration") or "front expiry"
        if pcr is not None:
            observed = f"{pcr:.2f} open-interest positioning, {expiry_note}"
            if pcr < 0.7:
                factors.append(
                    _factor(
                        "Put/Call ratio",
                        f"{observed} (call-heavy)",
                        "bullish",
                        0.5,
                        0.4,
                        options_source or "options",
                    )
                )
            elif pcr > 1.2:
                factors.append(
                    _factor(
                        "Put/Call ratio",
                        f"{observed} (put-heavy)",
                        "bearish",
                        0.5,
                        -0.4,
                        options_source or "options",
                    )
                )
            else:
                factors.append(
                    _factor(
                        "Put/Call ratio",
                        f"{observed} (balanced)",
                        "neutral",
                        0.3,
                        0.0,
                        options_source or "options",
                    )
                )
        else:
            missing.append("put_call_ratio")
    else:
        missing.append("option_chain")

    # IV rank tells us whether premium is cheap or rich. That is a strategy
    # decision (debit vs credit structures), not a directional one.
    volatility_regime: str | None = None
    if iv_rank is not None:
        partial = " (partial lookback)" if iv_stats and iv_stats.get("partial") else ""
        if iv_rank < 30:
            volatility_regime = "cheap"
            observed = f"{iv_rank:.0f} — premium cheap, favours debit structures{partial}"
        elif iv_rank > 70:
            volatility_regime = "expensive"
            observed = f"{iv_rank:.0f} — premium rich, favours credit structures{partial}"
        else:
            volatility_regime = "mid"
            observed = f"{iv_rank:.0f} — mid-range{partial}"
        factors.append(
            _factor("IV rank", observed, "neutral", 0.0, 0.0, "iv-history", role="modulator")
        )
        sources.add("iv-history")
    else:
        missing.append("iv_rank")

    directional = [f for f in factors if f.role == "directional"]
    raw = sum(f.contribution for f in directional)
    denominator = sum(abs(f.weight) for f in directional) or 1.0
    score = raw / denominator

    considered = len(directional) + len(missing)
    coverage = len(directional) / considered if considered else 0.0

    adx_value = ind.get("adx")
    conviction = 1.0
    if adx_value is not None:
        if adx_value >= ADX_TRENDING:
            conviction = 1.15
        elif adx_value < ADX_CHOPPY:
            conviction = 0.8

    thin_coverage = coverage < MIN_COVERAGE_FOR_DIRECTION
    if thin_coverage:
        missing.append("insufficient_factor_coverage")

    if score >= BUY_THRESHOLD and not thin_coverage:
        action, trend, direction = "Buy", "Bullish", "bullish"
    elif score <= SELL_THRESHOLD and not thin_coverage:
        action, trend, direction = "Sell", "Bearish", "bearish"
    else:
        action, direction = "Avoid", "neutral"
        trend = (
            "Bullish" if regime == "uptrend" else "Bearish" if regime == "downtrend" else "Sideways"
        )

    strength_points = min(abs(score), 1.0) * STRENGTH_POINTS * conviction
    coverage_points = coverage * COVERAGE_POINTS * conviction
    confidence = max(
        CONFIDENCE_FLOOR, min(CONFIDENCE_CEILING, strength_points + coverage_points)
    )

    breakdown = _confidence_breakdown(directional, strength_points, coverage_points)

    entry = price
    stop: float | None = None
    targets: list[float] = []
    risk_reward: float | None = None
    atr = ind.get("atr") or price * 0.02

    if direction == "bullish":
        stop = max(price - 1.5 * atr, 0.01)
        targets = [price + 2 * atr, price + 3 * atr]
        risk_reward = (targets[0] - entry) / (entry - stop) if entry > stop else None
    elif direction == "bearish":
        stop = price + 1.5 * atr
        targets = [max(price - 2 * atr, 0.01), max(price - 3 * atr, 0.01)]
        risk_reward = (entry - targets[0]) / (stop - entry) if stop > entry else None

    if contracts and direction in {"bullish", "bearish"}:
        suggested = suggest_contract(contracts, spot=price, direction=direction)

    pop: float | None = None
    pop_basis: str = "unavailable"
    if suggested and suggested.delta is not None:
        pop = probability_itm_from_delta(suggested.delta, suggested.option_type)
        if pop is not None:
            pop_basis = "delta_approximation"

    reasoning = explain(action, confidence, factors, missing)

    return SignalResponse(
        symbol=symbol.upper(),
        action=action,  # type: ignore[arg-type]
        trend=trend,  # type: ignore[arg-type]
        confidence=round(confidence, 1),
        confidence_breakdown=breakdown,
        trend_regime=regime,  # type: ignore[arg-type]
        volatility_regime=volatility_regime,  # type: ignore[arg-type]
        data_coverage=round(coverage, 3),
        entry=round(entry, 4),
        stop_loss=round(stop, 4) if stop is not None else None,
        take_profit=[round(t, 4) for t in targets],
        risk_reward=round(risk_reward, 2) if risk_reward is not None else None,
        probability_of_profit=pop,
        probability_of_profit_basis=pop_basis,  # type: ignore[arg-type]
        suggested_contract=suggested,
        factors=factors,
        missing_factors=missing,
        reasoning=reasoning,
        generated_at=datetime.now(UTC),
        sources=sorted(sources),
    )


def _confidence_breakdown(
    directional: list[Factor],
    strength_points: float,
    coverage_points: float,
) -> list[ConfidenceComponent]:
    """Split the confidence number into additive, attributable pieces."""
    components: list[ConfidenceComponent] = []
    total_abs = sum(abs(f.contribution) for f in directional)
    if total_abs > 0:
        for f in directional:
            if f.contribution == 0:
                continue
            share = abs(f.contribution) / total_abs * strength_points
            components.append(
                ConfidenceComponent(
                    name=f.name,
                    direction=f.direction,
                    points=round(share, 1),
                )
            )
    components.sort(key=lambda c: c.points, reverse=True)
    components.append(
        ConfidenceComponent(
            name="Data coverage",
            direction="neutral",
            points=round(coverage_points, 1),
        )
    )
    return components
