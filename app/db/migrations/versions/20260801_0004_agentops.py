"""add agentops tables

Revision ID: 20260801_0004
Revises: 20260731_0003
Create Date: 2026-08-01
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260801_0004"
down_revision: str | None = "20260731_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_turns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("sequence", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("startup_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True)),
        sa.Column("stage", sa.String(length=50), nullable=False),
        sa.Column("tool_call_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["startup_id"], ["startups.id"], name="fk_agent_turns_startup_id_startups"),
        sa.ForeignKeyConstraint(["session_id"], ["chat_sessions.id"], name="fk_agent_turns_session_id_chat_sessions"),
    )

    op.create_table(
        "llm_calls",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("sequence", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("turn_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("startup_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True)),
        sa.Column("stage", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=False),
        sa.Column("prompt_tokens", sa.Integer()),
        sa.Column("completion_tokens", sa.Integer()),
        sa.Column("total_tokens", sa.Integer()),
        sa.Column("cost_usd", sa.Numeric(12, 6)),
        sa.Column("pricing_unknown", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error_code", sa.String(length=100)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["turn_id"], ["agent_turns.id"], name="fk_llm_calls_turn_id_agent_turns"),
        sa.ForeignKeyConstraint(["startup_id"], ["startups.id"], name="fk_llm_calls_startup_id_startups"),
        sa.ForeignKeyConstraint(["session_id"], ["chat_sessions.id"], name="fk_llm_calls_session_id_chat_sessions"),
    )
    op.create_index("ix_llm_calls_created_at", "llm_calls", ["created_at"])
    op.create_index("ix_llm_calls_stage_created_at", "llm_calls", ["stage", "created_at"])

    op.create_table(
        "tool_calls_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("sequence", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("turn_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("startup_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tool_name", sa.String(length=100), nullable=False),
        sa.Column("stage", sa.String(length=50), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error_type", sa.String(length=100)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["turn_id"], ["agent_turns.id"], name="fk_tool_calls_log_turn_id_agent_turns"),
        sa.ForeignKeyConstraint(["startup_id"], ["startups.id"], name="fk_tool_calls_log_startup_id_startups"),
    )
    op.create_index("ix_tool_calls_log_created_at", "tool_calls_log", ["created_at"])
    op.create_index("ix_tool_calls_log_stage_created_at", "tool_calls_log", ["stage", "created_at"])

    op.create_table(
        "alert_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("sequence", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("metric_name", sa.String(length=100), nullable=False),
        sa.Column("scope", sa.String(length=100)),
        sa.Column("threshold", sa.Numeric(), nullable=False),
        sa.Column("observed_value", sa.Numeric(), nullable=False),
        sa.Column("window_seconds", sa.Integer(), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("triggered_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_table("alert_events")
    op.drop_index("ix_tool_calls_log_stage_created_at", table_name="tool_calls_log")
    op.drop_index("ix_tool_calls_log_created_at", table_name="tool_calls_log")
    op.drop_table("tool_calls_log")
    op.drop_index("ix_llm_calls_stage_created_at", table_name="llm_calls")
    op.drop_index("ix_llm_calls_created_at", table_name="llm_calls")
    op.drop_table("llm_calls")
    op.drop_table("agent_turns")
