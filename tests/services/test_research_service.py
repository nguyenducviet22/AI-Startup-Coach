import uuid
from datetime import UTC, datetime

import pytest
import inspect
from collections.abc import AsyncIterator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.community.postgres import PostgresContainer
import app.db.base  # noqa: F401
from app.models.base import Base
from app.models.user import User
from app.models.startup import Startup

from app.core.config import Settings
from app.research.errors import ResearchProviderError
from app.research.schemas import EvidenceAuthority, EvidenceRecord, ProviderSearchResponse, ResearchCategory, ResearchRequest
from app.services.research_service import ResearchOwnerContext, ResearchService
from app.services.research_errors import ResearchServiceError

@pytest.fixture(scope="module")
def postgres_url() -> AsyncIterator[str]:
    with PostgresContainer("postgres:16-alpine") as p: yield p.get_connection_url().replace("postgresql+psycopg2://", "postgresql+asyncpg://")
@pytest.fixture()
async def session_factory(postgres_url):
    e=create_async_engine(postgres_url)
    async with e.begin() as c: await c.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto")); await c.run_sync(Base.metadata.drop_all); await c.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(e,expire_on_commit=False); await e.dispose()


class FakeProvider:
    def __init__(self, outcome: ProviderSearchResponse | Exception) -> None:
        self.outcome = outcome
        self.search_calls = 0
        self.extract_calls = 0

    async def search(self, **kwargs):
        self.search_calls += 1
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome

    async def extract(self, **kwargs):
        self.extract_calls += 1
        if isinstance(self.outcome, Exception): raise self.outcome
        return self.outcome


async def test_legal_request_requires_jurisdiction_before_provider_or_persistence() -> None:
    provider = FakeProvider(_provider_response())
    service = ResearchService(None, provider, _settings(), quota_service=_NoQuota(), cache_service=_NoCache())  # type: ignore[arg-type]
    with pytest.raises(ResearchServiceError) as exc_info:
        await service.execute(
            owner=ResearchOwnerContext(startup_id=uuid.uuid4(), user_id=uuid.uuid4()),
            request=ResearchRequest(query="licensing", category=ResearchCategory.LEGAL),
        )
    assert exc_info.value.detail.code == "research_jurisdiction_required"
    assert provider.search_calls == 0


async def test_provider_failure_releases_reservation_and_is_structured() -> None:
    quota = _NoQuota()
    provider = FakeProvider(ResearchProviderError("provider_timeout"))
    service = ResearchService(None, provider, _settings(), quota_service=quota, cache_service=_NoCache())  # type: ignore[arg-type]
    with pytest.raises(ResearchServiceError) as exc_info:
        await service.execute(
            owner=ResearchOwnerContext(startup_id=uuid.uuid4(), user_id=uuid.uuid4()),
            request=ResearchRequest(query="market"),
        )
    assert exc_info.value.detail.code == "provider_timeout"
    assert quota.reconciliations == [(None, False)]


async def test_success_cache_force_refresh_and_extract_use_shared_result_contract() -> None:
    owner = ResearchOwnerContext(startup_id=uuid.uuid4(), user_id=uuid.uuid4())
    cached = _provider_response()
    cache = _NoCache(cached_result=None)
    quota = _NoQuota(); provider = FakeProvider(_provider_response())
    service = ResearchService(None, provider, _settings(), quota_service=quota, cache_service=cache)  # type: ignore[arg-type]
    success = await service.execute(owner=owner, request=ResearchRequest(query="market"))
    assert success.accounting.credits_charged == 1 and success.accounting.cost_usd is None and success.accounting.pricing_unknown and quota.reconciliations == [(1, True)]
    cache.cached_result = success.result
    hit = await service.execute(owner=owner, request=ResearchRequest(query="market"))
    assert hit.result.cache_hit is True and provider.search_calls == 1 and quota.reserve_calls == 1
    refreshed = await service.execute(owner=owner, request=ResearchRequest(query="market", force_refresh=True))
    assert refreshed.accounting.provider_call_made is True and provider.search_calls == 2 and quota.reserve_calls == 2
    extracted = await service.execute(
        owner=owner,
        request=ResearchRequest(
            query="market",
            urls=["https://example.com"],
            force_refresh=True,
        ),
    )
    assert provider.extract_calls == 1 and extracted.result.evidence[0].source_id == "source"
    source = inspect.getsource(ResearchService)
    assert "StageService" not in source and "DocumentService" not in source and "research_calls" not in source


