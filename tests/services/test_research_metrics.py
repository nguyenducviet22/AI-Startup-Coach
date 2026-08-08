from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.community.postgres import PostgresContainer

import app.db.base  # noqa: F401
from app.db import session as db_session
from app.models.agentops import AgentTurn
from app.models.base import Base
from app.models.chat import ChatSession
from app.models.research import ResearchCall
from app.models.startup import Startup
from app.models.user import User
from app.research.schemas import EvidenceAuthority, EvidenceRecord, ResearchResult
from app.services.agentops.instrumented_research_service import InstrumentedResearchService
from app.services.agentops.pricing import get_research_cost
from app.services.agentops.research_metrics_service import record_research_call
from app.services.research_errors import ResearchErrorDetail, ResearchServiceError
from app.services.research_service import ResearchAccountingOutcome, ResearchOwnerContext, ResearchServiceResult
from app.research.schemas import ResearchRequest


@pytest.fixture()
async def metrics_session_factory() -> async_sessionmaker[AsyncSession]:
    with PostgresContainer("postgres:16-alpine") as postgres:
        url = postgres.get_connection_url().replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url)
        async with engine.begin() as connection:
            await connection.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
            await connection.run_sync(Base.metadata.drop_all)
            await connection.run_sync(Base.metadata.create_all)

        previous_engine = db_session._engine
        previous_session_local = db_session._session_local
        db_session._engine = engine
        db_session._session_local = async_sessionmaker(engine, expire_on_commit=False)
        try:
            yield db_session._session_local
        finally:
            db_session._engine = previous_engine
            db_session._session_local = previous_session_local
            await engine.dispose()


class FakeMetricsSession:
    def __init__(self) -> None:
        self.records: list[ResearchCall] = []
        self.commits = 0

    def add(self, record: ResearchCall) -> None:
        self.records.append(record)

    async def commit(self) -> None:
        self.commits += 1


class FakeResearchService:
    def __init__(self, outcome: ResearchServiceResult | Exception) -> None:
        self.outcome = outcome
        self.settings = SimpleNamespace(
            research_provider="tavily",
            research_pricing_enabled=True,
            tavily_basic_search_credits=1,
            tavily_advanced_search_credits=2,
            tavily_extract_credits_per_five_urls=1,
        )

    async def execute(self, **kwargs) -> ResearchServiceResult:
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def _outcome(*, cache_hit: bool = False) -> ResearchServiceResult:
    now = datetime(2026, 8, 6, tzinfo=UTC)
    return ResearchServiceResult(
        result=ResearchResult(
            evidence=[EvidenceRecord(source_id="s", url="https://example.com", title="T", excerpt="E", retrieved_at=now, authority=EvidenceAuthority.UNKNOWN, legal_or_regulatory=False)],
            cache_hit=cache_hit,
            retrieved_at=now,
            served_at=now,
        ),
        accounting=ResearchAccountingOutcome(
            provider="fake", operation="search", query_fingerprint="fingerprint", provider_call_made=not cache_hit,
            cache_hit=cache_hit, credits_reserved=None if cache_hit else 1, credits_charged=0 if cache_hit else 1,
            provider_request_id="provider-request",
        ),
    )


