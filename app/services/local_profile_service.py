from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


LOCAL_USER_EMAIL = "local@ai-startup-coach.local"


class LocalProfileService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_or_create_user(self) -> User:
        result = await self.session.execute(select(User).where(User.email == LOCAL_USER_EMAIL))
        user = result.scalar_one_or_none()
        if user is not None:
            return user

        user = User(name="", email=LOCAL_USER_EMAIL)
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def get_or_create_profile(self) -> dict[str, Any]:
        return profile_to_dict(await self.get_or_create_user())

    async def update_profile(self, name: str) -> dict[str, Any]:
        user = await self.get_or_create_user()
        user.name = name.strip()
        await self.session.commit()
        await self.session.refresh(user)
        return profile_to_dict(user)


def profile_to_dict(user: User) -> dict[str, Any]:
    return {"name": user.name, "configured": bool(user.name.strip())}
