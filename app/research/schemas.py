"""Provider-neutral, normalized research records.

These models are the only evidence shape consumed outside a provider adapter.
"""

from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StringConstraints, field_validator, model_validator

MAX_EVIDENCE_EXCERPT_LENGTH = 1_000
LEGAL_NOTICE = (
    "This is not legal advice. Laws and regulations change and vary by jurisdiction. "
    "Verify the cited primary sources and consult a qualified legal professional before acting."
)


class ResearchCategory(StrEnum):
    GENERAL = "general"
    NEWS = "news"
    PRICING = "pricing"
    LEGAL = "legal"


class SearchDepth(StrEnum):
    BASIC = "basic"
    ADVANCED = "advanced"


class EvidenceAuthority(StrEnum):
    PRIMARY = "primary"
    OFFICIAL = "official"
    SECONDARY = "secondary"
    UNKNOWN = "unknown"


class LegalNotice(BaseModel):
    model_config = ConfigDict(frozen=True)

    required: bool = True
    message: str = LEGAL_NOTICE


class EvidenceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
    url: HttpUrl
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=512)]
    excerpt: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_EVIDENCE_EXCERPT_LENGTH),
    ]
    retrieved_at: datetime
    published_at: datetime | None = None
    authority: EvidenceAuthority
    legal_or_regulatory: bool

    @field_validator("url")
    @classmethod
    def require_http_url(cls, value: HttpUrl) -> HttpUrl:
        if value.scheme not in {"http", "https"}:
            raise ValueError("Evidence URLs must use http or https.")
        return value

    @field_validator("retrieved_at", "published_at")
    @classmethod
    def require_utc_datetime(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
            raise ValueError("Evidence timestamps must be UTC.")
        return value.astimezone(UTC)


class ResearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2_000)] | None = None
    urls: list[HttpUrl] = Field(default_factory=list, max_length=5)
    category: ResearchCategory = ResearchCategory.GENERAL
    search_depth: SearchDepth = SearchDepth.BASIC
    max_results: Annotated[int, Field(ge=1, le=20)] = 5
    include_domains: list[str] = Field(default_factory=list)
    start_date: date | None = None
    end_date: date | None = None
    jurisdiction: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
    ] | None = None
    force_refresh: bool = False

    @model_validator(mode="after")
    def require_query_or_urls(self) -> "ResearchRequest":
        if self.query is None and not self.urls:
            raise ValueError("Provide a non-empty query or at least one extraction URL.")
        return self


class ResearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    call_id: UUID | None = None
    provider_request_id: str | None = None
    evidence: list[EvidenceRecord]
    cache_hit: bool = False
    cache_key: str | None = None
    retrieved_at: datetime
    served_at: datetime
    legal_notice: LegalNotice | None = None

    @field_validator("retrieved_at", "served_at")
    @classmethod
    def require_utc_result_datetime(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
            raise ValueError("Research timestamps must be UTC.")
        return value.astimezone(UTC)


class ProviderSearchResponse(BaseModel):
    """Normalized search output, deliberately independent of any vendor payload."""

    model_config = ConfigDict(extra="forbid")

    evidence: list[EvidenceRecord]
    request_id: str | None = None
    credits_used: int | None = Field(default=None, ge=0)
    retrieved_at: datetime


class ProviderExtractResponse(BaseModel):
    """Normalized extract output, deliberately independent of any vendor payload."""

    model_config = ConfigDict(extra="forbid")

    evidence: list[EvidenceRecord]
    request_id: str | None = None
    credits_used: int | None = Field(default=None, ge=0)
    retrieved_at: datetime
