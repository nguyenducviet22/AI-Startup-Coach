"""Best-effort persistence for provider-neutral research telemetry."""

import uuid
from decimal import Decimal

from app.models.research import ResearchCall
from app.services.agentops.session import agentops_session


async def record_research_call(
    *,
    turn_id: uuid.UUID | None,
    startup_id: uuid.UUID,
    user_id: uuid.UUID,
    session_id: uuid.UUID | None,
    stage: str,
    provider: str,
    operation: str,
    category: str,
    query_fingerprint: str,
    provider_request_id: str | None,
    cache_hit: bool,
    provider_call_made: bool,
    credits_reserved: int | None,
    credits_charged: int | None,
    cost_usd: Decimal | None,
    pricing_unknown: bool,
    latency_ms: int,
    status: str,
    error_code: str | None,
) -> None:
    async with agentops_session() as session:
        session.add(
            ResearchCall(
                turn_id=turn_id,
                startup_id=startup_id,
                user_id=user_id,
                session_id=session_id,
                stage=stage,
                provider=provider,
                operation=operation,
                category=category,
                query_fingerprint=query_fingerprint,
                provider_request_id=provider_request_id,
                cache_hit=cache_hit,
                provider_call_made=provider_call_made,
                credits_reserved=credits_reserved,
                credits_charged=credits_charged,
                cost_usd=cost_usd,
                pricing_unknown=pricing_unknown,
                latency_ms=latency_ms,
                status=status,
                error_code=error_code,
            )
        )
        await session.commit()
