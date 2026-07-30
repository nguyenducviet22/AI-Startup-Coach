from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.domain.stages import StageName


OptionalName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class CreateStartupRequest(BaseModel):
    user_id: UUID
    name: OptionalName | None = None


class StartupResponse(BaseModel):
    id: UUID
    user_id: UUID
    name: str | None
    current_stage: StageName
    created_at: str | None
    updated_at: str | None


class ChatRequest(BaseModel):
    user_id: UUID
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    session_id: UUID | None = None


class ChatResponse(BaseModel):
    session_id: UUID
    message: str


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
