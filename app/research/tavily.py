"""Tavily HTTP adapter; all vendor payload handling is contained in this module."""

import asyncio
import hashlib
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime
from typing import Any
from urllib.parse import urlparse

import httpx
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.research.errors import ResearchProviderError
from app.research.schemas import (
    MAX_EVIDENCE_EXCERPT_LENGTH,
    EvidenceAuthority,
    EvidenceRecord,
    ProviderExtractResponse,
    ProviderSearchResponse,
)

_TRANSIENT_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}


class TavilyResearchProvider:
    def __init__(
        self,
        settings: Settings | None = None,
        http_client: httpx.AsyncClient | Any | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.settings = settings or get_settings()
        self._http_client = http_client
        self._sleep = sleep

    async def search(
        self,
        *,
        query: str,
        topic: str,
        search_depth: str,
        max_results: int,
        include_domains: list[str],
        start_date: date | None,
        end_date: date | None,
    ) -> ProviderSearchResponse:
        payload: dict[str, Any] = {
            "query": query,
            "topic": topic,
            "search_depth": search_depth,
            "max_results": max_results,
            "include_domains": include_domains,
            "include_answer": False,
        }
        if start_date is not None:
            payload["start_date"] = start_date.isoformat()
        if end_date is not None:
            payload["end_date"] = end_date.isoformat()
        response = await self._post("/search", payload)
        retrieved_at = datetime.now(UTC)
        evidence = self._normalize_search_results(response.get("results"), retrieved_at, topic)
        return ProviderSearchResponse(
            evidence=evidence,
            request_id=self._request_id(response),
            credits_used=self._credits_used(response),
            retrieved_at=retrieved_at,
        )

    async def extract(
        self,
        *,
        urls: list[str],
        query: str | None,
        extract_depth: str,
    ) -> ProviderExtractResponse:
        valid_urls = [url for url in urls if self._is_http_url(url)]
        if not valid_urls:
            raise ResearchProviderError("provider_malformed_response")
        payload: dict[str, Any] = {"urls": valid_urls, "extract_depth": extract_depth}
        if query is not None:
            payload["query"] = query
        response = await self._post("/extract", payload)
        retrieved_at = datetime.now(UTC)
        evidence = self._normalize_extract_results(response.get("results"), retrieved_at)
        return ProviderExtractResponse(
            evidence=evidence,
            request_id=self._request_id(response),
            credits_used=self._credits_used(response),
            retrieved_at=retrieved_at,
        )

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.settings.research_enabled:
            raise ResearchProviderError("research_disabled")
        if self.settings.research_provider != "tavily" or not self.settings.tavily_base_url.strip():
            raise ResearchProviderError("research_misconfigured")
        if not self.settings.tavily_api_key.strip():
            raise ResearchProviderError("provider_missing_key")
        last_error: ResearchProviderError | None = None
        for attempt in range(self.settings.research_provider_max_retries + 1):
            try:
                response = await self._send_post(path, payload)
                if response.status_code == 429:
                    raise ResearchProviderError("provider_rate_limited")
                if response.status_code >= 400:
                    if response.status_code in _TRANSIENT_STATUS_CODES:
                        raise ResearchProviderError("provider_unavailable")
                    raise ResearchProviderError("provider_request_rejected")
                body = response.json()
                if not isinstance(body, dict):
                    raise ResearchProviderError("provider_malformed_response")
                return body
            except ResearchProviderError as exc:
                last_error = exc
                if exc.code not in {"provider_timeout", "provider_unavailable"} or not self._can_retry(attempt):
                    raise
            except httpx.TimeoutException:
                last_error = ResearchProviderError("provider_timeout")
                if not self._can_retry(attempt):
                    raise last_error
            except (httpx.RequestError, ValueError):
                last_error = ResearchProviderError("provider_unavailable")
                if not self._can_retry(attempt):
                    raise last_error
            await self._sleep(0)
        raise last_error or ResearchProviderError("provider_unavailable")

    async def _send_post(self, path: str, payload: dict[str, Any]) -> httpx.Response:
        headers = {"Authorization": f"Bearer {self.settings.tavily_api_key}"}
        if self._http_client is not None:
            return await self._http_client.post(path, json=payload, headers=headers)
        async with httpx.AsyncClient(
            base_url=self.settings.tavily_base_url,
            timeout=self.settings.research_provider_timeout_seconds,
        ) as client:
            return await client.post(path, json=payload, headers=headers)

    def _normalize_search_results(
        self, raw_results: Any, retrieved_at: datetime, topic: str
    ) -> list[EvidenceRecord]:
        if not isinstance(raw_results, list):
            raise ResearchProviderError("provider_malformed_response")
        return self._normalize_records(raw_results, retrieved_at, topic == "legal")

    def _normalize_extract_results(
        self, raw_results: Any, retrieved_at: datetime
    ) -> list[EvidenceRecord]:
        if not isinstance(raw_results, list):
            raise ResearchProviderError("provider_malformed_response")
        return self._normalize_records(raw_results, retrieved_at, False)

    @staticmethod
    def _normalize_records(
        raw_results: list[Any], retrieved_at: datetime, legal: bool
    ) -> list[EvidenceRecord]:
        evidence: list[EvidenceRecord] = []
        for item in raw_results:
            if not isinstance(item, dict):
                continue
            url = item.get("url")
            title = item.get("title") or url
            content = item.get("content") or item.get("raw_content")
            if not isinstance(url, str) or not TavilyResearchProvider._is_http_url(url):
                continue
            if not isinstance(title, str) or not title.strip() or not isinstance(content, str) or not content.strip():
                continue
            try:
                evidence.append(
                    EvidenceRecord(
                        source_id=hashlib.sha256(url.encode("utf-8")).hexdigest()[:32],
                        url=url,
                        title=title.strip(),
                        excerpt=content.strip()[:MAX_EVIDENCE_EXCERPT_LENGTH],
                        retrieved_at=retrieved_at,
                        published_at=TavilyResearchProvider._published_at(item),
                        authority=TavilyResearchProvider._authority_for(url),
                        legal_or_regulatory=legal or TavilyResearchProvider._is_legal_source(url),
                    )
                )
            except ValidationError:
                continue
        return evidence

    @staticmethod
    def _published_at(item: dict[str, Any]) -> datetime | None:
        value = item.get("published_date") or item.get("published_at")
        if not isinstance(value, str):
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(UTC)

    @staticmethod
    def _request_id(response: dict[str, Any]) -> str | None:
        request_id = response.get("request_id")
        return request_id if isinstance(request_id, str) and request_id.strip() else None

    @staticmethod
    def _credits_used(response: dict[str, Any]) -> int | None:
        usage = response.get("usage")
        if not isinstance(usage, dict):
            return None
        credits = usage.get("credits")
        return credits if isinstance(credits, int) and credits >= 0 else None

    @staticmethod
    def _is_http_url(value: str) -> bool:
        parsed = urlparse(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    @staticmethod
    def _authority_for(url: str) -> EvidenceAuthority:
        host = (urlparse(url).hostname or "").lower()
        if host.endswith(".gov") or host.endswith(".gov.uk") or host.endswith(".europa.eu"):
            return EvidenceAuthority.OFFICIAL
        if host.endswith(".edu") or host.endswith(".org"):
            return EvidenceAuthority.SECONDARY
        return EvidenceAuthority.UNKNOWN

    @staticmethod
    def _is_legal_source(url: str) -> bool:
        host = (urlparse(url).hostname or "").lower()
        return host.endswith(".gov") or host.endswith(".gov.uk") or "court" in host

    def _can_retry(self, attempt: int) -> bool:
        return attempt < self.settings.research_provider_max_retries


def create_research_provider(settings: Settings) -> TavilyResearchProvider:
    """Construct this adapter without exposing its implementation type to routes."""
    return TavilyResearchProvider(settings=settings)
