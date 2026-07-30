import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.startup import Startup
from app.models.user import User


class StartupServiceError(Exception):
    """Base error for startup persistence failures."""


class StartupNotFoundError(StartupServiceError):
    def __init__(self, startup_id: uuid.UUID) -> None:
        super().__init__(f"Startup '{startup_id}' was not found.")
        self.startup_id = startup_id


class UserNotFoundError(StartupServiceError):
    def __init__(self, user_id: uuid.UUID) -> None:
        super().__init__(f"User '{user_id}' was not found.")
        self.user_id = user_id


class StartupService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_startup(
        self,
        *,
        user_id: uuid.UUID | str,
        name: str | None = None,
    ) -> dict[str, Any]:
        user_uuid = _coerce_uuid(user_id)
        user_result = await self.session.execute(select(User.id).where(User.id == user_uuid))
        if user_result.scalar_one_or_none() is None:
            raise UserNotFoundError(user_uuid)

        startup = Startup(user_id=user_uuid, name=name)
        self.session.add(startup)
        await self.session.commit()
        await self.session.refresh(startup)
        return startup_to_dict(startup)

    async def get_startup(self, startup_id: uuid.UUID | str) -> Startup:
        startup_uuid = _coerce_uuid(startup_id)
        result = await self.session.execute(select(Startup).where(Startup.id == startup_uuid))
        startup = result.scalar_one_or_none()
        if startup is None:
            raise StartupNotFoundError(startup_uuid)
        return startup

    async def get_startup_data(self, startup_id: uuid.UUID | str) -> dict[str, Any]:
        return startup_to_dict(await self.get_startup(startup_id))


def startup_to_dict(startup: Startup) -> dict[str, Any]:
    return {
        "id": str(startup.id),
        "user_id": str(startup.user_id),
        "name": startup.name,
        "current_stage": startup.current_stage,
        "created_at": startup.created_at.isoformat() if startup.created_at is not None else None,
        "updated_at": startup.updated_at.isoformat() if startup.updated_at is not None else None,
    }


def _coerce_uuid(value: uuid.UUID | str) -> uuid.UUID:
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
