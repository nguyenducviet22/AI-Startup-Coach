from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings


_engine: AsyncEngine | None = None
_session_local: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine

    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    return _engine


def get_session_local() -> async_sessionmaker[AsyncSession]:
    global _session_local

    if _session_local is None:
        _session_local = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _session_local


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with get_session_local()() as session:
        yield session
