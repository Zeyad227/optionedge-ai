"""API forecast metadata and worker health surface."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.constants import FORECAST_TYPE, SIGNAL_DISCLAIMER
from app.main import create_app
from app.schemas.models import Quote
from app.schemas.sourced import Sourced


def test_health_reports_worker_jobs():
    app = create_app()
    with TestClient(app) as client, patch(
        "app.api.routes.health.check_provider_health",
        new=AsyncMock(return_value={"yfinance": True, "stooq": True}),
    ):
        body = client.get("/health").json()
        assert body["status"] == "ok"
        assert body["forecast_type"] == FORECAST_TYPE
        assert "worker_jobs" in body
        if body["workers_enabled"]:
            assert isinstance(body["worker_jobs"], list)
            assert {job["id"] for job in body["worker_jobs"]} >= {
                "refresh_scanner",
                "refresh_news",
            }


def test_market_routes_include_forecast_metadata():
    app = create_app()
    sourced = Sourced.of(Quote(symbol="SPY", price=500.0), "fixture")
    with TestClient(app) as client, patch(
        "app.services.market.fetch_quote",
        new=AsyncMock(return_value=sourced),
    ):
        body = client.get("/api/market/quote/SPY").json()
        assert body["forecast_type"] == FORECAST_TYPE
        assert body["disclaimer"] == SIGNAL_DISCLAIMER


def test_scanner_route_includes_forecast_metadata():
    app = create_app()
    with TestClient(app) as client, patch(
        "app.services.market.get_scanner_results",
        new=AsyncMock(return_value=[]),
    ):
        body = client.get("/api/scanner").json()
        assert body["forecast_type"] == FORECAST_TYPE
        assert body["disclaimer"] == SIGNAL_DISCLAIMER
        assert "universe" in body
