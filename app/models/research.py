import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ResearchCall(Base):
    __tablename__ = "research_calls"
    __table_args__ = (
        Index("ix_research_calls_startup_created_at", "startup_id", "created_at"),
        Index("ix_research_calls_user_created_at", "user_id", "created_at"),
        Index("ix_research_calls_session_created_at", "session_id", "created_at"),
        Index("ix_research_calls_stage_category_created_at", "stage", "category", "created_at"),
        Index("ix_research_calls_turn_id", "turn_id"),
    )

    sequence: Mapped[int] = mapped_column(BigInteger, Identity(always=False), nullable=False)
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    turn_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_turns.id", name="fk_research_calls_turn_id_agent_turns"),
    )
    startup_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("startups.id", name="fk_research_calls_startup_id_startups"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", name="fk_research_calls_user_id_users"),
        nullable=False,
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_sessions.id", name="fk_research_calls_session_id_chat_sessions"),
    )
    stage: Mapped[str] = mapped_column(String(50), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    operation: Mapped[str] = mapped_column(String(50), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    query_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_request_id: Mapped[str | None] = mapped_column(String(255))
    cache_hit: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    provider_call_made: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )
    credits_reserved: Mapped[int | None] = mapped_column(Integer)
    credits_charged: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    pricing_unknown: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
    )


class ResearchCacheEntry(Base):
    __tablename__ = "research_cache_entries"
    __table_args__ = (
        UniqueConstraint(
            "startup_id",
            "cache_key",
            name="uq_research_cache_entries_startup_id_cache_key",
        ),
        Index("ix_research_cache_entries_expires_at", "expires_at"),
    )

    sequence: Mapped[int] = mapped_column(BigInteger, Identity(always=False), nullable=False)
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    startup_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("startups.id", name="fk_research_cache_entries_startup_id_startups"),
        nullable=False,
    )
    research_call_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "research_calls.id",
            name="fk_research_cache_entries_research_call_id_research_calls",
            ondelete="SET NULL",
        ),
    )
    cache_key: Mapped[str] = mapped_column(String(128), nullable=False)
    operation: Mapped[str] = mapped_column(String(50), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
    )


class ResearchQuotaReservation(Base):
    __tablename__ = "research_quota_reservations"
    __table_args__ = (
        Index("ix_research_quota_reservations_user_created_at", "user_id", "created_at"),
        Index("ix_research_quota_reservations_session_created_at", "session_id", "created_at"),
    )

    sequence: Mapped[int] = mapped_column(BigInteger, Identity(always=False), nullable=False)
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", name="fk_research_quota_reservations_user_id_users"),
        nullable=False,
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "chat_sessions.id",
            name="fk_research_quota_reservations_session_id_chat_sessions",
        ),
    )
    reserved_calls: Mapped[int] = mapped_column(Integer, nullable=False)
    reserved_credits: Mapped[int] = mapped_column(Integer, nullable=False)
    charged_credits: Mapped[int | None] = mapped_column(Integer)
    released_credits: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
    )
    reconciled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
