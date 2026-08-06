from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import MODEL_PLACEHOLDERS, Settings, get_settings
from app.core.security import TokenExpiredError, TokenInvalidError, decode_access_token
from app.db.session import get_db_session
from app.llm.openrouter import ChatCompletionClient, OpenRouterChatClient
from app.models.startup import Startup
from app.models.user import User
from app.research.errors import ResearchProviderError
from app.research.protocol import ResearchProvider
from app.research.tavily import create_research_provider
from app.services.local_profile_service import LocalProfileService


def get_chat_client(
    settings: Annotated[Settings, Depends(get_settings)],
    openrouter_api_key: Annotated[
        str | None,
        Header(alias="X-OpenRouter-Api-Key", max_length=4096),
    ] = None,
) -> ChatCompletionClient:
    api_key = openrouter_api_key.strip() if openrouter_api_key else ""
    if not api_key:
        return OpenRouterChatClient(settings=settings)

    openrouter_model = settings.openrouter_model.strip()
    if not openrouter_model or openrouter_model in MODEL_PLACEHOLDERS:
        openrouter_model = "openrouter/auto"

    request_settings = settings.model_copy(
        update={
            "llm_provider": "openrouter",
            "llm_api_key": api_key,
            "llm_base_url": settings.openrouter_base_url.strip().rstrip("/"),
            "llm_model": openrouter_model,
            "llm_max_tokens": settings.openrouter_max_tokens,
        }
    )
    return OpenRouterChatClient(settings=request_settings)


def get_research_provider(settings: Annotated[Settings, Depends(get_settings)]) -> ResearchProvider:
    if not settings.research_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=ResearchProviderError("research_disabled").detail(),
        )
    if settings.research_provider != "tavily" or not settings.tavily_base_url.strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=ResearchProviderError("research_misconfigured").detail(),
        )
    if not settings.tavily_api_key.strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=ResearchProviderError("provider_missing_key").detail(),
        )
    return create_research_provider(settings)


def get_chat_research_provider(
    settings: Annotated[Settings, Depends(get_settings)],
) -> ResearchProvider:
    """Build the adapter for a chat turn without blocking non-research chat."""
    return create_research_provider(settings)


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


async def get_local_user(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    # Tokens remain accepted for backwards-compatible API clients, while the
    # local frontend intentionally sends none and receives the singleton user.
    if authorization is not None:
        return await get_current_user(session, settings, authorization)
    return await LocalProfileService(session).get_or_create_user()


async def require_startup_owner(
    startup_id: UUID,
    current_user: Annotated[User, Depends(get_local_user)],
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
