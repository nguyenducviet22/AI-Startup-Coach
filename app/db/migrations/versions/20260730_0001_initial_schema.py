"""initial schema

Revision ID: 20260730_0001
Revises:
Create Date: 2026-07-30
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260730_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("email"),
    )

    op.create_table(
        "startups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(length=255)),
        sa.Column("current_stage", sa.String(length=50), nullable=False, server_default=sa.text("'idea'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "lean_canvas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("startup_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("startups.id"), nullable=False),
        sa.Column("problem", sa.Text()),
        sa.Column("solution", sa.Text()),
        sa.Column("unique_value_proposition", sa.Text()),
        sa.Column("unfair_advantage", sa.Text()),
        sa.Column("customer_segments", sa.Text()),
        sa.Column("key_metrics", sa.Text()),
        sa.Column("channels", sa.Text()),
        sa.Column("cost_structure", sa.Text()),
        sa.Column("revenue_streams", sa.Text()),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("is_current", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "bmc",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("startup_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("startups.id"), nullable=False),
        sa.Column("key_partners", sa.Text()),
        sa.Column("key_activities", sa.Text()),
        sa.Column("key_resources", sa.Text()),
        sa.Column("value_propositions", sa.Text()),
        sa.Column("customer_relationships", sa.Text()),
        sa.Column("channels", sa.Text()),
        sa.Column("customer_segments", sa.Text()),
        sa.Column("cost_structure", sa.Text()),
        sa.Column("revenue_streams", sa.Text()),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("is_current", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "swot",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("startup_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("startups.id"), nullable=False),
        sa.Column("strengths", postgresql.JSONB()),
        sa.Column("weaknesses", postgresql.JSONB()),
        sa.Column("opportunities", postgresql.JSONB()),
        sa.Column("threats", postgresql.JSONB()),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("is_current", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "product_plan",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("startup_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("startups.id"), nullable=False),
        sa.Column("mvp_scope", sa.Text()),
        sa.Column("features", postgresql.JSONB()),
        sa.Column("timeline", postgresql.JSONB()),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("is_current", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "marketing_strategy",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("startup_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("startups.id"), nullable=False),
        sa.Column("target_audience", sa.Text()),
        sa.Column("channels", postgresql.JSONB()),
        sa.Column("key_messages", sa.Text()),
        sa.Column("budget_estimate", sa.Text()),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("is_current", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "funding_guide",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("startup_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("startups.id"), nullable=False),
        sa.Column("pitch_outline", postgresql.JSONB()),
        sa.Column("valuation_notes", sa.Text()),
        sa.Column("funding_stage_recommendation", sa.String(length=100)),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("is_current", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "chat_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("startup_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("startups.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "chat_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("chat_sessions.id"), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tool_call_data", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("chat_messages")
    op.drop_table("chat_sessions")
    op.drop_table("funding_guide")
    op.drop_table("marketing_strategy")
    op.drop_table("product_plan")
    op.drop_table("swot")
    op.drop_table("bmc")
    op.drop_table("lean_canvas")
    op.drop_table("startups")
    op.drop_table("users")

