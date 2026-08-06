import asyncio
import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.community.postgres import PostgresContainer

import app.db.base  # noqa: F401
from app.core.config import Settings
from app.models.base import Base
from app.models.chat import ChatSession
from app.models.research import ResearchQuotaReservation
from app.models.startup import Startup
from app.models.user import User
from app.services.research_errors import ResearchServiceError
from app.services.research_quota_service import ResearchQuotaService, _advisory_key


@pytest.fixture(scope="module")
def postgres_url() -> AsyncIterator[str]:
    with PostgresContainer("postgres:16-alpine") as postgres:
        yield _asyncpg_url(postgres.get_connection_url())


@pytest.fixture()
async def session_factory(postgres_url: str) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(postgres_url, pool_pre_ping=True)
    async with engine.begin() as connection:
        await connection.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def test_concurrent_user_reservations_overlap_and_only_one_consumes_final_unit(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await _user_id(session_factory)
    settings = _settings(RESEARCH_USER_HOURLY_CALL_LIMIT=1)
    async with session_factory() as held_lock_session:
        await held_lock_session.execute(
            text("SELECT pg_advisory_xact_lock(:key)"), {"key": _advisory_key(user_id)}
        )
        entered = [asyncio.Event(), asyncio.Event()]

        async def reserve(index: int):
            async with session_factory() as task_session:
                entered[index].set()
                return await ResearchQuotaService(task_session, settings).reserve(
                    user_id=user_id, session_id=None, credits=1
                )

        first = asyncio.create_task(reserve(0))
        second = asyncio.create_task(reserve(1))
        await asyncio.wait_for(entered[0].wait(), timeout=5)
        await asyncio.wait_for(entered[1].wait(), timeout=5)
        await asyncio.sleep(0.1)
        assert not first.done()
        assert not second.done()
        await held_lock_session.commit()

    outcomes = await asyncio.wait_for(asyncio.gather(first, second, return_exceptions=True), timeout=10)
    assert len([outcome for outcome in outcomes if isinstance(outcome, ResearchQuotaReservation)]) == 1
    errors = [outcome for outcome in outcomes if isinstance(outcome, ResearchServiceError)]
    assert len(errors) == 1
    assert errors[0].detail.code == "research_rate_limited"
    assert errors[0].detail.scope == "user"
    assert errors[0].detail.retry_at is not None


async def test_session_limit_releases_failed_provider_reservation(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id, session_id = await _session_owner(session_factory)
    settings = _settings(RESEARCH_SESSION_HOURLY_CALL_LIMIT=1)
    async with session_factory() as held_lock_session:
        await held_lock_session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _advisory_key(session_id)})
        entered = [asyncio.Event(), asyncio.Event()]
        async def reserve(index: int):
            async with session_factory() as task_session:
                entered[index].set()
                return await ResearchQuotaService(task_session, settings).reserve(user_id=user_id, session_id=session_id, credits=1)
        first, second = asyncio.create_task(reserve(0)), asyncio.create_task(reserve(1))
        await asyncio.wait_for(entered[0].wait(), timeout=5); await asyncio.wait_for(entered[1].wait(), timeout=5)
        await asyncio.sleep(0.1); assert not first.done() and not second.done()
        await held_lock_session.commit()
    outcomes = await asyncio.wait_for(asyncio.gather(first, second, return_exceptions=True), timeout=10)
    assert len([outcome for outcome in outcomes if isinstance(outcome, ResearchQuotaReservation)]) == 1
    assert [outcome.detail.scope for outcome in outcomes if isinstance(outcome, ResearchServiceError)] == ["session"]


async def _user_id(session_factory: async_sessionmaker[AsyncSession]) -> uuid.UUID:
    async with session_factory() as session:
        user = User(name="Research User", email=f"{uuid.uuid4()}@example.com")
        session.add(user)
        await session.commit()
        return user.id


async def _session_owner(session_factory: async_sessionmaker[AsyncSession]) -> tuple[uuid.UUID, uuid.UUID]:
    async with session_factory() as session:
        user = User(name="Session User", email=f"{uuid.uuid4()}@example.com")
        session.add(user); await session.flush()
        startup = Startup(user_id=user.id, name="Research startup")
        session.add(startup); await session.flush()
        chat = ChatSession(startup_id=startup.id)
        session.add(chat); await session.commit()
        return user.id, chat.id


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "_env_file": None,
        "JWT_SECRET": "research-quota-test-secret-with-at-least-thirty-two-bytes",
        "LLM_BASE_URL": "http://localhost:20128/v1",
        "LLM_MODEL": "proxy-model",
        "LLM_API_KEY": "proxy-key",
        "RESEARCH_SESSION_HOURLY_CALL_LIMIT": 8,
        "RESEARCH_SESSION_DAILY_CREDIT_LIMIT": 20,
        "RESEARCH_USER_HOURLY_CALL_LIMIT": 20,
        "RESEARCH_USER_DAILY_CREDIT_LIMIT": 60,
    }
    values.update(overrides)
    return Settings(**values)


def _asyncpg_url(url: str) -> str:
    if url.startswith("postgresql+psycopg2://"):
        return url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
    return url.replace("postgresql://", "postgresql+asyncpg://", 1)
