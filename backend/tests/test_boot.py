"""Smoke checks for app boot / health surface."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import create_app


def test_app_boots_and_health():
    app = create_app()
    with TestClient(app) as client, patch(
        "app.api.routes.health.check_provider_health",
        new=AsyncMock(return_value={"yfinance": True}),
    ):
        root = client.get("/")
        assert root.status_code == 200
        body = root.json()
        assert body["name"] == "OptionEdge AI"
        assert body["forecast_type"] == "probabilistic"

        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"
