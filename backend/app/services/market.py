"""Domain services that wire providers → analysis → responses."""

from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import Any, TypeVar

from dataclasses import dataclass

from app.analysis.indicators import compute_all
from app.analysis.insider_clusters import cluster_for_symbol, detect_clusters
from app.analysis.iv_history import atm_iv_from_chain, backfill_iv_from_bars, ensure_iv_rank
from app.analysis.options_metrics import chain_summary
from app.analysis.patterns import detect_patterns
from app.ai.scoring import score_symbol
from app.ai.sentiment import annotate_articles
from app.cache import TTL_CHAIN, TTL_INSIDER, TTL_NEWS, TTL_OHLCV, TTL_QUOTE, TTL_SIGNAL, cached
from app.db import repository as repo
from app.db.session import get_engine, session_scope
from app.config import get_settings
from app.providers.registry import get_registry
from app.schemas.models import (
    Candle,
    NewsArticle,
    OptionContract,
    SignalResponse,
)
from app.schemas.sourced import Sourced

logger = logging.getLogger(__name__)
T = TypeVar("T")


def as_sourced(payload: Any) -> Sourced | None:
    """Rebuild Sourced from a cache hit (dict) or pass through live results."""
    if payload is None:
        return None
    if isinstance(payload, Sourced):
        return payload
    if isinstance(payload, dict) and "value" in payload and "source" in payload:
        return Sourced.model_validate(payload)
    return None


def _list_of(model, values: Any) -> list:
    if not values:
        return []
    if isinstance(values[0], model):
        return list(values)
    return [model.model_validate(v) for v in values]


@dataclass
class InsidersBundle:
    """Sourced insider trades plus derived cluster metadata."""

    sourced: Sourced
    clusters: list[dict]

    @property
    def value(self):
        return self.sourced.value

    @property
    def source(self):
        return self.sourced.source

    @property
    def fetched_at(self):
        return self.sourced.fetched_at

    @property
    def url(self):
        return self.sourced.url

    @property
    def note(self):
        return self.sourced.note

    def model_dump(self, *, mode: str = "json") -> dict:
        return self.sourced.model_dump(mode=mode)


async def fetch_quote(symbol: str):
    registry = get_registry()

    async def _():
        return await registry.first(
            registry.market,
            lambda p: p.get_quote(symbol),
        )

    return as_sourced(await cached(f"quote:{symbol.upper()}", TTL_QUOTE, _))


async def fetch_ohlcv(symbol: str, period: str = "6mo", *, adjusted: bool = True):
    registry = get_registry()
    adj_key = "adj" if adjusted else "raw"
    key = f"ohlcv:{symbol.upper()}:{period}:{adj_key}"

    async def _():
        if not adjusted:
            for provider in registry.market:
                if provider.name == "yfinance":
                    result = await provider.get_ohlcv(symbol, period=period, adjusted=False)
                    if result is not None:
                        return result
        return await registry.first(
            registry.market,
            lambda p: p.get_ohlcv(symbol, period=period),
        )

    return as_sourced(await cached(key, TTL_OHLCV, _))


async def fetch_chain(symbol: str, expiration: date | None = None):
    registry = get_registry()
    key = f"chain:{symbol.upper()}:{expiration.isoformat() if expiration else 'near'}"

    async def _():
        return await registry.first(
            registry.options,
            lambda p: p.get_chain(symbol, expiration),
        )

    return as_sourced(await cached(key, TTL_CHAIN, _))


async def fetch_news(symbol: str | None = None, limit: int = 20):
    registry = get_registry()

    async def _():
        sourced = await registry.first(
            registry.news,
            lambda p: p.get_news(symbol, limit=limit),
        )
        if sourced is None:
            return None
        articles = await annotate_articles(list(sourced.value))
        try:
            async with session_scope() as session:
                await repo.persist_news(session, articles)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to persist news")
        return Sourced.of(articles, sourced.source, url=sourced.url, note=sourced.note)

    return as_sourced(await cached(f"news:{symbol or 'market'}:{limit}", TTL_NEWS, _))


