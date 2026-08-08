import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from testcontainers.community.postgres import PostgresContainer

import app.db.base  # noqa: F401
from app.api.dependencies import get_chat_client, get_chat_research_provider, get_research_provider
from app.core.config import Settings, get_settings
from app.core.security import create_access_token
from app.db import session as db_session
from app.db.session import get_db_session
from app.main import app
from app.models.base import Base
from app.models.chat import ChatSession
from app.models.agentops import AgentTurn
from app.models.research import ResearchCall
from app.models.startup import Startup
from app.models.user import User
from app.research.errors import ResearchProviderError
from app.research.schemas import (
    EvidenceAuthority,
    EvidenceRecord,
    ProviderExtractResponse,
    ProviderSearchResponse,
)


class FakeResearchProvider:
    def __init__(self, *, legal: bool = False, failure: Exception | None = None) -> None:
        self.legal = legal
        self.failure = failure
        self.search_calls = 0
        self.extract_calls = 0

    async def search(self, **kwargs):
        self.search_calls += 1
        return self._response(ProviderSearchResponse)

    async def extract(self, **kwargs):
        self.extract_calls += 1
        return self._response(ProviderExtractResponse)

    def _response(self, response_type):
        if self.failure:
            raise self.failure
        now = datetime.now(UTC)
        return response_type(
            evidence=[
                EvidenceRecord(
                    source_id="source-1",
                    url="https://example.com/source",
                    title="Source",
                    excerpt="Evidence",
                    retrieved_at=now,
                    authority=EvidenceAuthority.OFFICIAL
                    if self.legal
                    else EvidenceAuthority.UNKNOWN,
                    legal_or_regulatory=self.legal,
                )
            ],
            request_id="fake-request",
            credits_used=1,
            retrieved_at=now,
        )


@pytest.fixture(scope="module")
def postgres_url() -> AsyncIterator[str]:
    with PostgresContainer("postgres:16-alpine") as postgres:
        yield postgres.get_connection_url().replace(
            "postgresql+psycopg2://", "postgresql+asyncpg://", 1
        )


@pytest.fixture()
async def session_factory(postgres_url: str):
    engine = create_async_engine(postgres_url)
    async with engine.begin() as connection:
        await connection.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture()
async def client(session_factory, postgres_url, monkeypatch):
    provider = FakeResearchProvider()

    async def override_session():
        async with session_factory() as session:
            yield session

    monkeypatch.setenv("DATABASE_URL", postgres_url)
    monkeypatch.setenv("JWT_SECRET", "research-route-test-secret-with-at-least-thirty-two-bytes")
    get_settings.cache_clear()
    db_session._engine = None
    db_session._session_local = None
    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_research_provider] = lambda: provider
    app.dependency_overrides[get_chat_research_provider] = lambda: provider
    app.dependency_overrides[get_settings] = _settings
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http_client:
        http_client.provider = provider
        yield http_client
    app.dependency_overrides.clear()
    db_session._engine = None
    db_session._session_local = None
    get_settings.cache_clear()


async def _user(factory):
    async with factory() as s:
        user = User(name="u", email=f"{uuid.uuid4()}@example.com")
        s.add(user)
        await s.commit()
        return user.id


async def _startup(factory, user_id):
    async with factory() as s:
        startup = Startup(user_id=user_id, name="s")
        s.add(startup)
        await s.commit()
        return startup.id


def _headers(user_id):
    return {"Authorization": f"Bearer {create_access_token(user_id, settings=_settings())}"}


def _settings():
    return Settings(
        _env_file=None,
        DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/coaching",
        TAVILY_API_KEY="test",
        JWT_SECRET="research-route-test-secret-with-at-least-thirty-two-bytes",
        LLM_BASE_URL="http://localhost:20128/v1",
        LLM_MODEL="m",
        LLM_API_KEY="k",
    )


async def _research(client, startup_id, user_id, body):
    return await client.post(
        f"/startups/{startup_id}/research", json=body, headers=_headers(user_id)
    )


