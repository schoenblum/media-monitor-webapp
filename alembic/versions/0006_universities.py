"""university affiliation (Item 8)

Adds:
  - ``universities`` table (id, name UNIQUE, timestamps)
  - ``users.university_id`` (nullable FK; null = unaffiliated, today's behaviour)
  - ``runs.university_id`` (nullable FK; snapshot at run-creation time)
  - ``university_languages.university_id`` (nullable FK; null = user-private)
  - ``outlets.university_id`` (nullable FK; null = user-private)
  - UNIQUE (university_id, iso_code) on university_languages
  - UNIQUE (university_id, domain) on outlets

PostgreSQL UNIQUE treats NULLs as distinct, so a user can still have one
private "EN" entry while affiliated members share their own "EN" entry —
the two constraints (user_id, iso_code) and (university_id, iso_code)
co-exist cleanly.

Revision ID: 0006_universities
Revises: 0005_drop_legacy_search_tables
Create Date: 2026-05-22 02:30:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0006_universities"
down_revision: Union[str, None] = "0005_drop_legacy_search_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "universities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("name", name="uq_universities_name"),
    )

    for table in ("users", "runs", "university_languages", "outlets"):
        op.add_column(
            table,
            sa.Column(
                "university_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("universities.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )
        op.create_index(
            f"ix_{table}_university_id",
            table,
            ["university_id"],
        )

    op.create_unique_constraint(
        "uq_university_languages_uni_iso",
        "university_languages",
        ["university_id", "iso_code"],
    )
    op.create_unique_constraint(
        "uq_outlet_uni_domain",
        "outlets",
        ["university_id", "domain"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_outlet_uni_domain", "outlets", type_="unique")
    op.drop_constraint(
        "uq_university_languages_uni_iso", "university_languages", type_="unique"
    )
    for table in ("users", "runs", "university_languages", "outlets"):
        op.drop_index(f"ix_{table}_university_id", table_name=table)
        op.drop_column(table, "university_id")
    op.drop_table("universities")
