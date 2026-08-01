import uuid

from app.models.agentops import ToolCallLog
from app.services.agentops.session import agentops_session


async def record_tool_call(
    *,
    turn_id: uuid.UUID,
    startup_id: uuid.UUID,
    tool_name: str,
    stage: str,
    latency_ms: int,
    status: str,
    error_type: str | None,
) -> None:
    async with agentops_session() as session:
        session.add(
            ToolCallLog(
                turn_id=turn_id,
                startup_id=startup_id,
                tool_name=tool_name,
                stage=stage,
                latency_ms=latency_ms,
                status=status,
                error_type=error_type,
            )
        )
        await session.commit()