async def fetch_insiders(limit: int = 40):
    registry = get_registry()
    settings = get_settings()

    async def _():
        sourced = await registry.first(
            registry.insiders,
            lambda p: p.get_recent(limit=limit),
        )
        if sourced is None:
            return None
        trades = list(sourced.value)

        # Enrich top filings with ownership XML (rate-limited via http client).
        edgar = registry.insiders[0] if registry.insiders else None
        if edgar and hasattr(edgar, "enrich_filing"):
            for i, trade in enumerate(trades[: settings.insider_enrich_limit]):
                if not trade.form_url or trade.shares is not None:
                    continue
                try:
                    detail = await edgar.enrich_filing(trade.form_url)
                    if detail and detail.value:
                        enriched = detail.value
                        trades[i] = enriched
                except Exception:  # noqa: BLE001
                    logger.exception("Failed to enrich Form 4 %s", trade.form_url)

        clusters = detect_clusters(trades)
        note = sourced.note
        if clusters:
            cluster_note = "; ".join(c["label"] for c in clusters[:3])
            note = f"{note or ''} Clusters: {cluster_note}".strip()

        try:
            async with session_scope() as session:
                await repo.persist_insiders(session, trades)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to persist insiders")

        payload = Sourced.of(trades, sourced.source, url=sourced.url, note=note)
        return {"sourced": payload.model_dump(mode="json"), "clusters": clusters}

    data = await cached(f"insiders:{limit}", TTL_INSIDER, _)
    if not data:
        return None
    from app.schemas.models import InsiderTrade

    if isinstance(data, dict) and "sourced" in data:
        sourced = as_sourced(data["sourced"])
        clusters = data.get("clusters") or []
    else:
        sourced = as_sourced(data)
        trades = _list_of(InsiderTrade, sourced.value if sourced else [])
        clusters = detect_clusters(trades) if trades else []

    if not sourced:
        return None
    return InsidersBundle(sourced=sourced, clusters=clusters)


def _alpaca_provider():
    registry = get_registry()
    registry.bootstrap()
    for provider in registry.options:
        if provider.name == "alpaca":
            return provider
    return None


async def build_signal(symbol: str) -> SignalResponse | None:
    settings = get_settings()

    async def _produce():
        ohlcv = await fetch_ohlcv(symbol)
        if not ohlcv:
            return None
        candles = _list_of(Candle, ohlcv.value)
        ohlcv = Sourced.of(candles, ohlcv.source, url=ohlcv.url, note=ohlcv.note)

        chain = await fetch_chain(symbol)
        contracts = None
        options_source = None
        if chain:
            contracts = _list_of(OptionContract, chain.value)
            options_source = chain.source

        news = await fetch_news(symbol, limit=10)
        if not news or not news.value:
            news = await fetch_news(None, limit=10)
        articles = None
        news_source = None
        if news:
            articles = _list_of(NewsArticle, news.value)
            news_source = news.source

        insiders = await fetch_insiders(limit=40)
        insider_trades = None
        insider_cluster = None
        if insiders and insiders.value:
            from app.schemas.models import InsiderTrade

            insider_trades = _list_of(InsiderTrade, insiders.value)
            clusters = insiders.clusters or detect_clusters(
                insider_trades, symbol=symbol
            )
            insider_cluster = cluster_for_symbol(clusters, symbol)

        iv_rank = None
        iv_stats = None
        if contracts or candles:
            spot = candles[-1].close
            live_iv = atm_iv_from_chain(
                contracts,
                spot,
                min_dte=settings.min_option_dte,
            ) if contracts else None
            get_engine()
            from app.db.session import _session_factory

            if _session_factory:
                async with _session_factory() as session:
                    iv_stats = await ensure_iv_rank(
                        session,
                        symbol,
                        alpaca=_alpaca_provider(),
                        candles=candles,
                        live_iv=live_iv,
                        live_source=options_source or "options",
                        max_backfill_days=settings.iv_backfill_days_per_run,
                    )
                    if iv_stats:
                        iv_rank = iv_stats["iv_rank"]

        return score_symbol(
            symbol,
            candles,
            candle_source=ohlcv.source,
            contracts=contracts,
            options_source=options_source,
            news=articles,
            news_source=news_source,
            iv_rank=iv_rank,
            iv_stats=iv_stats,
            insider_cluster=insider_cluster,
        )

    result = await cached(f"signal:{symbol.upper()}", TTL_SIGNAL, _produce)
    if result is None:
        return None
    if isinstance(result, dict):
        return SignalResponse.model_validate(result)
    return result


