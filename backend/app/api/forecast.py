"""Consistent forecast metadata on API payloads."""

from __future__ import annotations

from typing import Any

from app.config import get_settings
from app.constants import FORECAST_TYPE, SIGNAL_DISCLAIMER


def forecast_meta(*, include_disclaimer: bool = True) -> dict[str, Any]:
    settings = get_settings()
    meta: dict[str, Any] = {"forecast_type": FORECAST_TYPE}
    if include_disclaimer and settings.disclaimer_enabled:
        meta["disclaimer"] = SIGNAL_DISCLAIMER
    return meta


def with_forecast(payload: dict[str, Any], *, include_disclaimer: bool = True) -> dict[str, Any]:
    return {**payload, **forecast_meta(include_disclaimer=include_disclaimer)}