async def test_research_route_returns_404_for_non_owner(client, session_factory):
    owner, other = await _user(session_factory), await _user(session_factory)
    startup = await _startup(session_factory, owner)
    assert (await _research(client, startup, other, {"query": "market"})).status_code == 404


async def test_research_route_reuses_or_creates_chat_session_for_correlation(
    client, session_factory
):
    user = await _user(session_factory)
    startup = await _startup(session_factory, user)
    response = await _research(client, startup, user, {"query": "market"})
    assert response.status_code == 200
    async with session_factory() as s:
        session = (
            await s.execute(select(ChatSession).where(ChatSession.startup_id == startup))
        ).scalar_one()
    assert (
        await _research(client, startup, user, {"query": "other", "session_id": str(session.id)})
    ).status_code == 200


async def test_research_route_handles_direct_query_request(client, session_factory):
    user = await _user(session_factory)
    startup = await _startup(session_factory, user)
    response = await _research(client, startup, user, {"query": "market"})
    assert response.status_code == 200 and client.provider.search_calls == 1


async def test_research_route_handles_direct_url_extraction_request(client, session_factory):
    user = await _user(session_factory)
    startup = await _startup(session_factory, user)
    response = await _research(client, startup, user, {"urls": ["https://example.com"]})
    assert response.status_code == 200 and client.provider.extract_calls == 1


async def test_research_route_rejects_malformed_url_with_structured_error(client, session_factory):
    user = await _user(session_factory)
    startup = await _startup(session_factory, user)
    response = await _research(client, startup, user, {"urls": ["not-a-url"]})
    assert response.status_code == 422
    assert response.json()["detail"] == {
        "field": "urls.0",
        "code": "research_request_invalid",
        "message": "Input should be a valid URL, relative URL without a base",
    }


async def test_research_route_includes_legal_notice_when_evidence_is_legal_or_regulatory(
    client, session_factory
):
    client.provider.legal = True
    user = await _user(session_factory)
    startup = await _startup(session_factory, user)
    response = await _research(
        client, startup, user, {"query": "law", "category": "legal", "jurisdiction": "Vietnam"}
    )
    assert response.status_code == 200 and response.json()["legal_notice"]


async def test_research_route_second_identical_request_is_a_cache_hit_and_skips_provider_call(
    client, session_factory
):
    user = await _user(session_factory)
    startup = await _startup(session_factory, user)
    await _research(client, startup, user, {"query": "market"})
    response = await _research(client, startup, user, {"query": "market"})
    assert response.json()["cache_hit"] is True and client.provider.search_calls == 1


async def test_research_route_maps_rate_limit_to_429_with_structured_detail(
    client, session_factory, monkeypatch
):
    from app.services.research_quota_service import ResearchQuotaService

    async def limited(self, **kwargs):
        from app.services.research_errors import ResearchErrorDetail, ResearchServiceError

        raise ResearchServiceError(
            ResearchErrorDetail("research", "research_rate_limited", "Limited")
        )

    monkeypatch.setattr(ResearchQuotaService, "reserve", limited)
    user = await _user(session_factory)
    startup = await _startup(session_factory, user)
    response = await _research(client, startup, user, {"query": "market"})
    assert (
        response.status_code == 429 and response.json()["detail"]["code"] == "research_rate_limited"
    )


async def test_research_route_maps_provider_failure_to_structured_error_not_raw_exception(
    client, session_factory
):
    client.provider.failure = ResearchProviderError("provider_timeout")
    user = await _user(session_factory)
    startup = await _startup(session_factory, user)
    response = await _research(client, startup, user, {"query": "market"})
    assert response.status_code == 503 and response.json()["detail"]["code"] == "provider_timeout"


async def test_research_route_does_not_mutate_stage_or_document_state(client, session_factory):
    user = await _user(session_factory)
    startup = await _startup(session_factory, user)
    await _research(client, startup, user, {"query": "market"})
    async with session_factory() as s:
        assert (await s.get(Startup, startup)).current_stage == "idea"


