"""extend run_trigger + run_status enums (item 7)

Adds ``scheduled`` to ``run_trigger`` and ``skipped`` to ``run_status``.

PostgreSQL enums are extended with ``ALTER TYPE … ADD VALUE …``. That
statement cannot run inside a transaction block in older PG versions, so we
wrap each ADD VALUE in an autocommit block (the same shape the commit
``d5309a3 "Fix Postgres enum migration"`` settled on). ``IF NOT EXISTS`` makes
the migration idempotent in case of a partial re-run — important here because
the v2.4 first deploy attempt successfully added both enum values before
failing on the final ``alembic_version`` bookkeeping update (the original
revision ID was 47 chars and the default ``alembic_version.version_num``
column is ``VARCHAR(32)``). Re-running this with the shorter ID below
applies cleanly because the ADD VALUEs no-op on the second pass.

Revision ID: 0008_extend_run_enums
Revises: 0007_normalise_web_outlet_name
Create Date: 2026-05-26 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0008_extend_run_enums"
down_revision: Union[str, None] = "0007_normalise_web_outlet_name"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ALTER TYPE … ADD VALUE cannot run inside a transaction on older PG, so
    # commit each enum addition on its own. autocommit_block() handles that.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE run_trigger ADD VALUE IF NOT EXISTS 'scheduled'")
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE run_status ADD VALUE IF NOT EXISTS 'skipped'")


def downgrade() -> None:
    # PostgreSQL does not support dropping an enum value cleanly (it would
    # require recreating the type and rewriting every dependent column). Roll
    # forward instead of trying to undo. New rows that used the added values
    # would also block any naive downgrade.
    pass
