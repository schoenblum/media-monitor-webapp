"""add university_languages table

Revision ID: 0002_university_languages
Revises: 0001_initial
Create Date: 2026-05-15 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0002_university_languages"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "university_languages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("iso_code", sa.String(10), nullable=False),
        sa.Column("language_label", sa.String(100), nullable=False),
        sa.Column("university_name", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_university_languages_user_id", "university_languages", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_university_languages_user_id", table_name="university_languages")
    op.drop_table("university_languages")
