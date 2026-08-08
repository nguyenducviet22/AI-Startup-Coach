import uuid
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    get_chat_client,
    get_chat_research_provider,
    get_local_user,
    get_research_provider,
    require_startup_owner,
)
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
    ResearchRequest as ApiResearchRequest,
    ResearchResponse,
    CreateStartupRequest,
    DocumentHistoryResponse,
    DocumentResponse,
    LocalProfileResponse,
    SetStageRequest,
    StartupListResponse,
    StartupOverviewResponse,
    StartupReportResponse,
    StartupResponse,
    UpdateLocalProfileRequest,
    UpdateStartupRequest,
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
from app.services.document_service import (
    DocumentService,
    DocumentVersionNotFoundError,
    UnknownDocumentTypeError,
)
from app.services.document_export_service import DocumentExportService
from app.services.local_profile_service import LocalProfileService
from app.services.agentops.instrumented_chat_client import InstrumentedChatClient
from app.services.agentops.instrumented_orchestrator import InstrumentedAgentOrchestrator
from app.services.agentops.instrumented_research_service import InstrumentedResearchService
from app.services.agentops.instrumented_tool_dispatcher import InstrumentedToolDispatcher
from app.services.orchestrator import AgentOrchestrator
from app.services.research_prompt import ResearchSkillLoader
from app.services.research_response_policy import apply_research_response_policy
from app.services.research_service import ResearchOwnerContext, ResearchService
from app.services.research_errors import ResearchServiceError
from app.services.skill_loader import SkillLoader
from app.services.tool_dispatcher import ResearchExecutionContext
from app.services.stage_service import AlreadyCompletedError, StageService
from app.services.startup_service import (
    StartupNotFoundError,
    StartupService,
    UserNotFoundError,
    startup_to_dict,
)
from app.services.startup_overview_service import StartupOverviewService
from app.services.startup_report_service import ReportSectionSelectionError, StartupReportService
from app.services.tool_dispatcher import ToolDispatcher
from app.research.protocol import ResearchProvider
from app.research.schemas import ResearchRequest

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


