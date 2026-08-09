"""Provider protocol definitions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from app.schemas.models import Candle, InsiderTrade, NewsArticle, OptionContract, Quote
from app.schemas.sourced import Sourced


class MarketDataProvider(ABC):
    name: str

    @abstractmethod
    async def get_quote(self, symbol: str) -> Sourced[Quote] | None: ...

    @abstractmethod
    async def get_ohlcv(
        self,
        symbol: str,
        *,
        period: str = "6mo",
        interval: str = "1d",
    ) -> Sourced[list[Candle]] | None: ...


class OptionsProvider(ABC):
    name: str

    @abstractmethod
    async def get_expirations(self, symbol: str) -> Sourced[list[date]] | None: ...

    @abstractmethod
    async def get_chain(
        self,
        symbol: str,
        expiration: date | None = None,
    ) -> Sourced[list[OptionContract]] | None: ...


class NewsProvider(ABC):
    name: str

    @abstractmethod
    async def get_news(
        self,
        symbol: str | None = None,
        *,
        limit: int = 20,
    ) -> Sourced[list[NewsArticle]] | None: ...


class InsiderProvider(ABC):
    name: str

    @abstractmethod
    async def get_recent(
        self,
        *,
        limit: int = 50,
    ) -> Sourced[list[InsiderTrade]] | None: ...


class MacroProvider(ABC):
    name: str

    @abstractmethod
    async def get_series(
        self,
        series_id: str,
        *,
        limit: int = 24,
    ) -> Sourced[list[dict]] | None: ...
