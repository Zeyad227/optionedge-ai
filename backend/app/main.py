"""OptionEdge AI FastAPI application entrypoint."""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import backtest, health, insiders, market, news, options, scanner, signals
from app.config import get_settings
from app.constants import API_DISCLAIMER, FORECAST_TYPE
from app.db.session import init_db
from app.middleware.auth import ApiKeyMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.request_context import RequestContextMiddleware
from app.providers.http import close_http_client, init_http_client
from app.workers.jobs import shutdown_workers, start_workers, warm_cache

logger = logging.getLogger(__name__)

_background_tasks: set[asyncio.Task] = set()


def _track_task(coro) -> asyncio.Task:
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    if settings.database_url.startswith("sqlite"):
        Path("data").mkdir(parents=True, exist_ok=True)
    await init_db()
    await init_http_client()
    try:
        start_workers()
        if settings.warm_cache_on_startup:
            _track_task(warm_cache())
    except Exception:
        logger.exception("Background workers failed to start")
    yield
    shutdown_workers()
    await close_http_client()
    for task in list(_background_tasks):
        task.cancel()
    if _background_tasks:
        await asyncio.gather(*_background_tasks, return_exceptions=True)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="OptionEdge AI",
        version="0.1.0",
        description=API_DISCLAIMER,
        lifespan=lifespan,
    )
    app.add_middleware(ApiKeyMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", None)
        logger.exception("Unhandled error", extra={"request_id": request_id})
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "request_id": request_id},
        )

    app.include_router(health.router, tags=["health"])
    app.include_router(market.router, prefix="/api/market", tags=["market"])
    app.include_router(options.router, prefix="/api/options", tags=["options"])
    app.include_router(signals.router, prefix="/api/signals", tags=["signals"])
    app.include_router(news.router, prefix="/api/news", tags=["news"])
    app.include_router(insiders.router, prefix="/api/insiders", tags=["insiders"])
    app.include_router(scanner.router, prefix="/api/scanner", tags=["scanner"])
    app.include_router(backtest.router, prefix="/api/backtest", tags=["backtest"])

    @app.get("/")
    async def root():
        return {
            "name": "OptionEdge AI",
            "version": "0.1.0",
            "forecast_type": FORECAST_TYPE,
            "disclaimer": API_DISCLAIMER if settings.disclaimer_enabled else None,
        }

    return app


app = create_app()
