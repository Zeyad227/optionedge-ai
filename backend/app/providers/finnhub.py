"""Finnhub news provider."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.providers.base import NewsProvider
from app.providers.http import http_get
from app.schemas.models import NewsArticle
from app.schemas.sourced import Sourced


class FinnhubNewsProvider(NewsProvider):
    name = "finnhub"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    async def get_news(
        self,
        symbol: str | None = None,
        *,
        limit: int = 20,
    ) -> Sourced[list[NewsArticle]] | None:
        if symbol:
            to = datetime.now(UTC).date()
            frm = to - timedelta(days=7)
            resp = await http_get(
                "https://finnhub.io/api/v1/company-news",
                params={
                    "symbol": symbol.upper(),
                    "from": frm.isoformat(),
                    "to": to.isoformat(),
                    "token": self.api_key,
                },
                timeout=30.0,
            )
        else:
            resp = await http_get(
                "https://finnhub.io/api/v1/news",
                params={"category": "general", "token": self.api_key},
                timeout=30.0,
            )
        resp.raise_for_status()
        items = resp.json() or []

        articles: list[NewsArticle] = []
        for item in items[:limit]:
            ts = item.get("datetime")
            published = datetime.fromtimestamp(ts, tz=UTC) if ts else None
            articles.append(
                NewsArticle(
                    title=item.get("headline") or item.get("title") or "",
                    url=item.get("url") or "",
                    source=item.get("source") or self.name,
                    published_at=published,
                    summary=item.get("summary"),
                    related_symbols=[symbol.upper()] if symbol else [],
                )
            )
        if not articles:
            return None
        return Sourced.of(articles, self.name, url="https://finnhub.io/docs/api/company-news")
