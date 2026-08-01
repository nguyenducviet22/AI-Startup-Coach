import uuid
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_chat_client, get_current_user, require_startup_owner
from app.api.schemas import (
    AuthLoginRequest,
    AuthLogoutRequest,
    AuthLogoutResponse,
    AuthRefreshRequest,
    AuthSignupRequest,
    AuthTokenResponse,
    ChatRequest,
    ChatMessagesResponse,
    ChatResponse,
    CreateStartupRequest,
    DocumentHistoryResponse,
    DocumentResponse,
    SetStageRequest,
    StartupListResponse,
    StartupResponse,
)
from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.domain.stages import InvalidStageError
from app.llm.openrouter import ChatCompletionClient
from app.models.startup import Startup
from app.models.user import User
from app.services.auth_service import AuthService, AuthServiceError
from app.services.chat_service import ChatService, ChatServiceError
from app.services.context_builder import StartupContext
from app.services.document_service import DocumentService, UnknownDocumentTypeError
from app.services.agentops.instrumented_chat_client import InstrumentedChatClient
from app.services.agentops.instrumented_orchestrator import InstrumentedAgentOrchestrator
from app.services.agentops.instrumented_tool_dispatcher import InstrumentedToolDispatcher
from app.services.orchestrator import AgentOrchestrator
from app.services.stage_service import AlreadyCompletedError, StageService
from app.services.startup_service import (
    StartupNotFoundError,
    StartupService,
    UserNotFoundError,
    startup_to_dict,
)
from app.services.tool_dispatcher import ToolDispatcher

router = APIRouter()


