"""Sanitized errors that may cross the research-provider boundary."""

from typing import Literal

ProviderErrorCode = Literal[
    "provider_timeout",
    "provider_rate_limited",
    "provider_unavailable",
    "provider_request_rejected",
    "provider_malformed_response",
    "provider_missing_key",
    "research_disabled",
    "research_misconfigured",
]

_MESSAGES: dict[ProviderErrorCode, str] = {
    "provider_timeout": "The research provider timed out. Please try again.",
    "provider_rate_limited": "The research provider is temporarily rate limited. Please try again.",
    "provider_unavailable": "The research provider is temporarily unavailable. Please try again.",
    "provider_request_rejected": "The research provider rejected the request.",
    "provider_malformed_response": "The research provider returned an invalid response.",
    "provider_missing_key": "Live research is not configured.",
    "research_disabled": "Research is disabled.",
    "research_misconfigured": "Research is not configured correctly.",
}


class ResearchProviderError(RuntimeError):
    """An error safe to expose to a service as a structured detail."""

    def __init__(self, code: ProviderErrorCode) -> None:
        self.code = code
        self.message = _MESSAGES[code]
        super().__init__(code)

    def detail(self, *, field: str = "research") -> dict[str, str]:
        return {"field": field, "code": self.code, "message": self.message}
