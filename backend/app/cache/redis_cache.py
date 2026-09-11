"""Cache abstraction — in-memory by default, Redis when configured.

Per-domain TTLs and single-flight locking: concurrent cache misses for the
same key share one producer. With Redis, the lock is SET NX so multiple
API workers do not stampede a provider.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)


class CacheBackend:
    async def get(self, key: str) -> Any | None: ...
    async def set(self, key: str, value: Any, ttl: int) -> None: ...
    async def delete(self, key: str) -> None: ...

    async def acquire_lock(self, key: str, *, ttl: int = 30) -> bool:
        return True

    async def release_lock(self, key: str) -> None:
        return None


# Redis expires keys on its own; the in-process fallback must do it explicitly or a
# caller can grow the dict without bound by requesting many distinct symbols.
MEMORY_CACHE_MAX_ENTRIES = 5_000


class MemoryCache(CacheBackend):
    def __init__(self) -> None:
        self._store: dict[str, tuple[float, Any]] = {}

    async def get(self, key: str) -> Any | None:
        item = self._store.get(key)
        if not item:
            return None
        expires, value = item
        if expires < time.time():
            self._store.pop(key, None)
            return None
        return value

    def _evict(self) -> None:
        now = time.time()
        for key in [k for k, (expires, _) in self._store.items() if expires < now]:
            del self._store[key]
        # Still oversized after dropping expired keys: shed the soonest to expire.
        overflow = len(self._store) - MEMORY_CACHE_MAX_ENTRIES
        if overflow > 0:
            by_expiry = sorted(self._store, key=lambda k: self._store[k][0])
            for key in by_expiry[:overflow]:
                del self._store[key]

    async def set(self, key: str, value: Any, ttl: int) -> None:
        self._store[key] = (time.time() + ttl, value)
        if len(self._store) > MEMORY_CACHE_MAX_ENTRIES:
            self._evict()

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    async def acquire_lock(self, key: str, *, ttl: int = 30) -> bool:
        # In-process single-flight is handled by `_singleflight` in `cached()`.
        return True


class RedisCache(CacheBackend):
    def __init__(self, url: str) -> None:
        import redis.asyncio as redis

        self._client = redis.from_url(url, decode_responses=True)

    async def get(self, key: str) -> Any | None:
        raw = await self._client.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    async def set(self, key: str, value: Any, ttl: int) -> None:
        await self._client.set(key, json.dumps(value, default=str), ex=ttl)

    async def delete(self, key: str) -> None:
        await self._client.delete(key)

    async def acquire_lock(self, key: str, *, ttl: int = 30) -> bool:
        # SET NX EX — true when this worker owns the miss
        return bool(await self._client.set(f"lock:{key}", "1", nx=True, ex=ttl))

    async def release_lock(self, key: str) -> None:
        await self._client.delete(f"lock:{key}")


# Domain TTLs (seconds)
TTL_QUOTE = 60
TTL_OHLCV = 300
TTL_CHAIN = 300
TTL_NEWS = 900
TTL_INSIDER = 3600
TTL_SIGNAL = 60
TTL_MACRO = 3600
TTL_NEGATIVE = 30

_NONE_SENTINEL = {"__cached_none__": True}

_cache: CacheBackend | None = None
_singleflight: dict[str, asyncio.Future] = {}


def get_cache() -> CacheBackend:
    global _cache
    if _cache is None:
        settings = get_settings()
        if settings.cache_backend == "redis" and settings.redis_url:
            _cache = RedisCache(settings.redis_url)
        else:
            _cache = MemoryCache()
    return _cache


def reset_cache_for_tests() -> None:
    """Drop cached singleton — tests only."""
    global _cache, _singleflight
    _cache = None
    _singleflight = {}


def _serialize(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, list) and value and hasattr(value[0], "model_dump"):
        return [v.model_dump(mode="json") for v in value]
    return value


async def cached(key: str, ttl: int, factory):
    """Single-flight cache: concurrent misses share one producer."""
    cache = get_cache()
    hit = await cache.get(key)
    if hit is not None:
        if hit == _NONE_SENTINEL:
            return None
        return hit

    if key in _singleflight:
        return await _singleflight[key]

    loop = asyncio.get_running_loop()
    fut: asyncio.Future = loop.create_future()
    _singleflight[key] = fut

    owned_lock = await cache.acquire_lock(key, ttl=min(ttl, 30) or 30)
    try:
        if not owned_lock:
            # Another worker is producing — brief poll for the value
            for _ in range(20):
                await asyncio.sleep(0.05)
                hit = await cache.get(key)
                if hit is not None:
                    result = None if hit == _NONE_SENTINEL else hit
                    fut.set_result(result)
                    return result
            # Fall through and produce locally as a safety net

        # Double-check after acquiring lock
        hit = await cache.get(key)
        if hit is not None:
            result = None if hit == _NONE_SENTINEL else hit
            fut.set_result(result)
            return result

        value = await factory()
        if value is not None:
            await cache.set(key, _serialize(value), ttl)
        else:
            await cache.set(key, _NONE_SENTINEL, TTL_NEGATIVE)
        fut.set_result(value)
        return value
    except Exception as exc:
        if not fut.done():
            fut.set_exception(exc)
        raise
    finally:
        if owned_lock:
            try:
                await cache.release_lock(key)
            except Exception:  # noqa: BLE001
                logger.debug("Failed to release cache lock for %s", key, exc_info=True)
        _singleflight.pop(key, None)
