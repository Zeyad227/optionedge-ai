"""Simple in-memory rate limiting."""

from __future__ import annotations

import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import get_settings


# Buckets are keyed by client + coarse route group rather than the raw path, so a
# caller cannot grow the tracking table without bound by inventing unique URLs.
SCANNER_BUCKET = "scanner"
DEFAULT_BUCKET = "default"

# Hard ceiling on distinct tracked clients; prevents unbounded memory growth from
# spoofed/rotating source addresses. Oldest-idle entries are dropped first.
MAX_TRACKED_BUCKETS = 10_000


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app) -> None:
        super().__init__(app)
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def _evict_idle(self, now: float, window: float) -> None:
        stale = [key for key, hits in self._hits.items() if not hits or now - hits[-1] > window]
        for key in stale:
            del self._hits[key]
        if len(self._hits) > MAX_TRACKED_BUCKETS:
            overflow = len(self._hits) - MAX_TRACKED_BUCKETS
            for key in list(self._hits)[:overflow]:
                del self._hits[key]

    def _allow(self, key: str, *, limit: int, window: float = 60.0) -> bool:
        now = time.monotonic()
        bucket = self._hits[key]
        while bucket and now - bucket[0] > window:
            bucket.popleft()
        if len(bucket) >= limit:
            return False
        bucket.append(now)
        if len(self._hits) > MAX_TRACKED_BUCKETS:
            self._evict_idle(now, window)
        return True

    async def dispatch(self, request: Request, call_next) -> Response:
        settings = get_settings()
        if settings.rate_limit_per_minute <= 0:
            return await call_next(request)

        client = request.client.host if request.client else "unknown"
        limit = settings.rate_limit_per_minute
        bucket = DEFAULT_BUCKET
        if request.url.path.startswith("/api/scanner"):
            bucket = SCANNER_BUCKET
            limit = min(limit, settings.scanner_rate_limit_per_minute)

        if not self._allow(f"{client}:{bucket}", limit=limit):
            request_id = getattr(request.state, "request_id", None)
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded", "request_id": request_id},
                headers={"Retry-After": "60"},
            )
        return await call_next(request)
