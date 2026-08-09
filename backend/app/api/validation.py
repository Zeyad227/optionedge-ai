"""Request validation helpers."""

from __future__ import annotations

import re

from fastapi import HTTPException

_SYMBOL_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")


def normalize_symbol(symbol: str) -> str:
    """Validate and normalize a ticker symbol for outbound provider calls."""
    cleaned = symbol.strip().upper()
    if not cleaned or not _SYMBOL_RE.match(cleaned):
        raise HTTPException(status_code=400, detail=f"Invalid symbol: {symbol!r}")
    return cleaned
