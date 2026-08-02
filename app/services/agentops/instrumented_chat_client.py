import logging
import time
import uuid
from decimal import Decimal
from typing import Any

from app.core.config import Settings
from app.llm.openrouter import ChatCompletionClient
from app.services.agentops.llm_metrics_service import record_llm_call
from app.services.agentops.pricing import get_cost

logger = logging.getLogger(__name__)


class InstrumentedChatClient:
    def __init__(
        self,
        *,
        wrapped: ChatCompletionClient,
        turn_id: uuid.UUID,
        startup_id: uuid.UUID,
        session_id: uuid.UUID | None,
        stage: str,
        settings: Settings,
    ) -> None:
        self._wrapped = wrapped
        self._turn_id = turn_id
        self._startup_id = startup_id
        self._session_id = session_id
        self._stage = stage
        self._settings = settings

    async def create_chat_completion(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
    ) -> Any:
        started_at = time.perf_counter()
        try:
            response = await self._wrapped.create_chat_completion(
                messages=messages,
                tools=tools,
                model=model,
            )
        except Exception as exc:
            latency_ms = _elapsed_ms(started_at)
            await self._record_call(
                model=model,
                prompt_tokens=None,
                completion_tokens=None,
                total_tokens=None,
                cost_usd=None,
                pricing_unknown=True,
                latency_ms=latency_ms,
                status="error",
                error_code=type(exc).__name__,
            )
            raise

        latency_ms = _elapsed_ms(started_at)
        prompt_tokens, completion_tokens, total_tokens = _usage_tokens(response)
        effective_model = (
            model
            or _get_optional(response, "model")
            or self._settings.llm_model
        )
        cost_usd, pricing_unknown = get_cost(
            str(effective_model),
            prompt_tokens,
            completion_tokens,
            settings=self._settings,
        )
        await self._record_call(
            model=str(effective_model),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_usd=cost_usd,
            pricing_unknown=pricing_unknown,
            latency_ms=latency_ms,
            status="success",
            error_code=None,
        )
        return response

    async def _record_call(
        self,
        *,
        model: str | None,
        prompt_tokens: int | None,
        completion_tokens: int | None,
        total_tokens: int | None,
        cost_usd: Decimal | None,
        pricing_unknown: bool,
        latency_ms: int,
        status: str,
        error_code: str | None,
    ) -> None:
        try:
            await record_llm_call(
                turn_id=self._turn_id,
                startup_id=self._startup_id,
                session_id=self._session_id,
                stage=self._stage,
                model=model or self._settings.llm_model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                cost_usd=cost_usd,
                pricing_unknown=pricing_unknown,
                latency_ms=latency_ms,
                status=status,
                error_code=error_code,
            )
        except Exception:
            logger.exception(
                "Failed to record AgentOps LLM call metrics "
                "turn_id=%s startup_id=%s session_id=%s stage=%s model=%s.",
                self._turn_id,
                self._startup_id,
                self._session_id,
                self._stage,
                model or self._settings.llm_model,
            )


def _elapsed_ms(started_at: float) -> int:
    return max(0, round((time.perf_counter() - started_at) * 1000))


def _usage_tokens(response: Any) -> tuple[int | None, int | None, int | None]:
    usage = _get_optional(response, "usage")
    if usage is None:
        return None, None, None
    return (
        _get_optional(usage, "prompt_tokens"),
        _get_optional(usage, "completion_tokens"),
        _get_optional(usage, "total_tokens"),
    )


def _get_optional(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)
