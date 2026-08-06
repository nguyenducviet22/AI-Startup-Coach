"""add research agent tables

Revision ID: 20260806_0005
Revises: 20260801_0004
Create Date: 2026-08-06
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260806_0005"
down_revision: str | None = "20260801_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "research_calls",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("sequence", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("turn_id", postgresql.UUID(as_uuid=True)),
        sa.Column("startup_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True)),
        sa.Column("stage", sa.String(length=50), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("operation", sa.String(length=50), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("query_fingerprint", sa.String(length=128), nullable=False),
        sa.Column("provider_request_id", sa.String(length=255)),
        sa.Column("cache_hit", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("provider_call_made", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("credits_reserved", sa.Integer()),
        sa.Column("credits_charged", sa.Integer()),
        sa.Column("cost_usd", sa.Numeric(12, 6)),
        sa.Column("pricing_unknown", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("error_code", sa.String(length=100)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["turn_id"], ["agent_turns.id"], name="fk_research_calls_turn_id_agent_turns"),
        sa.ForeignKeyConstraint(["startup_id"], ["startups.id"], name="fk_research_calls_startup_id_startups"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_research_calls_user_id_users"),
        sa.ForeignKeyConstraint(["session_id"], ["chat_sessions.id"], name="fk_research_calls_session_id_chat_sessions"),
    )
    op.create_index("ix_research_calls_startup_created_at", "research_calls", ["startup_id", "created_at"])
    op.create_index("ix_research_calls_user_created_at", "research_calls", ["user_id", "created_at"])
    op.create_index("ix_research_calls_session_created_at", "research_calls", ["session_id", "created_at"])
    op.create_index(
        "ix_research_calls_stage_category_created_at",
        "research_calls",
        ["stage", "category", "created_at"],
    )
    op.create_index("ix_research_calls_turn_id", "research_calls", ["turn_id"])

    op.create_table(
        "research_cache_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("sequence", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("startup_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("research_call_id", postgresql.UUID(as_uuid=True)),
        sa.Column("cache_key", sa.String(length=128), nullable=False),
        sa.Column("operation", sa.String(length=50), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["startup_id"], ["startups.id"], name="fk_research_cache_entries_startup_id_startups"),
        sa.ForeignKeyConstraint(
            ["research_call_id"],
            ["research_calls.id"],
            name="fk_research_cache_entries_research_call_id_research_calls",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("startup_id", "cache_key", name="uq_research_cache_entries_startup_id_cache_key"),
    )
    op.create_index("ix_research_cache_entries_expires_at", "research_cache_entries", ["expires_at"])

    op.create_table(
        "research_quota_reservations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("sequence", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True)),
        sa.Column("reserved_calls", sa.Integer(), nullable=False),
        sa.Column("reserved_credits", sa.Integer(), nullable=False),
        sa.Column("charged_credits", sa.Integer()),
        sa.Column("released_credits", sa.Integer()),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("reconciled_at", sa.DateTime(timezone=True)),
        sa.Column("released_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_research_quota_reservations_user_id_users"),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["chat_sessions.id"],
            name="fk_research_quota_reservations_session_id_chat_sessions",
        ),
    )
    op.create_index(
        "ix_research_quota_reservations_user_created_at",
        "research_quota_reservations",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_research_quota_reservations_session_created_at",
        "research_quota_reservations",
        ["session_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_research_quota_reservations_session_created_at",
        table_name="research_quota_reservations",
    )
    op.drop_index(
        "ix_research_quota_reservations_user_created_at",
        table_name="research_quota_reservations",
    )
    op.drop_table("research_quota_reservations")
    op.drop_index("ix_research_cache_entries_expires_at", table_name="research_cache_entries")
    op.drop_table("research_cache_entries")
    op.drop_index("ix_research_calls_turn_id", table_name="research_calls")
    op.drop_index("ix_research_calls_stage_category_created_at", table_name="research_calls")
    op.drop_index("ix_research_calls_session_created_at", table_name="research_calls")
    op.drop_index("ix_research_calls_user_created_at", table_name="research_calls")
    op.drop_index("ix_research_calls_startup_created_at", table_name="research_calls")
    op.drop_table("research_calls")
