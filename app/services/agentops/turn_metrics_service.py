import uuid

from sqlalchemy import update

from app.models.agentops import AgentTurn
from app.services.agentops.session import agentops_session


async def start_turn(
    turn_id: uuid.UUID,
    startup_id: uuid.UUID,
    session_id: uuid.UUID | None,
    stage: str,
) -> None:
    async with agentops_session() as session:
        session.add(
            AgentTurn(
                id=turn_id,
                startup_id=startup_id,
                session_id=session_id,
                stage=stage,
                tool_call_count=0,
                status="pending",
                latency_ms=0,
            )
        )
        await session.commit()


async def finish_turn(
    turn_id: uuid.UUID,
    status: str,
    latency_ms: int,
    tool_call_count: int,
) -> None:
    async with agentops_session() as session:
        result = await session.execute(
            update(AgentTurn)
            .where(AgentTurn.id == turn_id)
            .values(
                status=status,
                latency_ms=latency_ms,
                tool_call_count=tool_call_count,
            )
        )
        if result.rowcount != 1:
            await session.rollback()
            raise RuntimeError(f"Expected to finish exactly one agent_turns row, updated {result.rowcount}.")
        await session.commit()
