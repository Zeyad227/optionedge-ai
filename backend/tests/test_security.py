"""Security and validation tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import create_app


def test_invalid_symbol_rejected():
    app = create_app()
    with TestClient(app) as client, patch(
        "app.api.routes.health.check_provider_health",
        new=AsyncMock(return_value={}),
    ):
        resp = client.get("/api/market/quote/not valid!!")
        assert resp.status_code == 400
        assert "Invalid symbol" in resp.json()["detail"]


def test_invalid_ohlcv_period_rejected():
    app = create_app()
    with TestClient(app) as client, patch(
        "app.api.routes.health.check_provider_health",
        new=AsyncMock(return_value={}),
    ):
        resp = client.get("/api/market/ohlcv/AAPL", params={"period": "../../etc/passwd"})
        assert resp.status_code == 400
        assert "Invalid period" in resp.json()["detail"]


def test_invalid_news_symbol_rejected():
    app = create_app()
    with TestClient(app) as client, patch(
        "app.api.routes.health.check_provider_health",
        new=AsyncMock(return_value={}),
    ):
        resp = client.get("/api/news", params={"symbol": "A" * 64})
        assert resp.status_code == 400
        assert "Invalid symbol" in resp.json()["detail"]


def test_backtest_rejects_malformed_and_oversized_date_range():
    app = create_app()
    with TestClient(app) as client, patch(
        "app.api.routes.health.check_provider_health",
        new=AsyncMock(return_value={}),
    ):
        malformed = client.post(
            "/api/backtest/run",
            json={"start": "not-a-date", "end": "2026-01-01", "symbols": ["AAPL"]},
        )
        assert malformed.status_code == 400

        oversized = client.post(
            "/api/backtest/run",
            json={"start": "1990-01-01", "end": "2026-01-01", "symbols": ["AAPL"]},
        )
        assert oversized.status_code == 400
        assert "maximum" in oversized.json()["detail"]

        inverted = client.post(
            "/api/backtest/run",
            json={"start": "2026-01-01", "end": "2025-01-01", "symbols": ["AAPL"]},
        )
        assert inverted.status_code == 400


def test_api_key_required_when_configured(monkeypatch):
    monkeypatch.setenv("API_KEY", "secret-test-key")
    from app.config import get_settings

    get_settings.cache_clear()

    app = create_app()
    with TestClient(app) as client, patch(
        "app.api.routes.health.check_provider_health",
        new=AsyncMock(return_value={}),
    ), patch(
        "app.api.routes.scanner.market_service.get_scanner_results",
        new=AsyncMock(return_value=[]),
    ):
        assert client.get("/health").status_code == 200
        denied = client.get("/api/scanner")
        assert denied.status_code == 401
        ok = client.get("/api/scanner", headers={"X-API-Key": "secret-test-key"})
        assert ok.status_code == 200

    get_settings.cache_clear()
    monkeypatch.delenv("API_KEY", raising=False)
