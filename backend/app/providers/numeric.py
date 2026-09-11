"""Numeric coercion shared by market-data providers.

Feeds report absent values inconsistently — ``None``, empty strings, and NaN
placeholders for a bar that has not closed yet. Anything non-finite must become
``None`` here: it is indistinguishable from missing data downstream, and NaN
propagates silently through arithmetic before failing at JSON serialisation.
"""

from __future__ import annotations

import math


def finite(value: object) -> float | None:
    """Coerce to float, treating unparseable, NaN, and infinite input as missing."""
    if value is None:
        return None
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def finite_int(value: object) -> int | None:
    number = finite(value)
    return int(number) if number is not None else None
