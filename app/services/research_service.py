"""Shared, provider-neutral research use case for chat tools and founder requests."""

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.research.errors import ResearchProviderError
from app.research.protocol import ResearchProvider
from app.research.schemas import LegalNotice, ResearchCategory, ResearchRequest, ResearchResult
from app.services.research_cache_service import ResearchCacheService
from app.services.research_errors import missing_owner_context, provider_failure, validation_error
from app.services.research_quota_service import ResearchQuotaService


@dataclass(frozen=True)
class ResearchOwnerContext:
    startup_id: UUID | None
    user_id: UUID | None
    session_id: UUID | None = None


@dataclass(frozen=True)
class ResearchAccountingOutcome:
    provider: str
    operation: str
    query_fingerprint: str
    provider_call_made: bool
    cache_hit: bool
    credits_reserved: int | None
    credits_charged: int | None
    provider_request_id: str | None
    cost_usd: None = None
    pricing_unknown: bool = True


@dataclass(frozen=True)
class ResearchServiceResult:
    result: ResearchResult
    accounting: ResearchAccountingOutcome


class ResearchService:
    def __init__(
        self,
        session: AsyncSession,
        provider: ResearchProvider,
        settings: Settings,
        quota_service: ResearchQuotaService | None = None,
        cache_service: ResearchCacheService | None = None,
    ) -> None:
        self.session = session
        self.provider = provider
        self.settings = settings
        self.quota_service = quota_service or ResearchQuotaService(session, settings)
        self.cache_service = cache_service or ResearchCacheService(session, settings)

    async def execute(
        self,
        *,
        owner: ResearchOwnerContext,
        request: ResearchRequest,
        locale: str | None = None,
        authority_mode: str = "standard",
    ) -> ResearchServiceResult:
        if owner.startup_id is None or owner.user_id is None:
            raise missing_owner_context()
        if request.category is ResearchCategory.LEGAL and not request.jurisdiction:
            raise validation_error(
                "jurisdiction",
                "A jurisdiction is required for legal or regulatory research.",
                "research_jurisdiction_required",
            )
        extraction_urls = [str(url) for url in request.urls]
        operation = "extract" if extraction_urls else "search"
        normalized_subject = "|".join(extraction_urls) if extraction_urls else request.query
        assert normalized_subject is not None
        cache_key = self.cache_service.build_key(
            startup_id=owner.startup_id,
            provider=self.settings.research_provider,
            operation=operation,
            query_or_url=normalized_subject,
            locale=locale,
            topic=request.category.value,
            start_date=request.start_date.isoformat() if request.start_date else None,
            end_date=request.end_date.isoformat() if request.end_date else None,
            domains=request.include_domains,
            max_results=request.max_results,
            depth=request.search_depth.value,
            authority_mode=authority_mode,
            legal_mode=request.category is ResearchCategory.LEGAL,
        )
        fingerprint = hashlib.sha256(normalized_subject.encode("utf-8")).hexdigest()
        if not request.force_refresh:
            cached = await self.cache_service.get(startup_id=owner.startup_id, cache_key=cache_key)
            if cached is not None:
                return ResearchServiceResult(
                    result=cached,
                    accounting=ResearchAccountingOutcome(
                        provider=self.settings.research_provider,
                        operation=operation,
                        query_fingerprint=fingerprint,
                        provider_call_made=False,
                        cache_hit=True,
                        credits_reserved=None,
                        credits_charged=0,
                        provider_request_id=cached.provider_request_id,
                    ),
                )

        reserved_credits = self._reserved_credits(operation, request, extraction_urls)
        reservation = await self.quota_service.reserve(
            user_id=owner.user_id,
            session_id=owner.session_id,
            credits=reserved_credits,
        )
        try:
            if extraction_urls:
                provider_result = await self.provider.extract(
                    urls=extraction_urls,
                    query=request.query,
                    extract_depth=request.search_depth.value,
                )
            else:
                provider_result = await self.provider.search(
                    query=request.query,
                    topic=request.category.value,
                    search_depth=request.search_depth.value,
                    max_results=request.max_results,
                    include_domains=request.include_domains,
                    start_date=request.start_date,
                    end_date=request.end_date,
                )
        except ResearchProviderError as exc:
            await self.quota_service.reconcile(
                reservation=reservation,
                credits_charged=None,
                provider_succeeded=False,
            )
            raise provider_failure(exc) from exc
        except Exception:
            await self.quota_service.reconcile(
                reservation=reservation,
                credits_charged=None,
                provider_succeeded=False,
            )
            raise provider_failure(ResearchProviderError("provider_unavailable"))

        served_at = datetime.now(UTC)
        result = ResearchResult(
            provider_request_id=provider_result.request_id,
            evidence=provider_result.evidence,
            cache_hit=False,
            cache_key=cache_key,
            retrieved_at=provider_result.retrieved_at,
            served_at=served_at,
            legal_notice=(
                LegalNotice()
                if request.category is ResearchCategory.LEGAL
                or any(record.legal_or_regulatory for record in provider_result.evidence)
                else None
            ),
        )
        await self.quota_service.reconcile(
            reservation=reservation,
            credits_charged=provider_result.credits_used,
            provider_succeeded=True,
        )
        await self.cache_service.put(
            startup_id=owner.startup_id,
            cache_key=cache_key,
            operation=operation,
            category=request.category,
            result=result,
        )
        return ResearchServiceResult(
            result=result,
            accounting=ResearchAccountingOutcome(
                provider=self.settings.research_provider,
                operation=operation,
                query_fingerprint=fingerprint,
                provider_call_made=True,
                cache_hit=False,
                credits_reserved=reserved_credits,
                credits_charged=(
                    reserved_credits if provider_result.credits_used is None else provider_result.credits_used
                ),
                provider_request_id=provider_result.request_id,
            ),
        )

    def _reserved_credits(
        self, operation: str, request: ResearchRequest, urls: list[str] | None
    ) -> int:
        if operation == "extract":
            return max(1, ((len(urls or []) + 4) // 5) * self.settings.tavily_extract_credits_per_five_urls)
        if request.search_depth.value == "advanced":
            return self.settings.tavily_advanced_search_credits
        return self.settings.tavily_basic_search_credits
