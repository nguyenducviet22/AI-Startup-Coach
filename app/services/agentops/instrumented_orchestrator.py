import logging
import time
import uuid
from typing import Any

from app.services.agentops.turn_metrics_service import finish_turn, start_turn
from app.services.context_builder import StartupContext
from app.services.orchestrator import AgentOrchestrator, OrchestratorResult

logger = logging.getLogger(__name__)


class InstrumentedAgentOrchestrator:
    def __init__(
        self,
        *,
        wrapped: AgentOrchestrator,
        turn_id: uuid.UUID,
        startup_id: uuid.UUID,
        session_id: uuid.UUID | None,
        stage: str,
    ) -> None:
        self._wrapped = wrapped
        self._turn_id = turn_id
        self._startup_id = startup_id
        self._session_id = session_id
        self._stage = stage

    async def handle_turn(
        self,
        *,
        startup: StartupContext,
        history: list[dict[str, Any]],
        user_message: str,
        current_document: Any | None = None,
    ) -> OrchestratorResult:
        await self._start_turn()
        started_at = time.perf_counter()
        try:
            result = await self._wrapped.handle_turn(
                startup=startup,
                history=history,
                user_message=user_message,
                current_document=current_document,
            )
        except Exception:
            latency_ms = _elapsed_ms(started_at)
            await self._finish_turn(status="error", latency_ms=latency_ms, tool_call_count=0)
            raise

        latency_ms = _elapsed_ms(started_at)
        await self._finish_turn(
            status="success",
            latency_ms=latency_ms,
            tool_call_count=len(result.tool_call_data),
        )
        return result

    async def _start_turn(self) -> None:
        try:
            await start_turn(
                turn_id=self._turn_id,
                startup_id=self._startup_id,
                session_id=self._session_id,
                stage=self._stage,
            )
        except Exception:
            logger.exception(
                "Failed to record AgentOps turn start metrics "
                "turn_id=%s startup_id=%s session_id=%s stage=%s.",
                self._turn_id,
                self._startup_id,
                self._session_id,
                self._stage,
            )

    async def _finish_turn(self, *, status: str, latency_ms: int, tool_call_count: int) -> None:
        try:
            await finish_turn(
                turn_id=self._turn_id,
                status=status,
                latency_ms=latency_ms,
                tool_call_count=tool_call_count,
            )
        except Exception:
            logger.exception(
                "Failed to record AgentOps turn finish metrics "
                "turn_id=%s startup_id=%s session_id=%s stage=%s.",
                self._turn_id,
                self._startup_id,
                self._session_id,
                self._stage,
            )


def _elapsed_ms(started_at: float) -> int:
    return max(0, round((time.perf_counter() - started_at) * 1000))
