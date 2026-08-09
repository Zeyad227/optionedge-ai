"""Lightweight live probes for provider reachability (cached)."""

from __future__ import annotations

import asyncio
import logging
import time

from app.config import Settings

logger = logging.getLogger(__name__)

_PROBE_TIMEOUT = 5.0
_CACHE_TTL = 60.0
_cache: tuple[float, dict[str, bool]] | None = None


async def _probe(coro) -> bool:
    try:
        result = await asyncio.wait_for(coro, timeout=_PROBE_TIMEOUT)
        return result is not None
    except Exception:  # noqa: BLE001
        return False


async def check_provider_health(settings: Settings, registry) -> dict[str, bool]:
    """Return provider names mapped to whether a live probe succeeded."""
    global _cache
    now = time.monotonic()
    if _cache is not None and now - _cache[0] < _CACHE_TTL:
        return _cache[1]

    registry.bootstrap()
    status: dict[str, bool] = {}

    for provider in registry.market:
        status[provider.name] = await _probe(provider.get_quote("SPY"))

    for provider in registry.options:
        if provider.name == "alpaca" and not settings.alpaca_configured:
            status[provider.name] = False
        else:
            status[provider.name] = await _probe(provider.get_expirations("SPY"))

    for provider in registry.news:
        status[provider.name] = await _probe(provider.get_news(limit=1))

    for provider in registry.insiders:
        status[provider.name] = await _probe(provider.get_recent(limit=1))

    for provider in registry.macro:
        status[provider.name] = await _probe(provider.get_series("DFF", limit=1))

    _cache = (now, status)
    return status


def reset_health_cache_for_tests() -> None:
    global _cache
    _cache = None
