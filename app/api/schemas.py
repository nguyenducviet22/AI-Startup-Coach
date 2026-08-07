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


class UpdateStartupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: OptionalName


class LocalProfileResponse(BaseModel):
    name: str
    configured: bool


class UpdateLocalProfileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


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
    research: "ResearchResponse | None" = None


class ResearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2_000)] | None = None
    urls: list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2_000)]] = Field(default_factory=list, max_length=5)
    category: Literal["general", "news", "pricing", "legal"] = "general"
    search_depth: Literal["basic", "advanced"] = "basic"
    include_domains: list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]] = Field(default_factory=list, max_length=20)
    start_date: str | None = None
    end_date: str | None = None
    jurisdiction: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)] | None = None
    force_refresh: bool = False
    max_results: Annotated[int, Field(ge=1, le=20)] = 5
    session_id: UUID | None = None


class ResearchEvidenceResponse(BaseModel):
    source_id: str
    url: str
    title: str
    excerpt: str
    retrieved_at: str
    published_at: str | None
    authority: str
    legal_or_regulatory: bool


class ResearchResponse(BaseModel):
    evidence: list[ResearchEvidenceResponse]
    cache_hit: bool
    retrieved_at: str
    served_at: str
    legal_notice: str | None = None


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


class DocumentProgressResponse(BaseModel):
    doc_type: str
    exists: bool
    version: int | None
    updated_at: str | None


class RecentDocumentUpdateResponse(BaseModel):
    doc_type: str
    version: int
    updated_at: str | None


class StartupOverviewResponse(BaseModel):
    current_stage: StageName
    journey_completed_steps: int
    journey_total_steps: int
    completed_documents: int
    total_documents: int
    total_versions: int
    documents: list[DocumentProgressResponse]
    recent_updates: list[RecentDocumentUpdateResponse]


class ReportSectionResponse(BaseModel):
    key: str
    title: str
    available: bool
    content: dict[str, Any]


class StartupReportResponse(BaseModel):
    startup_id: UUID
    startup_name: str
    sections: list[ReportSectionResponse]


class SetStageRequest(BaseModel):
    stage: StageName


class ErrorResponse(BaseModel):
    detail: str = Field(min_length=1)
