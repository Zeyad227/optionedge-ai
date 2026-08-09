"""Typed wrapper that forces every datum to carry its provenance."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Sourced(BaseModel, Generic[T]):
    """A value that cannot be constructed without naming its source."""

    value: T
    source: str
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    url: str | None = None
    note: str | None = None

    @classmethod
    def of(
        cls,
        value: T,
        source: str,
        *,
        url: str | None = None,
        note: str | None = None,
    ) -> Sourced[T]:
        return cls(value=value, source=source, url=url, note=note)
