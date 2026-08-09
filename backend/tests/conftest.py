"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

from app.providers.http import close_http_client, init_http_client


@pytest.fixture(autouse=True)
async def _http_client_lifecycle():
    await init_http_client()
    yield
    await close_http_client()
