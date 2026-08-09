"""Initial schema: iv_snapshots, news_articles, insider_filings, scan_results.

Revision ID: 001
Revises:
Create Date: 2026-08-03
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "iv_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("iv", sa.Float(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("symbol", "as_of", name="uq_iv_symbol_date"),
    )
    op.create_index("ix_iv_snapshots_symbol", "iv_snapshots", ["symbol"])
    op.create_index("ix_iv_snapshots_as_of", "iv_snapshots", ["as_of"])

    op.create_table(
        "news_articles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("url_hash", sa.String(length=64), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=128), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sentiment", sa.String(length=16), nullable=True),
        sa.Column("sentiment_score", sa.Float(), nullable=True),
        sa.Column("impact", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_news_articles_url_hash", "news_articles", ["url_hash"], unique=True)

    op.create_table(
        "insider_filings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("form_url", sa.Text(), nullable=False),
        sa.Column("company", sa.String(length=256), nullable=False),
        sa.Column("symbol", sa.String(length=16), nullable=True),
        sa.Column("insider_name", sa.String(length=256), nullable=True),
        sa.Column("sentiment", sa.String(length=16), nullable=False),
        sa.Column("filed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_json", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("form_url"),
    )

    op.create_table(
        "scan_results",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("trend", sa.String(length=16), nullable=False),
        sa.Column("risk_reward", sa.Float(), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_results_symbol", "scan_results", ["symbol"])


def downgrade() -> None:
    op.drop_index("ix_scan_results_symbol", table_name="scan_results")
    op.drop_table("scan_results")
    op.drop_table("insider_filings")
    op.drop_index("ix_news_articles_url_hash", table_name="news_articles")
    op.drop_table("news_articles")
    op.drop_index("ix_iv_snapshots_as_of", table_name="iv_snapshots")
    op.drop_index("ix_iv_snapshots_symbol", table_name="iv_snapshots")
    op.drop_table("iv_snapshots")
