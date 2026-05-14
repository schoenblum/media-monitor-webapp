"""add config column to searches, migrate from search_terms + search_outlet_links

Revision ID: 0003_search_config
Revises: 0002_university_languages
Create Date: 2026-05-15 00:01:00.000000
"""
import json
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0003_search_config"
down_revision: Union[str, None] = "0002_university_languages"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add config column (nullable first so we can populate it).
    op.add_column(
        "searches",
        sa.Column("config", sa.JSON(), nullable=True),
    )

    connection = op.get_bind()

    # Migrate each existing search: build a config from its search_terms + outlet_links.
    searches = connection.execute(sa.text("SELECT id FROM searches")).fetchall()
    for (search_id,) in searches:
        sid_str = str(search_id)

        terms_rows = connection.execute(
            sa.text(
                "SELECT language_code, term, pages, is_enabled "
                "FROM search_terms WHERE search_id = :sid ORDER BY language_code"
            ),
            {"sid": sid_str},
        ).fetchall()

        outlet_rows = connection.execute(
            sa.text(
                "SELECT outlet_id FROM search_outlet_links WHERE search_id = :sid"
            ),
            {"sid": sid_str},
        ).fetchall()

        terms_config = []
        for i, row in enumerate(terms_rows):
            lang, term, pages, is_enabled = row
            if not (is_enabled and term and term.strip()):
                continue
            terms_config.append(
                {
                    "id": str(uuid.uuid4()),
                    "text": term.strip(),
                    "operator": "OR" if i > 0 else None,
                    "pages": int(pages),
                }
            )

        outlet_ids = [str(r[0]) for r in outlet_rows]

        config = {
            "search_window": "last",
            "fallback_hours": 72,
            "terms": terms_config,
            "doi": {"text": "", "pages": 1},
            "university_name": {"enabled": False, "language_ids": []},
            "outlets": {
                "enabled": len(outlet_ids) > 0,
                "outlet_ids": outlet_ids,
            },
        }

        connection.execute(
            sa.text("UPDATE searches SET config = :cfg WHERE id = :sid"),
            {"cfg": json.dumps(config), "sid": sid_str},
        )

    # Set non-nullable with server default.
    op.alter_column("searches", "config", nullable=False)
    op.execute("ALTER TABLE searches ALTER COLUMN config SET DEFAULT '{}'::json")


def downgrade() -> None:
    op.drop_column("searches", "config")
