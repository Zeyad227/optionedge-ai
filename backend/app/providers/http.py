"""Shared HTTP client helpers with 429 / 5xx retry."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
DEFAULT_MAX_ATTEMPTS = 4
DEFAULT_TIMEOUT = 30.0

# SEC EDGAR asks for ≤10 req/sec with a descriptive User-Agent.
_edgar_lock = asyncio.Lock()
_edgar_last_request = 0.0
EDGAR_MIN_INTERVAL = 0.11

_client: httpx.AsyncClient | None = None


async def init_http_client() -> httpx.AsyncClient:
    """Create the shared async client (called from app lifespan)."""
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            timeout=DEFAULT_TIMEOUT,
            follow_redirects=False,
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
        )
    return _client


async def close_http_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


def _get_client() -> httpx.AsyncClient:
    if _client is None:
        raise RuntimeError("HTTP client not initialized — call init_http_client() first")
    return _client


class RetryableHTTPError(Exception):
    """Raised when a response status should be retried."""

    def __init__(self, status_code: int, message: str, *, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retry_after = retry_after


def _parse_retry_after(resp: httpx.Response) -> float | None:
    raw = resp.headers.get("Retry-After")
    if not raw:
        return None
    try:
        return max(0.0, float(raw))
    except ValueError:
        return None


def _backoff_seconds(attempt: int, retry_after: float | None) -> float:
    if retry_after is not None:
        return retry_after
    # 0.5, 1, 2, 4 … capped
    return min(0.5 * (2 ** (attempt - 1)), 8.0)


async def throttle_edgar() -> None:
    """Serialize EDGAR calls and honor ~10 req/sec."""
    global _edgar_last_request
    async with _edgar_lock:
        now = time.monotonic()
        wait = EDGAR_MIN_INTERVAL - (now - _edgar_last_request)
        if wait > 0:
            await asyncio.sleep(wait)
        _edgar_last_request = time.monotonic()


async def http_get(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    follow_redirects: bool = False,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    edgar_throttle: bool = False,
) -> httpx.Response:
    """GET with retries on 429/5xx and transient transport errors."""
    client = _get_client()
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        if edgar_throttle:
            await throttle_edgar()
        try:
            resp = await client.get(
                url,
                headers=headers,
                params=params,
                timeout=timeout,
                follow_redirects=follow_redirects,
            )
        except httpx.TransportError as exc:
            last_error = exc
            if attempt >= max_attempts:
                raise
            delay = _backoff_seconds(attempt, None)
            logger.warning(
                "HTTP transport error on %s (attempt %s): %s; retry in %.1fs",
                url,
                attempt,
                exc,
                delay,
            )
            await asyncio.sleep(delay)
            continue

        if resp.status_code in RETRYABLE_STATUS:
            retry_after = _parse_retry_after(resp)
            if attempt >= max_attempts:
                resp.raise_for_status()
            delay = _backoff_seconds(attempt, retry_after)
            logger.warning(
                "HTTP %s from %s (attempt %s); retry in %.1fs",
                resp.status_code,
                url,
                attempt,
                delay,
            )
            await asyncio.sleep(delay)
            continue

        return resp

    assert last_error is not None
    raise last_error
