"""Tests for market calendar and candlestick trend context."""

from __future__ import annotations

from datetime import date, datetime

from app.analysis.candles import detect_candles
from app.analysis.options_expiry import pick_expiration
from app.schemas.models import Candle
from app.utils.market_calendar import (
    US_EASTERN,
    is_trading_session,
    is_weekday,
    market_today,
)


def _candle(day: int, close: float, *, open_: float | None = None) -> Candle:
    o = open_ if open_ is not None else close - 0.5
    return Candle(
        timestamp=datetime(2026, 8, day, 16, 0, tzinfo=US_EASTERN),
        open=o,
        high=max(o, close) + 0.5,
        low=min(o, close) - 0.5,
        close=close,
        volume=1_000_000,
    )


def test_market_today_uses_eastern():
    assert isinstance(market_today(), date)


def test_is_weekday():
    assert is_weekday(date(2026, 8, 3))  # Monday
    assert not is_weekday(date(2026, 8, 2))  # Sunday


def test_is_trading_session_weekend_false():
    saturday = datetime(2026, 8, 2, 12, 0, tzinfo=US_EASTERN)
    assert not is_trading_session(saturday)


def test_is_trading_session_midday_true():
    monday_noon = datetime(2026, 8, 3, 12, 0, tzinfo=US_EASTERN)
    assert is_trading_session(monday_noon)


def test_pick_expiration_prefers_min_dte():
    today = date(2026, 8, 3)
    expiries = [date(2026, 8, 4), date(2026, 8, 15), date(2026, 9, 19)]
    chosen = pick_expiration(expiries, min_dte=7, as_of=today)
    assert chosen == date(2026, 8, 15)


def test_hammer_requires_prior_decline():
    # Decline into the hammer bar.
    candles = [
        _candle(1, 110),
        _candle(2, 105),
        _candle(3, 100),
        _candle(4, 95),
        _candle(5, 90),
        Candle(
            timestamp=datetime(2026, 8, 6, 16, 0, tzinfo=US_EASTERN),
            open=89.5,
            high=90.2,
            low=85.0,
            close=90.0,
            volume=2_000_000,
        ),
    ]
    names = [p["name"] for p in detect_candles(candles)]
    assert "Hammer" in names


def test_hammer_suppressed_after_uptrend():
    candles = [
        _candle(1, 90),
        _candle(2, 95),
        _candle(3, 100),
        _candle(4, 105),
        _candle(5, 110),
        Candle(
            timestamp=datetime(2026, 8, 6, 16, 0, tzinfo=US_EASTERN),
            open=108,
            high=111,
            low=105,
            close=110,
            volume=2_000_000,
        ),
    ]
    names = [p["name"] for p in detect_candles(candles)]
    assert "Hammer" not in names
