import uuid
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatMessage, ChatSession
from app.models.startup import Startup


class ChatServiceError(Exception):
    """Base error for chat persistence failures."""


class ChatSessionNotFoundError(ChatServiceError):
    def __init__(self, session_id: uuid.UUID, startup_id: uuid.UUID) -> None:
        super().__init__(f"Chat session '{session_id}' was not found for startup '{startup_id}'.")
        self.session_id = session_id
        self.startup_id = startup_id


class ChatStartupNotFoundError(ChatServiceError):
    def __init__(self, startup_id: uuid.UUID) -> None:
        super().__init__(f"Startup '{startup_id}' was not found.")
        self.startup_id = startup_id


class ChatService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_or_create_session(
        self,
        *,
        startup_id: uuid.UUID | str,
        session_id: uuid.UUID | str | None = None,
    ) -> ChatSession:
        startup_uuid = _coerce_uuid(startup_id)
        session_uuid = _coerce_uuid(session_id) if session_id is not None else None

        if session_uuid is not None:
            result = await self.session.execute(
                select(ChatSession).where(
                    ChatSession.id == session_uuid,
                    ChatSession.startup_id == startup_uuid,
                )
            )
            existing = result.scalar_one_or_none()
            if existing is None:
                raise ChatSessionNotFoundError(session_uuid, startup_uuid)
            return existing

        result = await self.session.execute(
            select(ChatSession)
            .where(ChatSession.startup_id == startup_uuid)
            .order_by(desc(ChatSession.sequence))
            .limit(1)
        )
        latest = result.scalar_one_or_none()
        if latest is not None:
            return latest

        startup_result = await self.session.execute(select(Startup.id).where(Startup.id == startup_uuid))
        if startup_result.scalar_one_or_none() is None:
            raise ChatStartupNotFoundError(startup_uuid)

        new_session = ChatSession(startup_id=startup_uuid)
        self.session.add(new_session)
        await self.session.commit()
        await self.session.refresh(new_session)
        return new_session

    async def get_session(
        self,
        *,
        startup_id: uuid.UUID | str,
        session_id: uuid.UUID | str | None = None,
    ) -> ChatSession | None:
        startup_uuid = _coerce_uuid(startup_id)
        session_uuid = _coerce_uuid(session_id) if session_id is not None else None

        if session_uuid is not None:
            result = await self.session.execute(
                select(ChatSession).where(
                    ChatSession.id == session_uuid,
                    ChatSession.startup_id == startup_uuid,
                )
            )
            existing = result.scalar_one_or_none()
            if existing is None:
                raise ChatSessionNotFoundError(session_uuid, startup_uuid)
            return existing

        result = await self.session.execute(
            select(ChatSession)
            .where(ChatSession.startup_id == startup_uuid)
            .order_by(desc(ChatSession.sequence))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def save_message(
        self,
        *,
        session_id: uuid.UUID | str,
        role: str,
        content: str,
        tool_call_data: dict[str, Any] | list[Any] | None = None,
    ) -> ChatMessage:
        message = ChatMessage(
            session_id=_coerce_uuid(session_id),
            role=role,
            content=content,
            tool_call_data=tool_call_data,
        )
        self.session.add(message)
        await self.session.commit()
        await self.session.refresh(message)
        return message

    async def get_recent_messages(
        self,
        *,
        session_id: uuid.UUID | str,
        limit: int,
    ) -> list[dict[str, Any]]:
        result = await self.session.execute(
            select(ChatMessage)
            .where(
                ChatMessage.session_id == _coerce_uuid(session_id),
                ChatMessage.role.in_(("user", "assistant")),
            )
            .order_by(desc(ChatMessage.sequence))
            .limit(limit)
        )
        rows = list(reversed(result.scalars().all()))
        return [_message_to_context(row) for row in rows]

    async def get_session_research_tool_call_data(
        self,
        *,
        session_id: uuid.UUID | str,
    ) -> list[dict[str, Any]]:
        """Return persisted research results from prior assistant turns in this session only."""
        result = await self.session.execute(
            select(ChatMessage.tool_call_data)
            .where(
                ChatMessage.session_id == _coerce_uuid(session_id),
                ChatMessage.role == "assistant",
            )
            .order_by(ChatMessage.sequence)
        )
        entries: list[dict[str, Any]] = []
        for tool_call_data in result.scalars():
            if isinstance(tool_call_data, list):
                entries.extend(item for item in tool_call_data if isinstance(item, dict))
        return entries

    async def get_display_messages(
        self,
        *,
        session_id: uuid.UUID | str,
        limit: int,
        before_sequence: int | None = None,
    ) -> list[dict[str, Any]]:
        filters = [
            ChatMessage.session_id == _coerce_uuid(session_id),
            ChatMessage.role.in_(("user", "assistant")),
        ]
        if before_sequence is not None:
            filters.append(ChatMessage.sequence < before_sequence)

        result = await self.session.execute(
            select(ChatMessage)
            .where(*filters)
            .order_by(desc(ChatMessage.sequence))
            .limit(limit)
        )
        rows = list(reversed(result.scalars().all()))
        return [_message_to_display(row) for row in rows]


def _message_to_context(message: ChatMessage) -> dict[str, Any]:
    return {
        "role": message.role,
        "content": message.content,
    }


def _message_to_display(message: ChatMessage) -> dict[str, Any]:
    return {
        "role": message.role,
        "content": message.content,
        "created_at": message.created_at.isoformat() if message.created_at else None,
        "sequence": message.sequence,
    }


def _coerce_uuid(value: uuid.UUID | str) -> uuid.UUID:
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