@router.get("/profile", response_model=LocalProfileResponse)
async def get_local_profile(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    return await LocalProfileService(session).get_or_create_profile()


@router.put("/profile", response_model=LocalProfileResponse)
async def update_local_profile(
    request: UpdateLocalProfileRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    return await LocalProfileService(session).update_profile(request.name)


@router.post(
    "/startups",
    response_model=StartupResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_startup(
    request: CreateStartupRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_local_user)],
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
    current_user: Annotated[User, Depends(get_local_user)],
) -> dict[str, Any]:
    startups = await StartupService(session).list_startups_for_user(current_user.id)
    return {"startups": startups}


@router.get("/startups/{startup_id}", response_model=StartupResponse)
async def get_startup(
    startup: Annotated[Startup, Depends(require_startup_owner)],
) -> dict[str, Any]:
    return startup_to_dict(startup)


@router.patch("/startups/{startup_id}", response_model=StartupResponse)
async def rename_startup(
    startup: Annotated[Startup, Depends(require_startup_owner)],
    request: UpdateStartupRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    return await StartupService(session).rename_startup(startup.id, request.name)


@router.get("/startups/{startup_id}/overview", response_model=StartupOverviewResponse)
async def get_startup_overview(
    startup: Annotated[Startup, Depends(require_startup_owner)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    return await StartupOverviewService(session).get_overview(startup.id)


@router.get("/startups/{startup_id}/report", response_model=StartupReportResponse)
async def get_startup_report(
    startup: Annotated[Startup, Depends(require_startup_owner)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    return await StartupReportService(session).get_report(startup.id)


@router.get("/startups/{startup_id}/report/export")
async def export_startup_report(
    startup: Annotated[Startup, Depends(require_startup_owner)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    format: Literal["pdf", "docx"] = Query("pdf"),
    sections: str | None = Query(None),
) -> Response:
    service = StartupReportService(session)
    report = await service.get_report(startup.id)
    requested = [item.strip() for item in sections.split(",") if item.strip()] if sections is not None else None
    try:
        selected = service.select_sections(report, requested)
    except ReportSectionSelectionError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    if not selected:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No report sections are available to export.")
    exported = DocumentExportService().export_report(
        startup_name=report["startup_name"],
        sections=selected,
        file_format=format,
    )
    return Response(content=exported.content, media_type=exported.media_type, headers={"Content-Disposition": f'attachment; filename="{exported.filename}"'})


@router.get("/startups/{startup_id}/pitch-deck/export")
async def export_pitch_deck(
    startup: Annotated[Startup, Depends(require_startup_owner)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    format: Literal["pdf"] = Query("pdf"),
) -> Response:
    funding = await DocumentService(session).get_current_document(startup_id=startup.id, doc_type="funding")
    raw_slides = funding["content"].get("pitch_outline") if funding is not None else None
    slides = [slide for slide in raw_slides if isinstance(slide, dict)] if isinstance(raw_slides, list) else []
    if not slides:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No pitch outline is available to export.")
    exported = DocumentExportService().export_pitch_deck(
        startup_name=startup.name or "Startup chưa đặt tên",
        slides=slides,
    )
    return Response(content=exported.content, media_type=exported.media_type, headers={"Content-Disposition": f'attachment; filename="{exported.filename}"'})


@router.post("/startups/{startup_id}/chat", response_model=ChatResponse)
async def chat(
    startup: Annotated[Startup, Depends(require_startup_owner)],
    request: ChatRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    chat_client: Annotated[ChatCompletionClient, Depends(get_chat_client)],
    research_provider: Annotated[ResearchProvider, Depends(get_chat_research_provider)],
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
        research_context = ResearchExecutionContext(
            startup_id=startup.id,
            user_id=startup.user_id,
            session_id=chat_session.id,
            turn_id=turn_id,
            stage=startup.current_stage,
        )
        instrumented_research_service = InstrumentedResearchService(
            wrapped=ResearchService(session, research_provider, settings),
            turn_id=turn_id,
            startup_id=startup.id,
            user_id=startup.user_id,
            session_id=chat_session.id,
            stage=startup.current_stage,
        )
        tool_dispatcher = InstrumentedToolDispatcher(
            wrapped=ToolDispatcher(
                document_service=document_service,
                research_service=instrumented_research_service,
                research_context=research_context,
            ),
            turn_id=turn_id,
            startup_id=startup.id,
            stage=startup.current_stage,
        )

        orchestrator = AgentOrchestrator(
            chat_client=instrumented_chat_client,
            tool_dispatcher=tool_dispatcher,
            skill_loader=ResearchSkillLoader(SkillLoader()),
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
        prior_research_tool_call_data = await chat_service.get_session_research_tool_call_data(
            session_id=chat_session.id,
        )
        policy_result = apply_research_response_policy(
            result.content,
            result.tool_call_data,
            prior_tool_call_data=prior_research_tool_call_data,
        )
        result = result.__class__(content=policy_result.content, stage_readiness=result.stage_readiness, tool_messages=result.tool_messages, tool_call_data=result.tool_call_data)

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
        "research": policy_result.research,
    }


@router.post("/startups/{startup_id}/research", response_model=ResearchResponse)
async def research(
    startup: Annotated[Startup, Depends(require_startup_owner)],
    request: ApiResearchRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    provider: Annotated[ResearchProvider, Depends(get_research_provider)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    try:
        research_request = ResearchRequest(**request.model_dump(exclude={"session_id"}))
    except ValidationError as exc:
        error = exc.errors()[0]
        field = ".".join(str(part) for part in error.get("loc", ("research",)))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "field": field,
                "code": "research_request_invalid",
                "message": error["msg"],
            },
        ) from exc

    chat_service = ChatService(session)
    try:
        chat_session = await chat_service.get_or_create_session(startup_id=startup.id, session_id=request.session_id)
        service = InstrumentedResearchService(
            wrapped=ResearchService(session, provider, settings), turn_id=None, startup_id=startup.id,
            user_id=startup.user_id, session_id=chat_session.id, stage=startup.current_stage,
        )
        outcome = await service.execute(
            owner=ResearchOwnerContext(startup_id=startup.id, user_id=startup.user_id, session_id=chat_session.id),
            request=research_request,
        )
    except ResearchServiceError as exc:
        status_code = status.HTTP_429_TOO_MANY_REQUESTS if exc.detail.code == "research_rate_limited" else status.HTTP_503_SERVICE_UNAVAILABLE
        raise HTTPException(status_code=status_code, detail=exc.detail.to_dict()) from exc
    result = outcome.result.model_dump(mode="json")
    notice = result.get("legal_notice")
    return {**result, "legal_notice": notice.get("message") if isinstance(notice, dict) else None}


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


@router.post(
    "/startups/{startup_id}/documents/{doc_type}/versions/{version}/restore",
    response_model=DocumentResponse,
)
async def restore_document_version(
    startup: Annotated[Startup, Depends(require_startup_owner)],
    doc_type: str,
    version: Annotated[int, Path(ge=1)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    try:
        return await DocumentService(session).restore_document_version(
            startup_id=startup.id,
            doc_type=doc_type,
            version=version,
        )
    except UnknownDocumentTypeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except DocumentVersionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/startups/{startup_id}/documents/{doc_type}/export")
async def export_document(
    startup: Annotated[Startup, Depends(require_startup_owner)],
    doc_type: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    format: Literal["pdf", "docx"] = Query("pdf"),
) -> Response:
    try:
        document = await DocumentService(session).get_current_document(
            startup_id=startup.id,
            doc_type=doc_type,
        )
        if document is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No current '{doc_type}' document was found for startup '{startup.id}'.",
            )
        exported = DocumentExportService().export(
            startup_name=startup.name or "Startup chưa đặt tên",
            doc_type=doc_type,
            content=document["content"],
            file_format=format,
        )
    except UnknownDocumentTypeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return Response(
        content=exported.content,
        media_type=exported.media_type,
        headers={"Content-Disposition": f'attachment; filename="{exported.filename}"'},
    )


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
