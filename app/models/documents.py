import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class LeanCanvas(Base):
    __tablename__ = "lean_canvas"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    startup_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("startups.id"),
        nullable=False,
    )
    problem: Mapped[str | None] = mapped_column(Text)
    solution: Mapped[str | None] = mapped_column(Text)
    unique_value_proposition: Mapped[str | None] = mapped_column(Text)
    unfair_advantage: Mapped[str | None] = mapped_column(Text)
    customer_segments: Mapped[str | None] = mapped_column(Text)
    key_metrics: Mapped[str | None] = mapped_column(Text)
    channels: Mapped[str | None] = mapped_column(Text)
    cost_structure: Mapped[str | None] = mapped_column(Text)
    revenue_streams: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    is_current: Mapped[bool | None] = mapped_column(Boolean, server_default=text("true"))
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class Bmc(Base):
    __tablename__ = "bmc"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    startup_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("startups.id"),
        nullable=False,
    )
    key_partners: Mapped[str | None] = mapped_column(Text)
    key_activities: Mapped[str | None] = mapped_column(Text)
    key_resources: Mapped[str | None] = mapped_column(Text)
    value_propositions: Mapped[str | None] = mapped_column(Text)
    customer_relationships: Mapped[str | None] = mapped_column(Text)
    channels: Mapped[str | None] = mapped_column(Text)
    customer_segments: Mapped[str | None] = mapped_column(Text)
    cost_structure: Mapped[str | None] = mapped_column(Text)
    revenue_streams: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    is_current: Mapped[bool | None] = mapped_column(Boolean, server_default=text("true"))
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class Swot(Base):
    __tablename__ = "swot"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    startup_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("startups.id"),
        nullable=False,
    )
    strengths: Mapped[list[str] | None] = mapped_column(JSONB)
    weaknesses: Mapped[list[str] | None] = mapped_column(JSONB)
    opportunities: Mapped[list[str] | None] = mapped_column(JSONB)
    threats: Mapped[list[str] | None] = mapped_column(JSONB)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    is_current: Mapped[bool | None] = mapped_column(Boolean, server_default=text("true"))
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class ProductPlan(Base):
    __tablename__ = "product_plan"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    startup_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("startups.id"),
        nullable=False,
    )
    mvp_scope: Mapped[str | None] = mapped_column(Text)
    features: Mapped[list[dict[str, str]] | None] = mapped_column(JSONB)
    timeline: Mapped[list[dict[str, str]] | None] = mapped_column(JSONB)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    is_current: Mapped[bool | None] = mapped_column(Boolean, server_default=text("true"))
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class MarketingStrategy(Base):
    __tablename__ = "marketing_strategy"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    startup_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("startups.id"),
        nullable=False,
    )
    target_audience: Mapped[str | None] = mapped_column(Text)
    channels: Mapped[list[str] | None] = mapped_column(JSONB)
    key_messages: Mapped[str | None] = mapped_column(Text)
    budget_estimate: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    is_current: Mapped[bool | None] = mapped_column(Boolean, server_default=text("true"))
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class FundingGuide(Base):
    __tablename__ = "funding_guide"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    startup_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("startups.id"),
        nullable=False,
    )
    pitch_outline: Mapped[list[dict[str, str]] | None] = mapped_column(JSONB)
    valuation_notes: Mapped[str | None] = mapped_column(Text)
    funding_stage_recommendation: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    is_current: Mapped[bool | None] = mapped_column(Boolean, server_default=text("true"))
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
