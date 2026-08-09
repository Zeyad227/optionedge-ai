"""Persistence + cache contract tests (SQLite in-memory)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.cache.redis_cache import MemoryCache, cached, reset_cache_for_tests
from app.db.models import Base
from app.db.repository import persist_insiders, persist_news, persist_scan, recent_news
from app.schemas.models import InsiderTrade, NewsArticle, SignalResponse


@pytest.fixture
async def session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as sess:
        yield sess
    await engine.dispose()


@pytest.mark.asyncio
async def test_persist_news_upsert(session: AsyncSession):
    articles = [
        NewsArticle(
            title="Hello",
            url="https://example.com/a",
            source="test",
            sentiment="Bullish",
            sentiment_score=0.8,
            impact=0.5,
        )
    ]
    assert await persist_news(session, articles) == 1
    assert await persist_news(session, articles) == 0  # upsert, not insert
    rows = await recent_news(session, limit=10)
    assert len(rows) == 1
    assert rows[0].title == "Hello"
    assert rows[0].sentiment == "Bullish"


@pytest.mark.asyncio
async def test_persist_insiders_and_scan(session: AsyncSession):
    trades = [
        InsiderTrade(
            insider_name="Ada",
            company="Example Corp",
            symbol="EX",
            transaction_type="P",
            form_url="https://www.sec.gov/Archives/example.xml",
            sentiment="Bullish",
            filed_at=datetime.now(UTC),
        )
    ]
    assert await persist_insiders(session, trades) == 1
    assert await persist_insiders(session, trades) == 0

    signal = SignalResponse(
        symbol="EX",
        action="Buy",
        trend="Bullish",
        confidence=70.0,
        generated_at=datetime.now(UTC),
        sources=["test"],
    )
    await persist_scan(session, signal)
    await persist_scan(session, signal)  # append another snapshot


@pytest.mark.asyncio
async def test_cache_single_flight_one_producer(monkeypatch):
    reset_cache_for_tests()
    monkeypatch.setenv("CACHE_BACKEND", "memory")
    from app.config import get_settings

    get_settings.cache_clear()

    calls = {"n": 0}

    async def factory():
        calls["n"] += 1
        return {"ok": True}

    # Concurrent callers should share one producer via _singleflight
    import asyncio

    results = await asyncio.gather(
        cached("sf:test", 60, factory),
        cached("sf:test", 60, factory),
        cached("sf:test", 60, factory),
    )
    assert results == [{"ok": True}, {"ok": True}, {"ok": True}]
    assert calls["n"] == 1

    # Second wave hits the store without calling factory again
    hit = await cached("sf:test", 60, factory)
    assert hit == {"ok": True}
    assert calls["n"] == 1
    reset_cache_for_tests()


@pytest.mark.asyncio
async def test_cache_negative_result_short_circuits_factory(monkeypatch):
    reset_cache_for_tests()
    monkeypatch.setenv("CACHE_BACKEND", "memory")
    from app.config import get_settings

    get_settings.cache_clear()

    calls = {"n": 0}

    async def factory():
        calls["n"] += 1
        return None

    assert await cached("neg:test", 60, factory) is None
    assert calls["n"] == 1
    assert await cached("neg:test", 60, factory) is None
    assert calls["n"] == 1
    reset_cache_for_tests()


@pytest.mark.asyncio
async def test_memory_cache_ttl_expiry():
    cache = MemoryCache()
    await cache.set("k", {"v": 1}, ttl=1)
    assert await cache.get("k") == {"v": 1}
    # Force expiry
    import time

    cache._store["k"] = (time.time() - 1, {"v": 1})
    assert await cache.get("k") is None
