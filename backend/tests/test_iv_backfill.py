"""Tests for IV backfill helpers (BS invert on historical bars)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.analysis.greeks import black_scholes
from app.analysis.iv_history import (
    backfill_iv_from_bars,
    iv_from_option_bar,
    iv_rank_percentile,
    upsert_iv,
)
from app.db.models import Base
from app.schemas.models import Candle
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as sess:
        yield sess
    await engine.dispose()


def _candles(closes: list[float], *, days_ago_start: int = 30) -> list[Candle]:
    """Build candles ending ``days_ago_start`` days before today."""
    end = datetime.now(UTC) - timedelta(days=days_ago_start)
    start = end - timedelta(days=len(closes) - 1)
    out: list[Candle] = []
    price = closes[0]
    for i, close in enumerate(closes):
        out.append(
            Candle(
                timestamp=start + timedelta(days=i),
                open=price,
                high=max(price, close) + 0.5,
                low=min(price, close) - 0.5,
                close=float(close),
                volume=1_000_000,
            )
        )
        price = close
    return out


def test_iv_from_option_bar_roundtrip():
    spot, strike = 100.0, 100.0
    expiration = date(2024, 6, 1)
    as_of = date(2024, 3, 1)
    true_iv = 0.28
    t = (expiration - as_of).days / 365.0
    bar_close = black_scholes(spot, strike, t, 0.045, true_iv, "call").price
    solved = iv_from_option_bar(
        spot=spot,
        strike=strike,
        expiration=expiration,
        bar_close=bar_close,
        as_of=as_of,
    )
    assert solved is not None
    assert abs(solved - true_iv) < 1e-3


@pytest.mark.asyncio
async def test_backfill_writes_snapshots(session):
    candles = _candles([100 + (i % 5) for i in range(30)])
    sample_day = candles[0].timestamp.date()
    expiration = sample_day + timedelta(days=90)
    spot = candles[0].close
    strike = 100.0
    t = (expiration - sample_day).days / 365.0
    bar_close = black_scholes(spot, strike, t, 0.045, 0.25, "call").price

    alpaca = MagicMock()
    alpaca.pick_atm_call = AsyncMock(
        return_value={
            "symbol": "TEST240621C00100000",
            "expiration_date": expiration.isoformat(),
            "strike_price": str(strike),
        }
    )
    alpaca.get_option_bars = AsyncMock(
        return_value={"TEST240621C00100000": [{"c": bar_close}]}
    )

    summary = await backfill_iv_from_bars(
        session,
        alpaca,
        "TEST",
        candles,
        max_days_per_run=5,
    )
    assert summary["written"] >= 1
    assert summary["symbol"] == "TEST"


@pytest.mark.asyncio
async def test_iv_rank_requires_min_samples(session):
    start = date.today() - timedelta(days=25)
    for i in range(19):
        await upsert_iv(
            session,
            symbol="ABC",
            as_of=start + timedelta(days=i),
            iv=0.2 + i * 0.001,
            source="test",
        )
    assert await iv_rank_percentile(session, "ABC") is None

    await upsert_iv(
        session,
        symbol="ABC",
        as_of=start + timedelta(days=19),
        iv=0.25,
        source="test",
    )
    stats = await iv_rank_percentile(session, "ABC")
    assert stats is not None
    assert stats["samples"] == 20
    assert "iv_rank" in stats
