"""normalise legacy "Web" outlet_name to "" on results

Pre-v2.2, results from a search without any site restriction were stored with
``outlet_name = "Web"``. v2.2 changed that sentinel to the empty string and
moved the Results UI to derive a real source host from the result URL via
``utils/source.ts:sourceHostFor``. The Dashboard "Top sources" widget was
migrated to the same derivation in v2.4 item 1, but the historical rows still
need to be unified so reads of the raw column are consistent across all
history.

This is a pure data migration — no schema change. The dashboard and result
views already render the same thing for both values, but normalising removes
the last source of "Web vs '' " ambiguity.

Revision ID: 0007_normalise_web_outlet_name
Revises: 0006_universities
Create Date: 2026-05-26 09:00:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0007_normalise_web_outlet_name"
down_revision: Union[str, None] = "0006_universities"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE results SET outlet_name = '' WHERE outlet_name = 'Web'")


def downgrade() -> None:
    # Intentionally a no-op. The pre-v2.2 'Web' sentinel cannot be reconstructed
    # from the empty string: post-v2.2 runs also write '', so reversing the
    # update would incorrectly relabel new rows. Roll the migration forward
    # instead of trying to undo it.
    pass
