"""Best-effort AgentOps composition around the shared research use case."""

import hashlib
import logging
import time
import uuid

from app.research.schemas import ResearchRequest
from app.services.agentops.pricing import get_research_cost
from app.services.agentops.research_metrics_service import record_research_call
from app.services.research_errors import PROVIDER_ATTEMPT_ERROR_CODES, ResearchServiceError
from app.services.research_service import (
    ResearchOwnerContext,
    ResearchService,
    ResearchServiceResult,
)


logger = logging.getLogger(__name__)


class InstrumentedResearchService:
    def __init__(
        self,
        *,
        wrapped: ResearchService,
        turn_id: uuid.UUID | None,
        startup_id: uuid.UUID,
        user_id: uuid.UUID,
        session_id: uuid.UUID | None,
        stage: str,
    ) -> None:
        self._wrapped = wrapped
        self._turn_id = turn_id
        self._startup_id = startup_id
        self._user_id = user_id
        self._session_id = session_id
        self._stage = stage

    async def execute(
        self,
        *,
        owner: ResearchOwnerContext,
        request: ResearchRequest,
        locale: str | None = None,
        authority_mode: str = "standard",
    ) -> ResearchServiceResult:
        started_at = time.perf_counter()
        try:
            outcome = await self._wrapped.execute(
                owner=owner,
                request=request,
                locale=locale,
                authority_mode=authority_mode,
            )
        except ResearchServiceError as exc:
            await self._record_failure(
                request=request,
                latency_ms=_elapsed_ms(started_at),
                error_code=exc.detail.code,
            )
            raise

        await self._record_success(
            request=request,
            outcome=outcome,
            latency_ms=_elapsed_ms(started_at),
        )
        return outcome

    async def _record_success(
        self,
        *,
        request: ResearchRequest,
        outcome: ResearchServiceResult,
        latency_ms: int,
    ) -> None:
        accounting = outcome.accounting
        cost_usd, pricing_unknown = get_research_cost(
            _pricing_operation(accounting.operation, request),
            accounting.credits_charged,
            extract_url_count=len(request.urls) if request.urls else None,
            settings=self._wrapped.settings,
        )
        await self._record(
            provider=accounting.provider,
            operation=accounting.operation,
            category=request.category.value,
            query_fingerprint=accounting.query_fingerprint,
            provider_request_id=accounting.provider_request_id,
            cache_hit=accounting.cache_hit,
            provider_call_made=accounting.provider_call_made,
            credits_reserved=accounting.credits_reserved,
            credits_charged=accounting.credits_charged,
            cost_usd=cost_usd,
            pricing_unknown=pricing_unknown,
            latency_ms=latency_ms,
            status="success",
            error_code=None,
        )

    async def _record_failure(
        self,
        *,
        request: ResearchRequest,
        latency_ms: int,
        error_code: str,
    ) -> None:
        extraction_urls = [str(url) for url in request.urls]
        subject = "|".join(extraction_urls) if extraction_urls else request.query
        assert subject is not None
        await self._record(
            provider=self._wrapped.settings.research_provider,
            operation="extract" if extraction_urls else "search",
            category=request.category.value,
            query_fingerprint=hashlib.sha256(subject.encode("utf-8")).hexdigest(),
            provider_request_id=None,
            cache_hit=False,
            provider_call_made=error_code in PROVIDER_ATTEMPT_ERROR_CODES,
            credits_reserved=None,
            credits_charged=0,
            cost_usd=None,
            pricing_unknown=True,
            latency_ms=latency_ms,
            status="error",
            error_code=error_code,
        )

    async def _record(self, **kwargs: object) -> None:
        try:
            await record_research_call(
                turn_id=self._turn_id,
                startup_id=self._startup_id,
                user_id=self._user_id,
                session_id=self._session_id,
                stage=self._stage,
                **kwargs,
            )
        except Exception:
            logger.exception(
                "Failed to record AgentOps research metrics turn_id=%s startup_id=%s.",
                self._turn_id,
                self._startup_id,
            )


def _elapsed_ms(started_at: float) -> int:
    return max(0, round((time.perf_counter() - started_at) * 1000))


def _pricing_operation(operation: str, request: ResearchRequest) -> str:
    if operation == "search":
        return f"search_{request.search_depth.value}"
    return operation
