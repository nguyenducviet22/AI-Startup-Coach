import uuid
from datetime import UTC, datetime, timedelta
from collections.abc import AsyncIterator
import asyncio
import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.community.postgres import PostgresContainer
import app.db.base  # noqa: F401
from app.models.base import Base
from app.models.user import User
from app.models.startup import Startup
from app.models.research import ResearchCacheEntry

from app.core.config import Settings
from app.research.schemas import EvidenceAuthority, EvidenceRecord, ResearchCategory, ResearchResult
from app.services.research_cache_service import ResearchCacheService

@pytest.fixture(scope="module")
def postgres_url() -> AsyncIterator[str]:
    with PostgresContainer("postgres:16-alpine") as postgres: yield postgres.get_connection_url().replace("postgresql+psycopg2://", "postgresql+asyncpg://")

@pytest.fixture()
async def session_factory(postgres_url: str):
    engine = create_async_engine(postgres_url)
    async with engine.begin() as c:
        await c.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto")); await c.run_sync(Base.metadata.drop_all); await c.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


def test_cache_key_is_sensitive_to_every_versioned_component() -> None:
    base = _key_args()
    baseline = ResearchCacheService.build_key(**base)
    for field, replacement in {
        "startup_id": uuid.uuid4(), "provider": "other", "operation": "extract",
        "query_or_url": "another query", "locale": "vi-VN", "topic": "news",
        "start_date": "2026-08-01", "end_date": "2026-08-02", "domains": ["example.org"],
        "max_results": 4, "depth": "advanced", "authority_mode": "strict", "legal_mode": True,
    }.items():
        changed = {**base, field: replacement}
        assert ResearchCacheService.build_key(**changed) != baseline


def test_cache_key_is_startup_scoped() -> None:
    base = _key_args()
    first = ResearchCacheService.build_key(**base)
    second = ResearchCacheService.build_key(**{**base, "startup_id": uuid.uuid4()})
    assert first != second


def test_cache_ttls_come_from_settings_by_category() -> None:
    service = ResearchCacheService(None, _settings())  # type: ignore[arg-type]
    assert service._ttl(ResearchCategory.GENERAL) == timedelta(seconds=601)
    assert service._ttl(ResearchCategory.NEWS) == timedelta(seconds=602)
    assert service._ttl(ResearchCategory.PRICING) == timedelta(seconds=603)
    assert service._ttl(ResearchCategory.LEGAL) == timedelta(seconds=604)

async def test_cached_hit_preserves_retrieval_and_write_ttl(session_factory) -> None:
    startup_id = await _startup(session_factory); written = datetime(2026, 8, 6, tzinfo=UTC); read = written + timedelta(seconds=10)
    async with session_factory() as session:
        service = ResearchCacheService(session, _settings()); result = _result(written)
        await service.put(startup_id=startup_id, cache_key="key", operation="search", category=ResearchCategory.GENERAL, result=result, now=written)
        row = await session.scalar(select(ResearchCacheEntry)); assert row.expires_at == written + timedelta(seconds=601)
        hit = await service.get(startup_id=startup_id, cache_key="key", served_at=read)
        assert hit is not None and hit.retrieved_at == written and hit.served_at == read and hit.cache_hit

async def test_expired_entry_is_miss_and_concurrent_upsert_is_atomic(session_factory) -> None:
    startup_id = await _startup(session_factory); then = datetime(2026, 8, 6, tzinfo=UTC)
    async with session_factory() as session:
        s = ResearchCacheService(session, _settings()); await s.put(startup_id=startup_id, cache_key="key", operation="search", category=ResearchCategory.NEWS, result=_result(then), now=then)
        assert await s.get(startup_id=startup_id, cache_key="key", served_at=then + timedelta(seconds=603)) is None
    entered=[asyncio.Event(),asyncio.Event()]
    async def put(i):
        async with session_factory() as session:
            entered[i].set(); await asyncio.gather(*[event.wait() for event in entered])
            await ResearchCacheService(session,_settings()).put(startup_id=startup_id, cache_key="same", operation="search", category=ResearchCategory.GENERAL, result=_result(then+timedelta(seconds=i)), now=then)
    await asyncio.gather(asyncio.create_task(put(0)),asyncio.create_task(put(1)))
    async with session_factory() as session:
        assert len((await session.execute(select(ResearchCacheEntry).where(ResearchCacheEntry.cache_key=="same"))).scalars().all()) == 1

async def _startup(factory):
    async with factory() as s:
        u=User(name="u",email=f"{uuid.uuid4()}@x.com"); s.add(u); await s.flush(); x=Startup(user_id=u.id,name="x"); s.add(x); await s.commit(); return x.id

def _result(now):
    return ResearchResult(evidence=[EvidenceRecord(source_id="s",url="https://example.com",title="t",excerpt="e",retrieved_at=now,authority=EvidenceAuthority.UNKNOWN,legal_or_regulatory=False)],retrieved_at=now,served_at=now)


def _key_args() -> dict[str, object]:
    return {
        "startup_id": uuid.UUID("00000000-0000-0000-0000-000000000001"), "provider": "provider",
        "operation": "search", "query_or_url": "A query", "locale": "en-US", "topic": "general",
        "start_date": None, "end_date": None, "domains": ["example.com"], "max_results": 5,
        "depth": "basic", "authority_mode": "standard", "legal_mode": False,
    }


def _settings() -> Settings:
    return Settings(
        _env_file=None, JWT_SECRET="cache-test-secret-with-at-least-thirty-two-bytes",
        LLM_BASE_URL="http://localhost:20128/v1", LLM_MODEL="proxy-model", LLM_API_KEY="proxy-key",
        RESEARCH_CACHE_TTL_GENERAL_SECONDS=601, RESEARCH_CACHE_TTL_NEWS_SECONDS=602,
        RESEARCH_CACHE_TTL_PRICING_SECONDS=603, RESEARCH_CACHE_TTL_LEGAL_SECONDS=604,
    )
