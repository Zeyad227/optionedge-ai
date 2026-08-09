"""Provider registry with declared fallback order."""

from __future__ import annotations

import logging
from typing import Callable, Sequence, TypeVar

from app.config import Settings, get_settings
from app.providers.base import (
    InsiderProvider,
    MacroProvider,
    MarketDataProvider,
    NewsProvider,
    OptionsProvider,
)
from app.schemas.sourced import Sourced

logger = logging.getLogger(__name__)
T = TypeVar("T")


class ProviderRegistry:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.market: list[MarketDataProvider] = []
        self.options: list[OptionsProvider] = []
        self.news: list[NewsProvider] = []
        self.insiders: list[InsiderProvider] = []
        self.macro: list[MacroProvider] = []
        self._bootstrapped = False

    def bootstrap(self) -> None:
        if self._bootstrapped:
            return
        # Lazy imports so missing optional deps don't break import-time.
        from app.providers.alpaca import AlpacaOptionsProvider
        from app.providers.finnhub import FinnhubNewsProvider
        from app.providers.fred import FredMacroProvider
        from app.providers.news_rss import RssNewsProvider
        from app.providers.sec_edgar import SecEdgarInsiderProvider
        from app.providers.stooq import StooqMarketProvider
        from app.providers.tradier import TradierOptionsProvider
        from app.providers.yfinance_ import YFinanceMarketProvider, YFinanceOptionsProvider

        self.market = [YFinanceMarketProvider(), StooqMarketProvider()]
        if self.settings.twelve_data_api_key:
            from app.providers.twelve_data import TwelveDataMarketProvider

            self.market.append(TwelveDataMarketProvider(self.settings.twelve_data_api_key))
        if self.settings.alpha_vantage_api_key:
            from app.providers.alpha_vantage import AlphaVantageMarketProvider

            self.market.append(AlphaVantageMarketProvider(self.settings.alpha_vantage_api_key))

        self.options = []
        if self.settings.alpaca_configured:
            self.options.append(
                AlpacaOptionsProvider(
                    self.settings.alpaca_api_key_id,
                    self.settings.alpaca_api_secret_key,
                    feed=self.settings.alpaca_data_feed,
                )
            )
        self.options.append(YFinanceOptionsProvider())
        if self.settings.tradier_sandbox_token:
            self.options.append(TradierOptionsProvider(self.settings.tradier_sandbox_token))

        self.news = [RssNewsProvider()]
        if self.settings.finnhub_api_key:
            self.news.insert(0, FinnhubNewsProvider(self.settings.finnhub_api_key))

        self.insiders = [
            SecEdgarInsiderProvider(user_agent=self.settings.sec_edgar_user_agent)
        ]

        self.macro = []
        if self.settings.fred_api_key:
            self.macro.append(FredMacroProvider(self.settings.fred_api_key))

        self._bootstrapped = True

    def status(self) -> dict[str, bool]:
        self.bootstrap()
        return {
            "alpaca": self.settings.alpaca_configured,
            "yfinance": True,
            "stooq": True,
            "tradier": bool(self.settings.tradier_sandbox_token),
            "finnhub": bool(self.settings.finnhub_api_key),
            "fred": bool(self.settings.fred_api_key),
            "twelve_data": bool(self.settings.twelve_data_api_key),
            "alpha_vantage": bool(self.settings.alpha_vantage_api_key),
            "sec_edgar": True,
            "news_rss": True,
        }

    async def first(
        self,
        providers: Sequence[object],
        call: Callable,
    ) -> Sourced[T] | None:
        """Try providers in order; return the first non-None Sourced result."""
        self.bootstrap()
        last_error: Exception | None = None
        for provider in providers:
            try:
                result = await call(provider)
                if result is not None:
                    return result
            except Exception as exc:  # noqa: BLE001 — fall through to next provider
                last_error = exc
                logger.warning("%s failed: %s", getattr(provider, "name", provider), exc)
        if last_error:
            logger.error("All providers failed; last error: %s", last_error)
        return None


_registry: ProviderRegistry | None = None


def get_registry() -> ProviderRegistry:
    global _registry
    if _registry is None:
        _registry = ProviderRegistry()
        _registry.bootstrap()
    return _registry
