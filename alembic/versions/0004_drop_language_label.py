"""drop language_label column, add unique (user_id, iso_code) constraint

Revision ID: 0004_drop_language_label
Revises: 0003_search_config
Create Date: 2026-05-15 12:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0004_drop_language_label"
down_revision: Union[str, None] = "0003_search_config"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Deduplicate any (user_id, iso_code) pairs that may exist before adding the uniqueness constraint.
    op.execute(
        """
        DELETE FROM university_languages
        WHERE id IN (
            SELECT id FROM (
                SELECT id, ROW_NUMBER() OVER (
                    PARTITION BY user_id, iso_code ORDER BY created_at ASC
                ) AS rn
                FROM university_languages
            ) t WHERE t.rn > 1
        )
        """
    )
    op.create_unique_constraint(
        "uq_university_languages_user_iso",
        "university_languages",
        ["user_id", "iso_code"],
    )
    op.drop_column("university_languages", "language_label")


def downgrade() -> None:
    op.add_column(
        "university_languages",
        sa.Column("language_label", sa.String(length=100), nullable=False, server_default=""),
    )
    op.drop_constraint(
        "uq_university_languages_user_iso", "university_languages", type_="unique"
    )
