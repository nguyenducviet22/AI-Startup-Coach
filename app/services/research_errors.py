"""Structured, recoverable errors from the research service boundary."""

from dataclasses import dataclass
from datetime import datetime

from app.research.errors import ResearchProviderError


# These provider failures are transient/provider-originated conditions that
# contribute to AgentOps research_error_rate. Configuration, validation, quota,
# and provider request-rejection errors intentionally do not belong here.
PROVIDER_INFRASTRUCTURE_ERROR_CODES = frozenset(
    {
        "provider_timeout",
        "provider_rate_limited",
        "provider_unavailable",
        "provider_malformed_response",
    }
)


@dataclass(frozen=True)
class ResearchErrorDetail:
    field: str | None
    code: str
    message: str
    scope: str | None = None
    limit: int | None = None
    retry_at: datetime | None = None

    def to_dict(self) -> dict[str, object]:
        detail: dict[str, object] = {"field": self.field, "code": self.code, "message": self.message}
        if self.scope is not None:
            detail["scope"] = self.scope
        if self.limit is not None:
            detail["limit"] = self.limit
        if self.retry_at is not None:
            detail["retry_at"] = self.retry_at.isoformat()
        return detail


class ResearchServiceError(Exception):
    def __init__(self, detail: ResearchErrorDetail) -> None:
        self.detail = detail
        super().__init__(detail.code)


def provider_failure(error: ResearchProviderError) -> ResearchServiceError:
    return ResearchServiceError(
        ResearchErrorDetail(field="research", code=error.code, message=error.message)
    )


def validation_error(field: str, message: str, code: str = "research_validation_error") -> ResearchServiceError:
    return ResearchServiceError(ResearchErrorDetail(field=field, code=code, message=message))


def cache_conflict() -> ResearchServiceError:
    return ResearchServiceError(
        ResearchErrorDetail("research", "research_cache_conflict", "Research cache could not be updated.")
    )


def missing_owner_context() -> ResearchServiceError:
    return ResearchServiceError(
        ResearchErrorDetail("owner", "research_missing_owner_context", "Startup and user context are required.")
    )
