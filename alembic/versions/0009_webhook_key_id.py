"""webhook key lookup id (v2.5)

Adds ``users.webhook_key_id`` — the indexed, unique public half of the new
"<key_id>.<secret>" webhook API key format. Verification now does a single
indexed lookup on this column plus one SHA-256 constant-time compare against
``webhook_api_key_hash``, replacing the previous bcrypt-verify-against-every-user
scan (which both failed to scale and was a DoS amplifier).

No data migration: webhook keys are issued live and (at the time of this
revision) none exist. Any pre-existing key would simply need re-generating;
the old-format hash on its own can no longer authenticate.

Revision ID: 0009_webhook_key_id
Revises: 0008_extend_run_enums
Create Date: 2026-05-29 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0009_webhook_key_id"
down_revision: Union[str, None] = "0008_extend_run_enums"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("webhook_key_id", sa.String(length=32), nullable=True),
    )
    op.create_index(
        "ix_users_webhook_key_id", "users", ["webhook_key_id"], unique=True
    )
    # Existing old-format hashes can never match the new verify path, so clear
    # them to keep the data honest (count at this revision: zero).
    op.execute("UPDATE users SET webhook_api_key_hash = NULL")


def downgrade() -> None:
    op.drop_index("ix_users_webhook_key_id", table_name="users")
    op.drop_column("users", "webhook_key_id")
