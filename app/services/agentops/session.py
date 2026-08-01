from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session_local


@asynccontextmanager
async def agentops_session() -> AsyncIterator[AsyncSession]:
    async with get_session_local()() as session:
        yield session
