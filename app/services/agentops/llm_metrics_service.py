import uuid
from decimal import Decimal

from app.models.agentops import LlmCall
from app.services.agentops.session import agentops_session


async def record_llm_call(
    *,
    turn_id: uuid.UUID,
    startup_id: uuid.UUID,
    session_id: uuid.UUID | None,
    stage: str,
    model: str,
    prompt_tokens: int | None,
    completion_tokens: int | None,
    total_tokens: int | None,
    cost_usd: Decimal | None,
    pricing_unknown: bool,
    latency_ms: int,
    status: str,
    error_code: str | None,
) -> None:
    async with agentops_session() as session:
        session.add(
            LlmCall(
                turn_id=turn_id,
                startup_id=startup_id,
                session_id=session_id,
                stage=stage,
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                cost_usd=cost_usd,
                pricing_unknown=pricing_unknown,
                latency_ms=latency_ms,
                status=status,
                error_code=error_code,
            )
        )
        await session.commit()
