"""Database session + init."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.db.models import Base

_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine():
    global _engine, _session_factory
    if _engine is None:
        settings = get_settings()
        connect_args = {}
        if settings.database_url.startswith("sqlite"):
            connect_args = {"check_same_thread": False}
        _engine = create_async_engine(settings.database_url, echo=False, connect_args=connect_args)
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


async def init_db() -> None:
    """Ensure tables exist for local SQLite boots.

    Prefer `alembic upgrade head` for Postgres (Docker). `create_all` is
    idempotent and does not replace migrations for schema evolution.
    """
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def session_scope() -> AsyncGenerator[AsyncSession, None]:
    """Short-lived session for workers / service-side writes."""
    get_engine()
    if _session_factory is None:
        raise RuntimeError("Database session factory not initialized")
    async with _session_factory() as session:
        yield session


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    get_engine()
    if _session_factory is None:
        raise RuntimeError("Database session factory not initialized")
    async with _session_factory() as session:
        yield session
