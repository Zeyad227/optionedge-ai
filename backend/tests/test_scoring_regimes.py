"""Regression tests for regime handling and factor-role separation in scoring.

Each test here corresponds to a defect that produced an actively wrong trade
recommendation, so they assert on the trading decision, not on internals.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.ai.scoring import score_symbol
from app.schemas.models import Candle


def _series(
    *,
    drift: float,
    bars: int = 140,
    start: float = 200.0,
    final_volume_multiple: float = 1.0,
    final_bar_down: bool | None = None,
) -> list[Candle]:
    """Build a synthetic OHLCV series with a constant per-bar drift."""
    out: list[Candle] = []
    price = start
    for i in range(bars):
        price *= 1 + drift
        is_last = i == bars - 1
        rising = drift > 0
        if is_last and final_bar_down is not None:
            rising = not final_bar_down
        out.append(
            Candle(
                timestamp=datetime(2024, 1, 1, tzinfo=UTC) + timedelta(days=i),
                open=price * (0.995 if rising else 1.005),
                high=price * 1.008,
                low=price * 0.992,
                close=price,
                volume=1_000_000.0 * (final_volume_multiple if is_last else 1.0),
            )
        )
    return out


def test_sustained_downtrend_is_never_a_buy():
    """An unbroken multi-month decline must not be labelled Buy.

    Previously RSI (pinned at 0, read as "oversold"), a MACD crossover far below
    the zero line, and ADX contributing a fixed positive tilt combined to push an
    81% decline over the +0.25 Buy threshold.
    """
    signal = score_symbol("TEST", _series(drift=-0.012), candle_source="test")
    assert signal.action != "Buy", (
        f"downtrend scored {signal.action} "
        f"(factors: {[(f.name, f.contribution) for f in signal.factors]})"
    )
    assert signal.trend != "Bullish"
    assert signal.trend_regime == "downtrend"


def test_sustained_uptrend_is_never_a_sell():
    signal = score_symbol("TEST", _series(drift=0.012), candle_source="test")
    assert signal.action != "Sell"
    assert signal.trend_regime == "uptrend"


def test_oversold_in_downtrend_reads_bearish():
    signal = score_symbol("TEST", _series(drift=-0.012), candle_source="test")
    rsi = next(f for f in signal.factors if f.name == "RSI")
    assert rsi.contribution < 0, "oversold inside a downtrend is continuation, not a reversal"
    assert rsi.direction == "bearish"


def test_adx_never_contributes_direction():
    """ADX is unsigned; it may size conviction but must not vote on direction."""
    up = score_symbol("TEST", _series(drift=0.012), candle_source="test")
    down = score_symbol("TEST", _series(drift=-0.012), candle_source="test")
    for signal in (up, down):
        adx = next(f for f in signal.factors if f.name == "ADX")
        assert adx.contribution == 0.0
        assert adx.weight == 0.0
        assert adx.role == "modulator"


def test_high_volume_follows_the_bar_direction():
    """Volume confirms whoever won the bar; alone it carries no direction."""
    up_bar = score_symbol(
        "TEST",
        _series(drift=0.012, final_volume_multiple=3.0, final_bar_down=False),
        candle_source="test",
    )
    down_bar = score_symbol(
        "TEST",
        _series(drift=-0.012, final_volume_multiple=3.0, final_bar_down=True),
        candle_source="test",
    )
    assert next(f for f in up_bar.factors if f.name == "Relative volume").contribution > 0
    assert next(f for f in down_bar.factors if f.name == "Relative volume").contribution < 0


def test_iv_rank_does_not_move_direction():
    """Cheap or rich premium is a strategy choice, not a directional opinion."""
    candles = _series(drift=-0.012)
    scores = []
    for iv in (5.0, 50.0, 95.0):
        signal = score_symbol("TEST", candles, candle_source="test", iv_rank=iv)
        iv_factor = next(f for f in signal.factors if f.name == "IV rank")
        assert iv_factor.contribution == 0.0
        assert iv_factor.role == "modulator"
        scores.append(sum(f.contribution for f in signal.factors))
    assert len(set(scores)) == 1, "IV rank shifted the directional score"


@pytest.mark.parametrize("iv_rank,expected", [(5.0, "cheap"), (50.0, "mid"), (95.0, "expensive")])
def test_iv_rank_is_surfaced_as_a_volatility_regime(iv_rank, expected):
    signal = score_symbol("TEST", _series(drift=0.012), candle_source="test", iv_rank=iv_rank)
    assert signal.volatility_regime == expected


def test_context_factors_do_not_dilute_the_score():
    """Support levels and indecision candles must not damp the score magnitude."""
    signal = score_symbol("TEST", _series(drift=0.012), candle_source="test")
    for factor in signal.factors:
        if factor.role in {"context", "modulator"}:
            assert factor.weight == 0.0, f"{factor.name} still carries denominator weight"
            assert factor.contribution == 0.0


def test_confidence_breakdown_sums_to_confidence():
    signal = score_symbol("TEST", _series(drift=0.012), candle_source="test")
    assert signal.confidence_breakdown
    total = sum(abs(c.points) for c in signal.confidence_breakdown)
    # Only exact when confidence is not clamped at the floor/ceiling.
    if 5.0 < signal.confidence < 90.0:
        assert total == pytest.approx(signal.confidence, abs=0.5)


def test_confidence_is_labelled_uncalibrated():
    signal = score_symbol("TEST", _series(drift=0.012), candle_source="test")
    assert signal.confidence_basis == "heuristic_uncalibrated"
    assert signal.confidence <= 90.0


def test_thin_coverage_refuses_a_directional_call():
    """With most inputs unavailable the engine should decline, not extrapolate."""
    signal = score_symbol("TEST", _series(drift=0.012), candle_source="test")
    if signal.data_coverage is not None and signal.data_coverage < 0.45:
        assert signal.action == "Avoid"
        assert "insufficient_factor_coverage" in signal.missing_factors


def test_stop_loss_stays_positive_on_a_collapsed_price():
    signal = score_symbol("TEST", _series(drift=-0.05, start=5000.0), candle_source="test")
    if signal.stop_loss is not None:
        assert signal.stop_loss > 0
    assert all(t > 0 for t in signal.take_profit)
