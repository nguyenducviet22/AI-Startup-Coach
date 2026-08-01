import logging
import time
import uuid
from typing import Any

from app.services.agentops.tool_metrics_service import record_tool_call
from app.services.tool_dispatcher import ToolDispatcher

logger = logging.getLogger(__name__)


class InstrumentedToolDispatcher:
    def __init__(
        self,
        *,
        wrapped: ToolDispatcher,
        turn_id: uuid.UUID,
        startup_id: uuid.UUID,
        stage: str,
    ) -> None:
        self._wrapped = wrapped
        self._turn_id = turn_id
        self._startup_id = startup_id
        self._stage = stage

    async def execute(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any] | str,
        current_stage: str,
        startup_id: uuid.UUID | str | None = None,
    ) -> dict[str, Any]:
        started_at = time.perf_counter()
        try:
            result = await self._wrapped.execute(
                tool_name=tool_name,
                arguments=arguments,
                current_stage=current_stage,
                startup_id=startup_id,
            )
        except Exception as exc:
            latency_ms = _elapsed_ms(started_at)
            await self._record_call(
                tool_name=tool_name,
                stage=current_stage,
                latency_ms=latency_ms,
                status="error",
                error_type=type(exc).__name__,
            )
            raise

        latency_ms = _elapsed_ms(started_at)
        status, error_type = _status_from_result(result)
        await self._record_call(
            tool_name=tool_name,
            stage=current_stage,
            latency_ms=latency_ms,
            status=status,
            error_type=error_type,
        )
        return result

    async def _record_call(
        self,
        *,
        tool_name: str,
        stage: str,
        latency_ms: int,
        status: str,
        error_type: str | None,
    ) -> None:
        try:
            await record_tool_call(
                turn_id=self._turn_id,
                startup_id=self._startup_id,
                tool_name=tool_name,
                stage=stage,
                latency_ms=latency_ms,
                status=status,
                error_type=error_type,
            )
        except Exception:
            logger.exception(
                "Failed to record AgentOps tool call metrics "
                "turn_id=%s startup_id=%s stage=%s tool_name=%s.",
                self._turn_id,
                self._startup_id,
                stage,
                tool_name,
            )


def _status_from_result(result: dict[str, Any]) -> tuple[str, str | None]:
    if result.get("ok") is True:
        return "ok", None

    error = result.get("error")
    error_type = error.get("type") if isinstance(error, dict) else None
    if error_type == "tool_validation_error":
        return "validation_error", error_type
    if error_type == "tool_not_available_for_stage":
        return "not_allowed", error_type
    if error_type == "tool_persistence_error":
        return "persistence_error", error_type
    return "error", error_type


def _elapsed_ms(started_at: float) -> int:
    return max(0, round((time.perf_counter() - started_at) * 1000))
