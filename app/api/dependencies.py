from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.security import TokenExpiredError, TokenInvalidError, decode_access_token
from app.db.session import get_db_session
from app.llm.openrouter import ChatCompletionClient, OpenRouterChatClient
from app.models.startup import Startup
from app.models.user import User


def get_chat_client() -> ChatCompletionClient:
    return OpenRouterChatClient()


async def get_current_user(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    if authorization is None or not authorization.startswith("Bearer "):
        raise _auth_exception("authorization", "missing_token", "Authorization bearer token is required.")

    token = authorization.removeprefix("Bearer ").strip()
    if token == "":
        raise _auth_exception("authorization", "missing_token", "Authorization bearer token is required.")

    try:
        payload = decode_access_token(token, settings=settings)
        user_id = UUID(str(payload["sub"]))
    except TokenExpiredError as exc:
        raise _auth_exception("authorization", "expired_token", "Access token has expired.") from exc
    except (TokenInvalidError, ValueError) as exc:
        raise _auth_exception("authorization", "invalid_token", "Access token is invalid.") from exc

    user = await session.get(User, user_id)
    if user is None:
        raise _auth_exception("authorization", "invalid_token", "Access token is invalid.")
    return user


async def require_startup_owner(
    startup_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Startup:
    result = await session.execute(select(Startup).where(Startup.id == startup_id))
    startup = result.scalar_one_or_none()
    if startup is None or startup.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Startup '{startup_id}' was not found.",
        )
    return startup


def _auth_exception(field: str, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "field": field,
            "code": code,
            "message": message,
        },
    )
