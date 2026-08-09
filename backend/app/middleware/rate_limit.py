"""Simple in-memory rate limiting."""

from __future__ import annotations

import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import get_settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app) -> None:
        super().__init__(app)
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def _allow(self, key: str, *, limit: int, window: float = 60.0) -> bool:
        now = time.monotonic()
        bucket = self._hits[key]
        while bucket and now - bucket[0] > window:
            bucket.popleft()
        if len(bucket) >= limit:
            return False
        bucket.append(now)
        return True

    async def dispatch(self, request: Request, call_next) -> Response:
        settings = get_settings()
        if settings.rate_limit_per_minute <= 0:
            return await call_next(request)

        client = request.client.host if request.client else "unknown"
        path = request.url.path
        limit = settings.rate_limit_per_minute
        if path.startswith("/api/scanner"):
            limit = min(limit, settings.scanner_rate_limit_per_minute)

        if not self._allow(f"{client}:{path}", limit=limit):
            request_id = getattr(request.state, "request_id", None)
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded", "request_id": request_id},
                headers={"Retry-After": "60"},
            )
        return await call_next(request)
