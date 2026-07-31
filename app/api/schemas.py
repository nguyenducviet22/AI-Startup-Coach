from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.domain.stages import StageName


OptionalName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Email = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=320)]
Password = Annotated[str, StringConstraints(min_length=8)]


class CreateStartupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: OptionalName | None = None


class StartupResponse(BaseModel):
    id: UUID
    user_id: UUID
    name: str | None
    current_stage: StageName
    created_at: str | None
    updated_at: str | None


class StartupListResponse(BaseModel):
    startups: list[StartupResponse]


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    session_id: UUID | None = None


class StageReadinessResponse(BaseModel):
    ready: bool
    missing_fields: list[str]


class ChatResponse(BaseModel):
    session_id: UUID
    message: str
    stage_readiness: StageReadinessResponse | None = None


class ChatMessageResponse(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    created_at: str | None
    sequence: int


class ChatMessagesResponse(BaseModel):
    session_id: UUID | None
    messages: list[ChatMessageResponse]


class AuthSignupRequest(BaseModel):
    name: OptionalName
    email: Email
    password: Password


class AuthLoginRequest(BaseModel):
    email: Email
    password: Password


class AuthRefreshRequest(BaseModel):
    refresh_token: str


class AuthLogoutRequest(BaseModel):
    refresh_token: str


class AuthUserResponse(BaseModel):
    id: UUID
    name: str
    email: str


class AuthTokenResponse(BaseModel):
    user: AuthUserResponse
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int


class AuthLogoutResponse(BaseModel):
    revoked: bool


class DocumentResponse(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: UUID
    startup_id: UUID
    doc_type: str
    version: int
    is_current: bool | None
    created_at: str | None
    content: dict[str, Any]


class DocumentHistoryResponse(BaseModel):
    documents: list[DocumentResponse]


class SetStageRequest(BaseModel):
    stage: StageName


class ErrorResponse(BaseModel):
    detail: str = Field(min_length=1)
