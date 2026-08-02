from unittest.mock import AsyncMock, MagicMock

import app.db.base  # noqa: F401
from app.models.user import User
from app.services.local_profile_service import LOCAL_USER_EMAIL, LocalProfileService


async def test_get_profile_returns_unconfigured_local_user() -> None:
    user = User(name="", email=LOCAL_USER_EMAIL)
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    session = AsyncMock()
    session.execute.return_value = result

    profile = await LocalProfileService(session).get_or_create_profile()

    assert profile["name"] == ""
    assert profile["configured"] is False
    session.add.assert_not_called()


async def test_update_profile_persists_trimmed_name() -> None:
    user = User(name="", email=LOCAL_USER_EMAIL)
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    session = AsyncMock()
    session.execute.return_value = result

    profile = await LocalProfileService(session).update_profile("  Nguyễn Thị Nhã Uyên  ")

    assert profile == {"name": "Nguyễn Thị Nhã Uyên", "configured": True}
    assert user.name == "Nguyễn Thị Nhã Uyên"
    session.commit.assert_awaited_once()
