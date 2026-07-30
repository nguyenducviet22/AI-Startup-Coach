from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_chat_client
from app.api.schemas import (
    ChatRequest,
    ChatResponse,
    CreateStartupRequest,
    DocumentHistoryResponse,
    DocumentResponse,
    SetStageRequest,
    StartupResponse,
)
from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.domain.stages import InvalidStageError
from app.llm.openrouter import ChatCompletionClient
from app.services.chat_service import ChatService, ChatServiceError
from app.services.context_builder import StartupContext
from app.services.document_service import DocumentService, UnknownDocumentTypeError
from app.services.orchestrator import AgentOrchestrator
from app.services.stage_service import AlreadyCompletedError, StageService
from app.services.startup_service import (
    StartupNotFoundError,
    StartupService,
    UserNotFoundError,
)
from app.services.tool_dispatcher import ToolDispatcher

router = APIRouter()


@router.post(
    "/startups",
    response_model=StartupResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_startup(
    request: CreateStartupRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    try:
        return await StartupService(session).create_startup(
            user_id=request.user_id,
            name=request.name,
        )
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/startups/{startup_id}", response_model=StartupResponse)
async def get_startup(
    startup_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    try:
        return await StartupService(session).get_startup_data(startup_id)
    except StartupNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/startups/{startup_id}/chat", response_model=ChatResponse)
async def chat(
    startup_id: UUID,
    request: ChatRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    chat_client: Annotated[ChatCompletionClient, Depends(get_chat_client)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    startup_service = StartupService(session)
    chat_service = ChatService(session)
    document_service = DocumentService(session)

    try:
        startup = await startup_service.get_startup(startup_id)
        if startup.user_id != request.user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Startup '{startup_id}' was not found for user '{request.user_id}'.",
            )

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

        orchestrator = AgentOrchestrator(
            chat_client=chat_client,
            tool_dispatcher=ToolDispatcher(document_service=document_service),
        )
        result = await orchestrator.handle_turn(
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

    return {"session_id": chat_session.id, "message": result.content}


@router.get("/startups/{startup_id}/documents/{doc_type}", response_model=DocumentResponse)
async def get_current_document(
    startup_id: UUID,
    doc_type: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    try:
        document = await DocumentService(session).get_current_document(
            startup_id=startup_id,
            doc_type=doc_type,
        )
    except UnknownDocumentTypeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No current '{doc_type}' document was found for startup '{startup_id}'.",
        )
    return document


@router.get(
    "/startups/{startup_id}/documents/{doc_type}/history",
    response_model=DocumentHistoryResponse,
)
async def get_document_history(
    startup_id: UUID,
    doc_type: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    try:
        documents = await DocumentService(session).get_document_history(
            startup_id=startup_id,
            doc_type=doc_type,
        )
    except UnknownDocumentTypeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"documents": documents}


@router.post("/startups/{startup_id}/advance-stage", response_model=StartupResponse)
async def advance_stage(
    startup_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    try:
        return await StageService(session).advance_stage(startup_id)
    except StartupNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AlreadyCompletedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.patch("/startups/{startup_id}/stage", response_model=StartupResponse)
async def set_stage(
    startup_id: UUID,
    request: SetStageRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    try:
        return await StageService(session).set_stage(startup_id, request.stage)
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