@router.post(
    "/auth/signup",
    response_model=AuthTokenResponse,
    status_code=status.HTTP_201_CREATED,
)
async def signup(
    request: AuthSignupRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    try:
        return await AuthService(session, settings=settings).signup(
            name=request.name,
            email=request.email,
            password=request.password,
        )
    except AuthServiceError as exc:
        raise _auth_http_exception(exc) from exc


@router.post("/auth/login", response_model=AuthTokenResponse)
async def login(
    request: AuthLoginRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    # Frontend phase must deliberately choose JSON storage vs. httpOnly cookies for refresh tokens.
    try:
        return await AuthService(session, settings=settings).login(
            email=request.email,
            password=request.password,
        )
    except AuthServiceError as exc:
        raise _auth_http_exception(exc) from exc


@router.post("/auth/refresh", response_model=AuthTokenResponse)
async def refresh(
    request: AuthRefreshRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    # Frontend phase must deliberately choose JSON storage vs. httpOnly cookies for refresh tokens.
    try:
        return await AuthService(session, settings=settings).refresh(request.refresh_token)
    except AuthServiceError as exc:
        raise _auth_http_exception(exc) from exc


@router.post("/auth/logout", response_model=AuthLogoutResponse)
async def logout(
    request: AuthLogoutRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, bool]:
    try:
        return await AuthService(session, settings=settings).logout(request.refresh_token)
    except AuthServiceError as exc:
        raise _auth_http_exception(exc) from exc


@router.post(
    "/startups",
    response_model=StartupResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_startup(
    request: CreateStartupRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    try:
        return await StartupService(session).create_startup(
            user_id=current_user.id,
            name=request.name,
        )
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/startups", response_model=StartupListResponse)
async def list_startups(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    startups = await StartupService(session).list_startups_for_user(current_user.id)
    return {"startups": startups}


@router.get("/startups/{startup_id}", response_model=StartupResponse)
async def get_startup(
    startup: Annotated[Startup, Depends(require_startup_owner)],
) -> dict[str, Any]:
    return startup_to_dict(startup)


@router.post("/startups/{startup_id}/chat", response_model=ChatResponse)
async def chat(
    startup: Annotated[Startup, Depends(require_startup_owner)],
    request: ChatRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    chat_client: Annotated[ChatCompletionClient, Depends(get_chat_client)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    chat_service = ChatService(session)
    document_service = DocumentService(session)

    try:
        chat_session = await chat_service.get_or_create_session(
            startup_id=startup.id,
            session_id=request.session_id,
        )
        history = await chat_service.get_recent_messages(
            session_id=chat_session.id,
            limit=settings.chat_history_limit,
        )
        current_document = await _get_current_stage_document(
            document_service=document_service,
            startup_id=startup.id,
            current_stage=startup.current_stage,
        )
        turn_id = uuid.uuid4()
        instrumented_chat_client = InstrumentedChatClient(
            wrapped=chat_client,
            turn_id=turn_id,
            startup_id=startup.id,
            session_id=chat_session.id,
            stage=startup.current_stage,
            settings=settings,
        )
        tool_dispatcher = InstrumentedToolDispatcher(
            wrapped=ToolDispatcher(document_service=document_service),
            turn_id=turn_id,
            startup_id=startup.id,
            stage=startup.current_stage,
        )

        orchestrator = AgentOrchestrator(
            chat_client=instrumented_chat_client,
            tool_dispatcher=tool_dispatcher,
            settings=settings,
        )
        instrumented_orchestrator = InstrumentedAgentOrchestrator(
            wrapped=orchestrator,
            turn_id=turn_id,
            startup_id=startup.id,
            session_id=chat_session.id,
            stage=startup.current_stage,
        )
        result = await instrumented_orchestrator.handle_turn(
            startup=StartupContext(
                startup_id=str(startup.id),
                user_id=str(startup.user_id),
                current_stage=startup.current_stage,
                name=startup.name,
            ),
            history=history,
            user_message=request.message,
            current_document=current_document,
        )

        await chat_service.save_message(
            session_id=chat_session.id,
            role="user",
            content=request.message,
        )
        for tool_message in result.tool_messages:
            await chat_service.save_message(
                session_id=chat_session.id,
                role="tool",
                content=tool_message["content"],
                tool_call_data={
                    "tool_call_id": tool_message["tool_call_id"],
                },
            )
        await chat_service.save_message(
            session_id=chat_session.id,
            role="assistant",
            content=result.content,
            tool_call_data=result.tool_call_data or None,
        )
    except StartupNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ChatServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return {
        "session_id": chat_session.id,
        "message": result.content,
        "stage_readiness": result.stage_readiness,
    }


@router.get("/startups/{startup_id}/chat/messages", response_model=ChatMessagesResponse)
async def get_chat_messages(
    startup: Annotated[Startup, Depends(require_startup_owner)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    session_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    before_sequence: Annotated[int | None, Query(ge=1)] = None,
) -> dict[str, Any]:
    chat_service = ChatService(session)
    try:
        chat_session = await chat_service.get_session(
            startup_id=startup.id,
            session_id=session_id,
        )
    except ChatServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    if chat_session is None:
        return {"session_id": None, "messages": []}

    messages = await chat_service.get_display_messages(
        session_id=chat_session.id,
        limit=limit,
        before_sequence=before_sequence,
    )
    return {"session_id": chat_session.id, "messages": messages}


@router.get("/startups/{startup_id}/documents/{doc_type}", response_model=DocumentResponse)
async def get_current_document(
    startup: Annotated[Startup, Depends(require_startup_owner)],
    doc_type: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    try:
        document = await DocumentService(session).get_current_document(
            startup_id=startup.id,
            doc_type=doc_type,
        )
    except UnknownDocumentTypeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No current '{doc_type}' document was found for startup '{startup.id}'.",
        )
    return document


@router.get(
    "/startups/{startup_id}/documents/{doc_type}/history",
    response_model=DocumentHistoryResponse,
)
async def get_document_history(
    startup: Annotated[Startup, Depends(require_startup_owner)],
    doc_type: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    try:
        documents = await DocumentService(session).get_document_history(
            startup_id=startup.id,
            doc_type=doc_type,
        )
    except UnknownDocumentTypeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"documents": documents}


@router.post("/startups/{startup_id}/advance-stage", response_model=StartupResponse)
async def advance_stage(
    startup: Annotated[Startup, Depends(require_startup_owner)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    try:
        return await StageService(session).advance_stage(startup.id)
    except StartupNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AlreadyCompletedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.patch("/startups/{startup_id}/stage", response_model=StartupResponse)
async def set_stage(
    startup: Annotated[Startup, Depends(require_startup_owner)],
    request: SetStageRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    try:
        return await StageService(session).set_stage(startup.id, request.stage)
    except StartupNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InvalidStageError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


async def _get_current_stage_document(
    *,
    document_service: DocumentService,
    startup_id: UUID,
    current_stage: str,
) -> dict[str, Any] | None:
    if current_stage in {"idea", "completed"}:
        return None
    return await document_service.get_current_document(
        startup_id=startup_id,
        doc_type=current_stage,
    )


def _auth_http_exception(exc: AuthServiceError) -> HTTPException:
    status_by_code = {
        "email_taken": status.HTTP_409_CONFLICT,
        "invalid_credentials": status.HTTP_401_UNAUTHORIZED,
        "missing_token": status.HTTP_401_UNAUTHORIZED,
        "invalid_token": status.HTTP_401_UNAUTHORIZED,
        "expired_token": status.HTTP_401_UNAUTHORIZED,
        "refresh_reused": status.HTTP_401_UNAUTHORIZED,
        "refresh_revoked": status.HTTP_401_UNAUTHORIZED,
    }
    return HTTPException(
        status_code=status_by_code.get(exc.detail.code, status.HTTP_400_BAD_REQUEST),
        detail=exc.detail.to_dict(),
    )