async def test_record_research_call_uses_isolated_session_and_commits(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.services.agentops.research_metrics_service as metrics

    session = FakeMetricsSession()

    @asynccontextmanager
    async def fake_agentops_session():
        yield session

    monkeypatch.setattr(metrics, "agentops_session", fake_agentops_session)
    turn_id = uuid.uuid4()
    await record_research_call(
        turn_id=turn_id, startup_id=uuid.uuid4(), user_id=uuid.uuid4(), session_id=uuid.uuid4(), stage="idea",
        provider="fake", operation="search", category="general", query_fingerprint="fingerprint", provider_request_id="provider-request",
        cache_hit=False, provider_call_made=True, credits_reserved=1, credits_charged=1, cost_usd=None,
        pricing_unknown=True, latency_ms=2, status="success", error_code=None,
    )

    assert session.commits == 1
    assert session.records[0].turn_id == turn_id
    assert session.records[0].sequence is None


async def test_instrumented_research_records_cache_hit_once_with_exact_turn_id(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.services.agentops.instrumented_research_service as instrumentation

    records: list[dict] = []

    async def record(**kwargs) -> None:
        records.append(kwargs)

    monkeypatch.setattr(instrumentation, "record_research_call", record)
    turn_id = uuid.uuid4()
    startup_id = uuid.uuid4()
    user_id = uuid.uuid4()
    service = InstrumentedResearchService(
        wrapped=FakeResearchService(_outcome(cache_hit=True)),  # type: ignore[arg-type]
        turn_id=turn_id, startup_id=startup_id, user_id=user_id, session_id=None, stage="idea",
    )
    returned = await service.execute(
        owner=ResearchOwnerContext(startup_id=startup_id, user_id=user_id), request=ResearchRequest(query="market")
    )

    assert returned == _outcome(cache_hit=True)
    assert len(records) == 1
    assert records[0]["turn_id"] == turn_id
    assert records[0]["cache_hit"] is True
    assert records[0]["provider_call_made"] is False
    assert records[0]["credits_charged"] == 0
    assert records[0]["cost_usd"] == Decimal("0.000000")
    assert records[0]["pricing_unknown"] is False


async def test_instrumented_research_records_actual_tavily_credit_cost(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.services.agentops.instrumented_research_service as instrumentation

    records: list[dict] = []

    async def record(**kwargs) -> None:
        records.append(kwargs)

    monkeypatch.setattr(instrumentation, "record_research_call", record)
    startup_id = uuid.uuid4()
    service = InstrumentedResearchService(
        wrapped=FakeResearchService(_outcome()),  # type: ignore[arg-type]
        turn_id=uuid.uuid4(),
        startup_id=startup_id,
        user_id=uuid.uuid4(),
        session_id=None,
        stage="idea",
    )

    await service.execute(
        owner=ResearchOwnerContext(startup_id=startup_id, user_id=uuid.uuid4()),
        request=ResearchRequest(query="market"),
    )

    assert records[0]["cost_usd"] == Decimal("0.008000")
    assert records[0]["pricing_unknown"] is False


async def test_instrumented_research_persists_cache_hit_with_identity_sequence(
    metrics_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with metrics_session_factory() as owner_session:
        user = User(name="Research founder", email=f"{uuid.uuid4()}@example.com")
        owner_session.add(user)
        await owner_session.flush()
        startup = Startup(user_id=user.id, name="Research startup")
        owner_session.add(startup)
        await owner_session.flush()
        chat_session = ChatSession(startup_id=startup.id)
        owner_session.add(chat_session)
        await owner_session.flush()
        turn_id = uuid.uuid4()
        owner_session.add(
            AgentTurn(
                id=turn_id,
                startup_id=startup.id,
                session_id=chat_session.id,
                stage="idea",
                tool_call_count=1,
                status="success",
                latency_ms=1,
            )
        )
        await owner_session.commit()

    service = InstrumentedResearchService(
        wrapped=FakeResearchService(_outcome(cache_hit=True)),  # type: ignore[arg-type]
        turn_id=turn_id,
        startup_id=startup.id,
        user_id=user.id,
        session_id=chat_session.id,
        stage="idea",
    )
    await service.execute(
        owner=ResearchOwnerContext(startup_id=startup.id, user_id=user.id, session_id=chat_session.id),
        request=ResearchRequest(query="market"),
    )

    async with metrics_session_factory() as verification_session:
        call = (await verification_session.execute(select(ResearchCall))).scalar_one()

    assert call.turn_id == turn_id
    assert call.sequence > 0
    assert call.cache_hit is True
    assert call.provider_call_made is False
    assert call.credits_charged == 0


async def test_instrumented_research_preserves_structured_failure_when_metrics_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.services.agentops.instrumented_research_service as instrumentation

    async def telemetry_failure(**kwargs) -> None:
        raise RuntimeError("metrics unavailable")

    monkeypatch.setattr(instrumentation, "record_research_call", telemetry_failure)
    error = ResearchServiceError(ResearchErrorDetail("research", "provider_unavailable", "Try again."))
    service = InstrumentedResearchService(
        wrapped=FakeResearchService(error),  # type: ignore[arg-type]
        turn_id=uuid.uuid4(), startup_id=uuid.uuid4(), user_id=uuid.uuid4(), session_id=uuid.uuid4(), stage="idea",
    )

    with pytest.raises(ResearchServiceError) as raised:
        await service.execute(
            owner=ResearchOwnerContext(startup_id=uuid.uuid4(), user_id=uuid.uuid4()), request=ResearchRequest(query="market")
        )

    assert raised.value is error


async def test_instrumented_research_records_structured_failure_once(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.services.agentops.instrumented_research_service as instrumentation

    records: list[dict] = []

    async def record(**kwargs) -> None:
        records.append(kwargs)

    monkeypatch.setattr(instrumentation, "record_research_call", record)
    startup_id = uuid.uuid4()
    user_id = uuid.uuid4()
    service = InstrumentedResearchService(
        wrapped=FakeResearchService(
            ResearchServiceError(ResearchErrorDetail("research", "provider_timeout", "Timed out."))
        ),  # type: ignore[arg-type]
        turn_id=uuid.uuid4(), startup_id=startup_id, user_id=user_id, session_id=None, stage="idea",
    )

    with pytest.raises(ResearchServiceError):
        await service.execute(
            owner=ResearchOwnerContext(startup_id=startup_id, user_id=user_id), request=ResearchRequest(query="market")
        )

    assert len(records) == 1
    assert records[0]["status"] == "error"
    assert records[0]["error_code"] == "provider_timeout"
    assert records[0]["provider_call_made"] is True


def test_tavily_research_pricing_uses_actual_credit_usage() -> None:
    settings = SimpleNamespace(
        research_pricing_enabled=True,
        tavily_basic_search_credits=1,
        tavily_advanced_search_credits=2,
        tavily_extract_credits_per_five_urls=1,
    )

    assert get_research_cost("search_basic", 1, settings=settings) == (Decimal("0.008000"), False)
    assert get_research_cost("search_advanced", 2, settings=settings) == (
        Decimal("0.016000"),
        False,
    )
    assert get_research_cost("extract", 2, extract_url_count=6, settings=settings) == (
        Decimal("0.016000"),
        False,
    )


def test_tavily_research_pricing_is_explicitly_unknown_when_disabled_or_unrecognized() -> None:
    disabled_settings = SimpleNamespace(
        research_pricing_enabled=False,
        tavily_basic_search_credits=1,
        tavily_advanced_search_credits=2,
        tavily_extract_credits_per_five_urls=1,
    )
    enabled_settings = SimpleNamespace(
        research_pricing_enabled=True,
        tavily_basic_search_credits=1,
        tavily_advanced_search_credits=2,
        tavily_extract_credits_per_five_urls=1,
    )

    assert get_research_cost("search_basic", 1, settings=disabled_settings) == (None, True)
    assert get_research_cost("unknown_operation", 1, settings=enabled_settings) == (None, True)
