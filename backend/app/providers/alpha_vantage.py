"""Alpha Vantage market provider — emergency fallback only (25 req/day)."""

from __future__ import annotations

from datetime import UTC, datetime

from app.providers.base import MarketDataProvider
from app.providers.http import http_get
from app.schemas.models import Candle, Quote
from app.schemas.sourced import Sourced


class AlphaVantageMarketProvider(MarketDataProvider):
    name = "alpha-vantage"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    async def get_quote(self, symbol: str) -> Sourced[Quote] | None:
        resp = await http_get(
            "https://www.alphavantage.co/query",
            params={
                "function": "GLOBAL_QUOTE",
                "symbol": symbol.upper(),
                "apikey": self.api_key,
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        q = resp.json().get("Global Quote") or {}
        price = q.get("05. price")
        if not price:
            return None
        return Sourced.of(
            Quote(
                symbol=symbol.upper(),
                price=float(price),
                change_pct=float(q["10. change percent"].rstrip("%"))
                if q.get("10. change percent")
                else None,
                volume=float(q["06. volume"]) if q.get("06. volume") else None,
            ),
            self.name,
            note="25 requests/day free tier — emergency fallback only",
        )

    async def get_ohlcv(
        self,
        symbol: str,
        *,
        period: str = "6mo",
        interval: str = "1d",
    ) -> Sourced[list[Candle]] | None:
        resp = await http_get(
            "https://www.alphavantage.co/query",
            params={
                "function": "TIME_SERIES_DAILY_ADJUSTED",
                "symbol": symbol.upper(),
                "outputsize": "compact",
                "apikey": self.api_key,
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        series = resp.json().get("Time Series (Daily)") or {}
        candles: list[Candle] = []
        for day, row in sorted(series.items()):
            candles.append(
                Candle(
                    timestamp=datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=UTC),
                    open=float(row["1. open"]),
                    high=float(row["2. high"]),
                    low=float(row["3. low"]),
                    close=float(row["4. close"]),
                    volume=float(row["6. volume"]),
                )
            )
        if not candles:
            return None
        return Sourced.of(candles, self.name, note="25 requests/day free tier")
