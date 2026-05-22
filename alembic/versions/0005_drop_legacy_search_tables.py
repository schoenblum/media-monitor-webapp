"""drop legacy search_terms and search_outlet_links tables

These tables were superseded by the JSONB ``searches.config`` column in
migration 0003, which data-migrated their contents. The ORM classes were
removed in v2.2; this migration drops the now-dormant tables.

Revision ID: 0005_drop_legacy_search_tables
Revises: 0004_drop_language_label
Create Date: 2026-05-22 10:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0005_drop_legacy_search_tables"
down_revision: Union[str, None] = "0004_drop_language_label"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("search_outlet_links")
    op.drop_table("search_terms")


def downgrade() -> None:
    # Re-create the legacy tables with the original v2 schema. They will be empty;
    # data migrated to searches.config in 0003 is not reversed here.
    op.create_table(
        "search_terms",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "search_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("searches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("language_code", sa.String(length=8), nullable=False),
        sa.Column("term", sa.String(length=500), nullable=False),
        sa.Column("pages", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.UniqueConstraint("search_id", "language_code", name="uq_term_search_lang"),
    )
    op.create_table(
        "search_outlet_links",
        sa.Column(
            "search_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("searches.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "outlet_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("outlets.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
