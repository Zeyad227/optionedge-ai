"""Twelve Data market provider (keyed backup)."""

from __future__ import annotations

from datetime import UTC, datetime

from app.providers.base import MarketDataProvider
from app.providers.http import http_get
from app.schemas.models import Candle, Quote
from app.schemas.sourced import Sourced


class TwelveDataMarketProvider(MarketDataProvider):
    name = "twelve-data"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    async def get_quote(self, symbol: str) -> Sourced[Quote] | None:
        resp = await http_get(
            "https://api.twelvedata.com/quote",
            params={"symbol": symbol.upper(), "apikey": self.api_key},
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") == "error" or "close" not in data:
            return None
        price = float(data["close"])
        prev = float(data["previous_close"]) if data.get("previous_close") else None
        change = ((price - prev) / prev * 100) if prev else None
        return Sourced.of(
            Quote(
                symbol=symbol.upper(),
                price=price,
                change_pct=change,
                volume=float(data["volume"]) if data.get("volume") else None,
            ),
            self.name,
            url="https://twelvedata.com/docs",
        )

    async def get_ohlcv(
        self,
        symbol: str,
        *,
        period: str = "6mo",
        interval: str = "1d",
    ) -> Sourced[list[Candle]] | None:
        size_map = {"1mo": 22, "3mo": 66, "6mo": 132, "1y": 252, "2y": 504}
        resp = await http_get(
            "https://api.twelvedata.com/time_series",
            params={
                "symbol": symbol.upper(),
                "interval": "1day" if interval == "1d" else interval,
                "outputsize": size_map.get(period, 132),
                "apikey": self.api_key,
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        values = data.get("values") or []
        candles: list[Candle] = []
        for row in reversed(values):
            candles.append(
                Candle(
                    timestamp=datetime.strptime(row["datetime"], "%Y-%m-%d").replace(tzinfo=UTC),
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row.get("volume") or 0),
                )
            )
        if not candles:
            return None
        return Sourced.of(candles, self.name)
