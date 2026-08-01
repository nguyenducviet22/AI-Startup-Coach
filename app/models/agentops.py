import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Identity, Index, Integer, Numeric, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AgentTurn(Base):
    __tablename__ = "agent_turns"

    sequence: Mapped[int] = mapped_column(BigInteger, Identity(always=False), nullable=False)
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    startup_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("startups.id", name="fk_agent_turns_startup_id_startups"),
        nullable=False,
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_sessions.id", name="fk_agent_turns_session_id_chat_sessions"),
    )
    stage: Mapped[str] = mapped_column(String(50), nullable=False)
    tool_call_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
    )


class LlmCall(Base):
    __tablename__ = "llm_calls"
    __table_args__ = (
        Index("ix_llm_calls_created_at", "created_at"),
        Index("ix_llm_calls_stage_created_at", "stage", "created_at"),
    )

    sequence: Mapped[int] = mapped_column(BigInteger, Identity(always=False), nullable=False)
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    turn_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_turns.id", name="fk_llm_calls_turn_id_agent_turns"),
        nullable=False,
    )
    startup_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("startups.id", name="fk_llm_calls_startup_id_startups"),
        nullable=False,
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_sessions.id", name="fk_llm_calls_session_id_chat_sessions"),
    )
    stage: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    total_tokens: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    pricing_unknown: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
    )


class ToolCallLog(Base):
    __tablename__ = "tool_calls_log"
    __table_args__ = (
        Index("ix_tool_calls_log_created_at", "created_at"),
        Index("ix_tool_calls_log_stage_created_at", "stage", "created_at"),
    )

    sequence: Mapped[int] = mapped_column(BigInteger, Identity(always=False), nullable=False)
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    turn_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_turns.id", name="fk_tool_calls_log_turn_id_agent_turns"),
        nullable=False,
    )
    startup_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("startups.id", name="fk_tool_calls_log_startup_id_startups"),
        nullable=False,
    )
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    stage: Mapped[str] = mapped_column(String(50), nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error_type: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
    )


class AlertEvent(Base):
    __tablename__ = "alert_events"

    sequence: Mapped[int] = mapped_column(BigInteger, Identity(always=False), nullable=False)
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    scope: Mapped[str | None] = mapped_column(String(100))
    threshold: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    observed_value: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    window_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    triggered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
