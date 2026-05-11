"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-11 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    user_role = postgresql.ENUM("admin", "user", name="user_role", create_type=False)
    run_status = postgresql.ENUM("pending", "running", "complete", "failed", name="run_status", create_type=False)
    run_trigger = postgresql.ENUM("manual", "webhook", name="run_trigger", create_type=False)
    user_role.create(op.get_bind(), checkfirst=True)
    run_status.create(op.get_bind(), checkfirst=True)
    run_trigger.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("backup_email", sa.String(255), nullable=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.Enum("admin", "user", name="user_role", create_type=False), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("google_api_key_encrypted", sa.LargeBinary(), nullable=True),
        sa.Column("search_engine_id_encrypted", sa.LargeBinary(), nullable=True),
        sa.Column("webhook_api_key_hash", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.Column("force_password_change", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "password_reset_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_password_reset_tokens_token_hash", "password_reset_tokens", ["token_hash"])

    op.create_table(
        "searches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_searches_user_id", "searches", ["user_id"])

    op.create_table(
        "search_terms",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("search_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("searches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("language_code", sa.String(8), nullable=False),
        sa.Column("term", sa.String(500), nullable=False),
        sa.Column("pages", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("search_id", "language_code", name="uq_term_search_lang"),
    )

    op.create_table(
        "outlets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("domain", sa.String(500), nullable=False),
        sa.Column("category", sa.String(255), nullable=True),
        sa.Column("keyword_langs", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "domain", name="uq_outlet_user_domain"),
    )
    op.create_index("ix_outlets_user_id", "outlets", ["user_id"])

    op.create_table(
        "search_outlet_links",
        sa.Column("search_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("searches.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("outlet_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("outlets.id", ondelete="CASCADE"), primary_key=True),
    )

    op.create_table(
        "runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("search_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("searches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("triggered_by", sa.Enum("manual", "webhook", name="run_trigger", create_type=False), nullable=False, server_default="manual"),
        sa.Column("status", sa.Enum("pending", "running", "complete", "failed", name="run_status", create_type=False), nullable=False, server_default="pending"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("api_calls_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.String(2000), nullable=True),
    )
    op.create_index("ix_runs_user_id", "runs", ["user_id"])
    op.create_index("ix_runs_search_id", "runs", ["search_id"])

    op.create_table(
        "results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("outlet_name", sa.String(255), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("display_source", sa.String(255), nullable=False, server_default=""),
        sa.Column("snippet", sa.Text(), nullable=False, server_default=""),
        sa.Column("date_extracted", sa.String(20), nullable=False, server_default=""),
        sa.Column("keyword_used", sa.String(255), nullable=False, server_default=""),
        sa.Column("search_lang", sa.String(8), nullable=False, server_default=""),
        sa.Column("detected_lang", sa.String(16), nullable=False, server_default=""),
        sa.Column("detected_lang_name", sa.String(64), nullable=False, server_default=""),
        sa.Column("is_selected", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_results_run_id", "results", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_results_run_id", table_name="results")
    op.drop_table("results")
    op.drop_index("ix_runs_search_id", table_name="runs")
    op.drop_index("ix_runs_user_id", table_name="runs")
    op.drop_table("runs")
    op.drop_table("search_outlet_links")
    op.drop_index("ix_outlets_user_id", table_name="outlets")
    op.drop_table("outlets")
    op.drop_table("search_terms")
    op.drop_index("ix_searches_user_id", table_name="searches")
    op.drop_table("searches")
    op.drop_index("ix_password_reset_tokens_token_hash", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS run_trigger")
    op.execute("DROP TYPE IF EXISTS run_status")
    op.execute("DROP TYPE IF EXISTS user_role")
