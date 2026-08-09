"""Persistence helpers for news, insiders, and scan results."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import InsiderFilingRow, NewsArticleRow, ScanResultRow
from app.schemas.models import InsiderTrade, NewsArticle, SignalResponse

DEFAULT_SCAN_RETENTION_DAYS = 30


def _url_hash(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


async def persist_news(session: AsyncSession, articles: list[NewsArticle]) -> int:
    """Upsert news articles by URL hash. Returns number of newly inserted rows."""
    candidates = [a for a in articles if a.url]
    if not candidates:
        return 0

    digests = {_url_hash(a.url) for a in candidates}
    result = await session.scalars(
        select(NewsArticleRow).where(NewsArticleRow.url_hash.in_(digests))
    )
    existing_by_hash = {row.url_hash: row for row in result.all()}

    inserted = 0
    for article in candidates:
        digest = _url_hash(article.url)
        existing = existing_by_hash.get(digest)
        if existing:
            existing.title = article.title
            existing.source = article.source
            existing.published_at = article.published_at
            existing.sentiment = article.sentiment
            existing.sentiment_score = article.sentiment_score
            existing.impact = article.impact
        else:
            session.add(
                NewsArticleRow(
                    url_hash=digest,
                    title=article.title,
                    url=article.url,
                    source=article.source,
                    published_at=article.published_at,
                    sentiment=article.sentiment,
                    sentiment_score=article.sentiment_score,
                    impact=article.impact,
                )
            )
            inserted += 1
    await session.commit()
    return inserted


async def persist_insiders(session: AsyncSession, trades: list[InsiderTrade]) -> int:
    """Upsert Form 4 rows by form_url. Returns number newly inserted."""
    candidates = [t for t in trades if t.form_url]
    if not candidates:
        return 0

    form_urls = [t.form_url for t in candidates]
    result = await session.scalars(
        select(InsiderFilingRow).where(InsiderFilingRow.form_url.in_(form_urls))
    )
    existing_by_url = {row.form_url: row for row in result.all()}

    inserted = 0
    for trade in candidates:
        form_url = trade.form_url or ""
        existing = existing_by_url.get(form_url)
        raw = trade.model_dump(mode="json")
        if existing:
            existing.company = trade.company
            existing.symbol = trade.symbol
            existing.insider_name = trade.insider_name
            existing.sentiment = trade.sentiment
            existing.filed_at = trade.filed_at
            existing.raw_json = json.dumps(raw)
        else:
            session.add(
                InsiderFilingRow(
                    form_url=form_url,
                    company=trade.company,
                    symbol=trade.symbol,
                    insider_name=trade.insider_name,
                    sentiment=trade.sentiment,
                    filed_at=trade.filed_at,
                    raw_json=json.dumps(raw),
                )
            )
            inserted += 1
    await session.commit()
    return inserted


async def prune_old_scans(
    session: AsyncSession,
    *,
    retention_days: int = DEFAULT_SCAN_RETENTION_DAYS,
) -> int:
    """Delete scan snapshots older than retention window. Returns rows removed."""
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)
    result = await session.execute(
        delete(ScanResultRow).where(ScanResultRow.generated_at < cutoff)
    )
    await session.commit()
    return result.rowcount or 0


async def persist_scan(
    session: AsyncSession,
    signal: SignalResponse,
    *,
    retention_days: int = DEFAULT_SCAN_RETENTION_DAYS,
) -> None:
    """Append a scan result snapshot for the symbol."""
    session.add(
        ScanResultRow(
            symbol=signal.symbol.upper(),
            action=signal.action,
            confidence=signal.confidence,
            trend=signal.trend,
            risk_reward=signal.risk_reward,
            generated_at=signal.generated_at or datetime.now(UTC),
            payload_json=signal.model_dump_json(),
        )
    )
    await session.commit()
    await prune_old_scans(session, retention_days=retention_days)


async def recent_news(session: AsyncSession, *, limit: int = 50) -> list[NewsArticleRow]:
    result = await session.scalars(
        select(NewsArticleRow).order_by(NewsArticleRow.id.desc()).limit(limit)
    )
    return list(result.all())


async def recent_insiders(session: AsyncSession, *, limit: int = 50) -> list[InsiderFilingRow]:
    result = await session.scalars(
        select(InsiderFilingRow).order_by(InsiderFilingRow.id.desc()).limit(limit)
    )
    return list(result.all())


async def latest_scans(session: AsyncSession, *, limit: int = 50) -> list[ScanResultRow]:
    result = await session.scalars(
        select(ScanResultRow).order_by(ScanResultRow.generated_at.desc()).limit(limit)
    )
    return list(result.all())
