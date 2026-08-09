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
