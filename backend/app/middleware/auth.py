"""Optional API key authentication."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import get_settings

_PUBLIC_PATHS = frozenset({"/", "/health", "/docs", "/openapi.json", "/redoc"})


class ApiKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        settings = get_settings()
        if not settings.api_key:
            return await call_next(request)

        path = request.url.path.rstrip("/") or "/"
        if path in _PUBLIC_PATHS:
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        bearer = auth_header.removeprefix("Bearer ").strip() if auth_header else ""
        provided = request.headers.get("X-API-Key") or bearer
        if provided != settings.api_key:
            request_id = getattr(request.state, "request_id", None)
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key", "request_id": request_id},
            )
        return await call_next(request)