async def test_research_route_records_exactly_one_research_call_row_with_null_turn_id(
    client, session_factory
):
    user = await _user(session_factory)
    startup = await _startup(session_factory, user)
    await _research(client, startup, user, {"query": "market"})
    async with session_factory() as s:
        calls = (
            (await s.execute(select(ResearchCall).where(ResearchCall.startup_id == startup)))
            .scalars()
            .all()
        )
    assert len(calls) == 1 and calls[0].turn_id is None


async def test_chat_route_research_call_still_gets_a_real_turn_id(client, session_factory):
    class Chat:
        def __init__(self):
            self.calls = 0

        async def create_chat_completion(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return {
                    "choices": [
                        {
                            "message": {
                                "content": None,
                                "tool_calls": [
                                    {
                                        "id": "research",
                                        "function": {
                                            "name": "research_web",
                                            "arguments": '{"query": "market"}',
                                        },
                                    }
                                ],
                            }
                        }
                    ]
                }
            return {"choices": [{"message": {"content": "Evidence [source-1].", "tool_calls": []}}]}

    app.dependency_overrides[get_chat_client] = lambda: Chat()
    user = await _user(session_factory)
    startup = await _startup(session_factory, user)
    response = await client.post(
        f"/startups/{startup}/chat", json={"message": "research"}, headers=_headers(user)
    )
    assert response.status_code == 200
    async with session_factory() as s:
        call = (
            await s.execute(select(ResearchCall).where(ResearchCall.startup_id == startup))
        ).scalar_one()
        turn = (
            await s.execute(select(AgentTurn).where(AgentTurn.startup_id == startup))
        ).scalar_one()
    assert call.turn_id is not None
    assert call.turn_id == turn.id


async def test_chat_route_accepts_later_turn_citation_from_same_session_research(
    client, session_factory
):
    class Chat:
        def __init__(self) -> None:
            self.responses = [
                {
                    "choices": [
                        {
                            "message": {
                                "content": None,
                                "tool_calls": [
                                    {
                                        "id": "research",
                                        "function": {
                                            "name": "research_web",
                                            "arguments": '{"query": "tutoring scheduling"}',
                                        },
                                    }
                                ],
                            }
                        }
                    ]
                },
                {"choices": [{"message": {"content": "Evidence [source-1].", "tool_calls": []}}]},
                {
                    "choices": [
                        {
                            "message": {
                                "content": None,
                                "tool_calls": [
                                    {
                                        "id": "canvas",
                                        "function": {
                                            "name": "generate_lean_canvas",
                                            "arguments": (
                                                '{"problem":"Manual scheduling","solution":"Automation",'
                                                '"unique_value_proposition":"Less admin",'
                                                '"customer_segments":"Tutoring centers"}'
                                            ),
                                        },
                                    }
                                ],
                            }
                        }
                    ]
                },
                {
                    "choices": [
                        {
                            "message": {
                                "content": "The canvas uses the scheduling evidence [source-1].",
                                "tool_calls": [],
                            }
                        }
                    ]
                },
            ]

        async def create_chat_completion(self, **kwargs):
            return self.responses.pop(0)

    chat_client = Chat()
    app.dependency_overrides[get_chat_client] = lambda: chat_client
    user = await _user(session_factory)
    startup = await _startup(session_factory, user)
    first = await client.post(
        f"/startups/{startup}/chat", json={"message": "Research scheduling."}, headers=_headers(user)
    )
    assert first.status_code == 200

    async with session_factory() as session:
        startup_row = await session.get(Startup, startup)
        assert startup_row is not None
        startup_row.current_stage = "lean_canvas"
        await session.commit()

    second = await client.post(
        f"/startups/{startup}/chat",
        json={"message": "Draft the Lean Canvas using that research.", "session_id": first.json()["session_id"]},
        headers=_headers(user),
    )

    assert second.status_code == 200
    assert second.json()["message"] == "The canvas uses the scheduling evidence [source-1]."
