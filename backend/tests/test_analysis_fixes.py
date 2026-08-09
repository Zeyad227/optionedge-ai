"""Regression tests for indicator and options-chain calculation defects."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pandas as pd
import pytest

from app.analysis.indicators import (
    candles_to_df,
    compute_all,
    directional_movement,
    rolling_vwap,
    rsi,
    vwap,
)
from app.analysis.options_metrics import (
    chain_summary,
    for_expiration,
    front_expiration,
    max_pain,
    put_call_ratio,
)
from app.schemas.models import Candle, OptionContract


def _flat_then_gap(bars: int = 200, shift_at: int = 180) -> list[Candle]:
    """200 bars at 100, then a step change to 300 for the tail."""
    out = []
    for i in range(bars):
        level = 300.0 if i >= shift_at else 100.0
        out.append(
            Candle(
                timestamp=datetime(2024, 1, 1, tzinfo=UTC) + timedelta(days=i),
                open=level,
                high=level + 1,
                low=level - 1,
                close=level,
                volume=1_000.0,
            )
        )
    return out


# --- RSI -------------------------------------------------------------------


def test_rsi_reaches_100_on_an_unbroken_up_run():
    """No losses in the window means maximum strength, not missing data."""
    closes = pd.Series([100.0 + i for i in range(40)])
    value = rsi(closes).iloc[-1]
    assert not pd.isna(value)
    assert value == pytest.approx(100.0)


def test_rsi_reaches_zero_on_an_unbroken_down_run():
    closes = pd.Series([200.0 - i for i in range(40)])
    assert rsi(closes).iloc[-1] == pytest.approx(0.0)


def test_rsi_is_50_on_a_flat_series():
    closes = pd.Series([100.0] * 40)
    assert rsi(closes).iloc[-1] == pytest.approx(50.0)


def test_rsi_stays_within_bounds_across_regimes():
    for closes in (
        pd.Series([100.0 + i for i in range(60)]),
        pd.Series([200.0 - i for i in range(60)]),
        pd.Series([100.0] * 60),
    ):
        values = rsi(closes).dropna()
        assert values.min() >= 0
        assert values.max() <= 100


# --- VWAP ------------------------------------------------------------------


def test_rolling_vwap_tracks_the_recent_regime():
    """A trailing VWAP should reflect current price, not two hundred stale bars."""
    df = candles_to_df(_flat_then_gap())
    assert rolling_vwap(df, 20).iloc[-1] == pytest.approx(300.0, rel=1e-6)


def test_anchored_vwap_still_spans_the_whole_series():
    df = candles_to_df(_flat_then_gap())
    anchored = vwap(df).iloc[-1]
    assert 100.0 < anchored < 300.0


def test_compute_all_reports_the_trailing_vwap_and_keeps_the_anchored_one():
    snapshot = compute_all(_flat_then_gap())
    assert snapshot["vwap"] == pytest.approx(300.0, rel=1e-6)
    assert snapshot["vwap_anchored"] == pytest.approx(120.0, rel=1e-6)


# --- Directional movement --------------------------------------------------


def test_directional_movement_separates_the_two_legs():
    rising = [
        Candle(
            timestamp=datetime(2024, 1, 1, tzinfo=UTC) + timedelta(days=i),
            open=100.0 + i,
            high=101.0 + i,
            low=99.5 + i,
            close=100.8 + i,
            volume=1_000.0,
        )
        for i in range(60)
    ]
    df = candles_to_df(rising)
    di_plus, di_minus, adx_line = directional_movement(df)
    assert di_plus.iloc[-1] > di_minus.iloc[-1]
    assert adx_line.iloc[-1] > 0


def test_compute_all_exposes_both_di_legs():
    snapshot = compute_all(_flat_then_gap())
    assert "di_plus" in snapshot
    assert "di_minus" in snapshot


# --- Options chain metrics -------------------------------------------------

NEAR = date(2024, 3, 15)
FAR = date(2026, 1, 16)


def _chain() -> list[OptionContract]:
    """Front expiry is call-heavy; a single LEAP put carries enormous open interest."""
    return [
        OptionContract(symbol="c1", underlying="X", expiration=NEAR, strike=100,
                       option_type="call", open_interest=10_000),
        OptionContract(symbol="p1", underlying="X", expiration=NEAR, strike=100,
                       option_type="put", open_interest=100),
        OptionContract(symbol="p2", underlying="X", expiration=FAR, strike=200,
                       option_type="put", open_interest=500_000),
    ]


def test_front_expiration_picks_the_nearest_date():
    assert front_expiration(_chain()) == NEAR
    assert front_expiration([]) is None


def test_for_expiration_slices_to_one_date():
    assert len(for_expiration(_chain())) == 2
    assert len(for_expiration(_chain(), FAR)) == 1


def test_put_call_ratio_is_scoped_to_one_expiration():
    """A distant LEAP must not invert the near-term positioning read."""
    ratio = put_call_ratio(_chain())
    assert ratio == pytest.approx(0.01)
    blended = put_call_ratio(_chain(), all_expirations=True)
    assert blended > 1.0
    assert ratio != blended


def test_max_pain_is_scoped_to_one_expiration():
    """Options settle on their own date, so payoffs cannot be summed across dates."""
    assert max_pain(_chain()) == 100.0
    assert max_pain(_chain(), all_expirations=True) == 200.0


def test_chain_summary_reports_which_expiration_it_used():
    summary = chain_summary(_chain(), spot=100.0)
    assert summary["front_expiration"] == NEAR.isoformat()
    assert summary["front_contract_count"] == 2
    assert summary["contract_count"] == 3
    assert summary["put_call_ratio"] == pytest.approx(0.01)
    assert summary["put_call_ratio_all_expirations"] > 1.0


def test_chain_metrics_tolerate_an_empty_chain():
    assert put_call_ratio([]) is None
    assert max_pain([]) is None
