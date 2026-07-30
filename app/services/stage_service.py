import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.stages import InvalidStageError, get_next_stage, validate_stage
from app.models.startup import Startup
from app.services.startup_service import StartupNotFoundError, startup_to_dict


class AlreadyCompletedError(Exception):
    def __init__(self, startup_id: uuid.UUID) -> None:
        super().__init__(f"Startup '{startup_id}' is already completed.")
        self.startup_id = startup_id


class StageService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def advance_stage(self, startup_id: uuid.UUID | str) -> dict[str, Any]:
        startup_uuid = _coerce_uuid(startup_id)
        startup = await self._get_startup_for_update(startup_uuid)
        next_stage = get_next_stage(startup.current_stage)
        if next_stage is None:
            raise AlreadyCompletedError(startup_uuid)

        startup.current_stage = next_stage
        startup.updated_at = datetime.now(UTC)
        await self.session.commit()
        await self.session.refresh(startup)
        return startup_to_dict(startup)

    async def set_stage(self, startup_id: uuid.UUID | str, stage: str) -> dict[str, Any]:
        startup = await self._get_startup_for_update(_coerce_uuid(startup_id))
        try:
            startup.current_stage = validate_stage(stage)
            startup.updated_at = datetime.now(UTC)
        except InvalidStageError:
            await self.session.rollback()
            raise

        await self.session.commit()
        await self.session.refresh(startup)
        return startup_to_dict(startup)

    async def _get_startup_for_update(self, startup_id: uuid.UUID) -> Startup:
        result = await self.session.execute(
            select(Startup).where(Startup.id == startup_id).with_for_update()
        )
        startup = result.scalar_one_or_none()
        if startup is None:
            raise StartupNotFoundError(startup_id)
        return startup


def _coerce_uuid(value: uuid.UUID | str) -> uuid.UUID:
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
