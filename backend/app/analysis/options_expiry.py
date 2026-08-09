"""Helpers for choosing option expirations with minimum DTE."""

from __future__ import annotations

from datetime import date, timedelta

from app.utils.market_calendar import market_today


def pick_expiration(
    expirations: list[date],
    *,
    min_dte: int = 7,
    as_of: date | None = None,
) -> date | None:
    """Pick the nearest expiry at least ``min_dte`` days out; fall back to nearest."""
    if not expirations:
        return None
    today = as_of or market_today()
    min_date = today + timedelta(days=min_dte)
    eligible = sorted(d for d in expirations if d >= min_date)
    if eligible:
        return eligible[0]
    return min(expirations)
