"""Request validation helpers."""

from __future__ import annotations

import re
from datetime import date

from fastapi import HTTPException

_SYMBOL_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")

# yfinance/Stooq period vocabulary. Restricting to an allow-list keeps arbitrary
# caller strings out of both provider URLs and cache keys.
ALLOWED_PERIODS = frozenset({"1mo", "3mo", "6mo", "1y", "2y", "5y", "max"})

MAX_BACKTEST_SPAN_DAYS = 1825


def normalize_symbol(symbol: str) -> str:
    """Validate and normalize a ticker symbol for outbound provider calls."""
    cleaned = symbol.strip().upper()
    if not cleaned or not _SYMBOL_RE.match(cleaned):
        raise HTTPException(status_code=400, detail=f"Invalid symbol: {symbol!r}")
    return cleaned


def normalize_period(period: str) -> str:
    """Validate an OHLCV lookback window against the supported provider vocabulary."""
    cleaned = period.strip().lower()
    if cleaned not in ALLOWED_PERIODS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid period: {period!r}. Allowed: {sorted(ALLOWED_PERIODS)}",
        )
    return cleaned


def parse_date_range(start: str, end: str) -> tuple[date, date]:
    """Parse an ISO date range and bound its span so a request cannot pin the worker."""
    try:
        start_date = date.fromisoformat(start.strip())
        end_date = date.fromisoformat(end.strip())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Dates must be ISO YYYY-MM-DD: {exc}") from exc

    if end_date < start_date:
        raise HTTPException(status_code=400, detail="`end` must not precede `start`")
    if (end_date - start_date).days > MAX_BACKTEST_SPAN_DAYS:
        raise HTTPException(
            status_code=400,
            detail=f"Date range exceeds the {MAX_BACKTEST_SPAN_DAYS}-day maximum",
        )
    return start_date, end_date
