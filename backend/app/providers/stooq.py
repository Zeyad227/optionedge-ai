"""Stooq end-of-day equity data fallback (keyless)."""

from __future__ import annotations

from datetime import UTC, datetime
from io import StringIO

import pandas as pd

from app.providers.base import MarketDataProvider
from app.providers.http import http_get
from app.providers.numeric import finite
from app.schemas.models import Candle, Quote
from app.schemas.sourced import Sourced


def _stooq_symbol(symbol: str) -> str:
    s = symbol.lower()
    if not s.endswith(".us") and symbol.isalpha():
        return f"{s}.us"
    return s


class StooqMarketProvider(MarketDataProvider):
    name = "stooq"

    async def get_quote(self, symbol: str) -> Sourced[Quote] | None:
        ohlcv = await self.get_ohlcv(symbol, period="5d")
        if not ohlcv or not ohlcv.value:
            return None
        last = ohlcv.value[-1]
        prev = ohlcv.value[-2] if len(ohlcv.value) > 1 else None
        change = None
        if prev and prev.close:
            change = (last.close - prev.close) / prev.close * 100
        return Sourced.of(
            Quote(symbol=symbol.upper(), price=last.close, change_pct=change, volume=last.volume),
            self.name,
            url=f"https://stooq.com/q/?s={_stooq_symbol(symbol)}",
        )

    async def get_ohlcv(
        self,
        symbol: str,
        *,
        period: str = "6mo",
        interval: str = "1d",
    ) -> Sourced[list[Candle]] | None:
        if interval != "1d":
            return None
        url = f"https://stooq.com/q/d/l/?s={_stooq_symbol(symbol)}&i=d"
        resp = await http_get(url, timeout=30.0, follow_redirects=True)
        resp.raise_for_status()
        text = resp.text.strip()
        if not text or "Date" not in text:
            return None
        df = pd.read_csv(StringIO(text))
        if df.empty:
            return None
        keep = {"1mo": 22, "3mo": 66, "6mo": 132, "1y": 252, "2y": 504, "5y": 1260}.get(period, 132)
        df = df.tail(keep)
        candles: list[Candle] = []
        for _, row in df.iterrows():
            ohlc = [finite(row.get(field)) for field in ("Open", "High", "Low", "Close")]
            if any(value is None for value in ohlc):
                continue
            open_, high, low, close = ohlc
            candles.append(
                Candle(
                    timestamp=datetime.strptime(str(row["Date"]), "%Y-%m-%d").replace(tzinfo=UTC),
                    open=open_,
                    high=high,
                    low=low,
                    close=close,
                    volume=finite(row.get("Volume")) or 0.0,
                )
            )
        if not candles:
            return None
        return Sourced.of(candles, self.name, url=url)