async def test_url_only_request_uses_canonical_url_for_cache_key_and_query_fingerprint() -> None:
    import hashlib

    owner = ResearchOwnerContext(startup_id=uuid.uuid4(), user_id=uuid.uuid4())
    quota = _NoQuota()
    cache = _NoCache()
    provider = FakeProvider(_provider_response())
    service = ResearchService(None, provider, _settings(), quota_service=quota, cache_service=cache)  # type: ignore[arg-type]

    outcome = await service.execute(
        owner=owner,
        request=ResearchRequest(urls=["https://EXAMPLE.com/founder-source"]),
    )

    canonical_url = "https://example.com/founder-source"
    assert provider.extract_calls == 1
    assert cache.key_arguments[0]["query_or_url"] == canonical_url
    assert outcome.accounting.query_fingerprint == hashlib.sha256(canonical_url.encode("utf-8")).hexdigest()


def test_research_request_rejects_neither_query_nor_extraction_url() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="Provide a non-empty query or at least one extraction URL"):
        ResearchRequest()

async def test_real_session_spy_records_only_research_tables(session_factory) -> None:
    async with session_factory() as seed:
        user=User(name="u",email=f"{uuid.uuid4()}@x.com"); seed.add(user); await seed.flush(); startup=Startup(user_id=user.id,name="s"); seed.add(startup); await seed.commit()
    async with session_factory() as raw:
        spy=_SessionSpy(raw); service=ResearchService(spy, FakeProvider(_provider_response()), _settings())
        await service.execute(owner=ResearchOwnerContext(startup_id=startup.id,user_id=user.id),request=ResearchRequest(query="market"))
        touched=" ".join(spy.sql).lower()
        assert "ResearchQuotaReservation" in spy.models and "research_cache_entries" in touched
        for forbidden in ("startups","lean_canvas","bmc","swot","product_plan","marketing_strategy","funding_guide"):
            assert forbidden not in touched

class _SessionSpy:
    def __init__(self, session): self._session=session; self.sql=[]; self.models=[]
    async def execute(self, statement, *args, **kwargs): self.sql.append(str(statement)); return await self._session.execute(statement,*args,**kwargs)
    def add(self, instance, *args, **kwargs): self.models.append(type(instance).__name__); return self._session.add(instance,*args,**kwargs)
    def __getattr__(self, name): return getattr(self._session,name)


class _NoQuota:
    def __init__(self) -> None:
        self.reconciliations: list[tuple[int | None, bool]] = []
        self.reservation = type("Reservation", (), {"reserved_credits": 1})()
        self.reserve_calls = 0

    async def reserve(self, **kwargs):
        self.reserve_calls += 1
        return self.reservation

    async def reconcile(self, *, credits_charged, provider_succeeded, **kwargs):
        self.reconciliations.append((credits_charged, provider_succeeded))


class _NoCache:
    def __init__(self, cached_result=None) -> None: self.cached_result = cached_result; self.key_arguments = []
    async def get(self, **kwargs):
        if self.cached_result is None: return None
        return self.cached_result.model_copy(update={"cache_hit": True})

    def build_key(self, **kwargs):
        self.key_arguments.append(kwargs)
        return "cache-key"

    async def put(self, **kwargs):
        return None


def _provider_response() -> ProviderSearchResponse:
    now = datetime.now(UTC)
    return ProviderSearchResponse(
        evidence=[EvidenceRecord(source_id="source", url="https://example.com", title="Title", excerpt="Text", retrieved_at=now, published_at=None, authority=EvidenceAuthority.UNKNOWN, legal_or_regulatory=False)],
        request_id="request", credits_used=1, retrieved_at=now,
    )


def _settings() -> Settings:
    return Settings(_env_file=None, JWT_SECRET="service-test-secret-with-at-least-thirty-two-bytes", LLM_BASE_URL="http://localhost:20128/v1", LLM_MODEL="proxy-model", LLM_API_KEY="proxy-key")
