"""SQLAlchemy models."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class IVSnapshot(Base):
    """Daily IV snapshot per underlying for IV rank / percentile."""

    __tablename__ = "iv_snapshots"
    __table_args__ = (UniqueConstraint("symbol", "as_of", name="uq_iv_symbol_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    as_of: Mapped[date] = mapped_column(Date, index=True)
    iv: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(64))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class NewsArticleRow(Base):
    __tablename__ = "news_articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    url_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(128))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sentiment: Mapped[str | None] = mapped_column(String(16), nullable=True)
    sentiment_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    impact: Mapped[float | None] = mapped_column(Float, nullable=True)


class InsiderFilingRow(Base):
    __tablename__ = "insider_filings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    form_url: Mapped[str] = mapped_column(Text, unique=True)
    company: Mapped[str] = mapped_column(String(256))
    symbol: Mapped[str | None] = mapped_column(String(16), nullable=True)
    insider_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    sentiment: Mapped[str] = mapped_column(String(16), default="Neutral")
    filed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    raw_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class ScanResultRow(Base):
    __tablename__ = "scan_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    action: Mapped[str] = mapped_column(String(16))
    confidence: Mapped[float] = mapped_column(Float)
    trend: Mapped[str] = mapped_column(String(16))
    risk_reward: Mapped[float | None] = mapped_column(Float, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payload_json: Mapped[str] = mapped_column(Text)