async def backfill_iv_universe(symbols: list[str] | None = None) -> list[dict]:
    """Worker entry: backfill IV history for scanner universe symbols."""
    settings = get_settings()
    alpaca = _alpaca_provider()
    if alpaca is None:
        return []

    targets = symbols or settings.universe
    results: list[dict] = []
    for symbol in targets:
        try:
            ohlcv = await fetch_ohlcv(symbol, period="1y", adjusted=False)
            if not ohlcv:
                continue
            candles = _list_of(Candle, ohlcv.value)
            async with session_scope() as session:
                summary = await backfill_iv_from_bars(
                    session,
                    alpaca,
                    symbol,
                    candles,
                    max_days_per_run=settings.iv_backfill_days_per_run,
                )
                results.append(summary)
        except Exception:  # noqa: BLE001
            logger.exception("IV universe backfill failed for %s", symbol)
    return results


async def get_scanner_results(symbols: list[str] | None = None) -> list[SignalResponse]:
    """Read cached signals for the universe — does not persist or force a full rescan."""
    settings = get_settings()
    targets = symbols or settings.universe
    sem = asyncio.Semaphore(settings.scan_concurrency)

    async def _one(symbol: str) -> SignalResponse | None:
        async with sem:
            try:
                return await build_signal(symbol)
            except Exception:  # noqa: BLE001
                logger.exception("Scanner read failed for %s", symbol)
                return None

    gathered = await asyncio.gather(
        *(_one(symbol) for symbol in targets),
        return_exceptions=True,
    )
    results: list[SignalResponse] = []
    for item in gathered:
        if isinstance(item, SignalResponse):
            results.append(item)
    results.sort(key=lambda s: s.confidence, reverse=True)
    return results


async def scan_universe(symbols: list[str]) -> list[SignalResponse]:
    settings = get_settings()
    sem = asyncio.Semaphore(settings.scan_concurrency)

    async def _scan_one(symbol: str) -> SignalResponse | None:
        async with sem:
            try:
                signal = await build_signal(symbol)
                if signal:
                    try:
                        async with session_scope() as session:
                            await repo.persist_scan(
                                session,
                                signal,
                                retention_days=settings.scan_retention_days,
                            )
                    except Exception:  # noqa: BLE001
                        logger.exception("Failed to persist scan for %s", symbol)
                return signal
            except Exception:  # noqa: BLE001
                logger.exception("Scan failed for %s", symbol)
                return None

    gathered = await asyncio.gather(
        *(_scan_one(symbol) for symbol in symbols),
        return_exceptions=True,
    )
    results: list[SignalResponse] = []
    for item in gathered:
        if isinstance(item, SignalResponse):
            results.append(item)
        elif isinstance(item, Exception):
            logger.error("Scan task raised: %s", item)
    results.sort(key=lambda s: s.confidence, reverse=True)
    return results


async def ticker_detail(symbol: str) -> dict:
    ohlcv, quote, chain, signal, news = await asyncio.gather(
        fetch_ohlcv(symbol, period="1y"),
        fetch_quote(symbol),
        fetch_chain(symbol),
        build_signal(symbol),
        fetch_news(symbol, limit=10),
    )

    candles = []
    indicators = None
    patterns = None
    if ohlcv:
        candles_raw = _list_of(Candle, ohlcv.value)
        candles = [c.model_dump(mode="json") for c in candles_raw]
        indicators = compute_all(candles_raw)
        patterns = detect_patterns(candles_raw)

    options_payload = None
    if chain:
        contracts = _list_of(OptionContract, chain.value)
        spot = indicators["close"] if indicators else (contracts[0].strike if contracts else 0)
        options_payload = {
            "source": chain.source,
            "note": chain.note,
            "summary": chain_summary(contracts, spot),
            "contracts": [c.model_dump(mode="json") for c in contracts[:200]],
        }

    return {
        "symbol": symbol.upper(),
        "quote": quote.model_dump(mode="json") if quote else None,
        "candles": {"source": ohlcv.source if ohlcv else None, "data": candles},
        "indicators": indicators,
        "patterns": patterns,
        "options": options_payload,
        "signal": signal.model_dump(mode="json") if signal else None,
        "news": news.model_dump(mode="json") if news else None,
    }
