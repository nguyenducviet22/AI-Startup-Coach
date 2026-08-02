import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Startup(Base):
    __tablename__ = "startups"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    name: Mapped[str | None] = mapped_column(String(255))
    current_stage: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default=text("'idea'"),
    )
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        onupdate=func.now(),
    )

    user = relationship("User", back_populates="startups")
    chat_sessions = relationship("ChatSession", back_populates="startup")

