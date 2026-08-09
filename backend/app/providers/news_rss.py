"""RSS news aggregator (Reuters, MarketWatch, CNBC, Yahoo, Fed, SEC — keyless)."""

from __future__ import annotations

from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from time import mktime

import feedparser

from app.providers.base import NewsProvider
from app.schemas.models import NewsArticle
from app.schemas.sourced import Sourced

FEEDS = [
    ("Reuters Business", "https://feeds.reuters.com/reuters/businessNews"),
    ("MarketWatch", "https://feeds.marketwatch.com/marketwatch/topstories/"),
    ("CNBC", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114"),
    ("Yahoo Finance", "https://finance.yahoo.com/news/rssindex"),
    ("Federal Reserve", "https://www.federalreserve.gov/feeds/press_all.xml"),
    ("SEC Press", "https://www.sec.gov/news/pressreleases.rss"),
]


class RssNewsProvider(NewsProvider):
    name = "news-rss"

    async def get_news(
        self,
        symbol: str | None = None,
        *,
        limit: int = 20,
    ) -> Sourced[list[NewsArticle]] | None:
        import asyncio

        articles: list[NewsArticle] = []
        for source_name, url in FEEDS:
            try:
                feed = await asyncio.to_thread(feedparser.parse, url)
            except Exception:  # noqa: BLE001
                continue
            for entry in feed.entries[:10]:
                published = _parse_date(entry)
                title = getattr(entry, "title", "") or ""
                summary = getattr(entry, "summary", "") or ""
                if symbol:
                    blob = f"{title} {summary}".upper()
                    # Keep symbol matches; also keep general market headlines
                    # that don't name another obvious ticker filter failure.
                    if symbol.upper() not in blob and len(articles) > 8:
                        continue
                articles.append(
                    NewsArticle(
                        title=title,
                        url=getattr(entry, "link", "") or "",
                        source=source_name,
                        published_at=published,
                        summary=summary or None,
                        related_symbols=[symbol.upper()] if symbol else [],
                    )
                )

        articles.sort(key=lambda a: a.published_at or datetime.min.replace(tzinfo=UTC), reverse=True)
        articles = articles[:limit]
        if not articles:
            return None
        return Sourced.of(articles, self.name, note="Aggregated public RSS feeds")


def _parse_date(entry) -> datetime | None:
    if getattr(entry, "published_parsed", None):
        return datetime.fromtimestamp(mktime(entry.published_parsed), tz=UTC)
    if getattr(entry, "published", None):
        try:
            dt = parsedate_to_datetime(entry.published)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt
        except (TypeError, ValueError, IndexError):
            return None
    return None
