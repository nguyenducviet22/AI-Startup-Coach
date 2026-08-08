import json
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.community.postgres import PostgresContainer

import app.db.base  # noqa: F401
from app.api.dependencies import get_chat_client
from app.api.routes import get_settings
from app.core.config import Settings
from app.core.security import create_access_token
from app.db import session as db_session
from app.db.session import get_db_session
from app.llm.openrouter import LLMProviderError
from app.models.agentops import AgentTurn, LlmCall, ToolCallLog
from app.main import app
from app.models.base import Base
from app.models.chat import ChatMessage, ChatSession
from app.models.documents import FundingGuide, LeanCanvas
from app.models.startup import Startup
from app.models.user import User


@pytest.fixture(scope="module")
def postgres_url() -> AsyncIterator[str]:
    with PostgresContainer("postgres:16-alpine") as postgres:
        yield _asyncpg_url(postgres.get_connection_url())


@pytest.fixture()
async def session_factory(
    postgres_url: str,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(postgres_url, pool_pre_ping=True)
    async with engine.begin() as connection:
        await connection.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)

    yield async_sessionmaker(engine, expire_on_commit=False)

    await engine.dispose()


@pytest.fixture()
async def client(
    session_factory: async_sessionmaker[AsyncSession],
    postgres_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[httpx.AsyncClient]:
    fake_chat_client = FakeChatClient()

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    monkeypatch.setenv("DATABASE_URL", postgres_url)
    monkeypatch.setenv("JWT_SECRET", "route-test-secret-with-at-least-thirty-two-bytes")
    get_settings.cache_clear()
    _reset_app_db_session()
    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_chat_client] = lambda: fake_chat_client
    app.dependency_overrides[get_settings] = lambda: _settings()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as test_client:
        test_client.fake_chat_client = fake_chat_client
        yield test_client

    app.dependency_overrides.clear()
    _reset_app_db_session()
    get_settings.cache_clear()


async def test_startup_routes_create_get_advance_and_set_stage(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await _create_user(session_factory)
    headers = _auth_headers(user_id)

    create_response = await client.post(
        "/startups",
        json={"name": "TutorOS"},
        headers=headers,
    )
    assert create_response.status_code == 201
    startup = create_response.json()
    assert startup["user_id"] == str(user_id)
    assert startup["current_stage"] == "idea"

    get_response = await client.get(f"/startups/{startup['id']}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "TutorOS"

    advance_response = await client.post(f"/startups/{startup['id']}/advance-stage", headers=headers)
    assert advance_response.status_code == 200
    assert advance_response.json()["current_stage"] == "lean_canvas"

    set_response = await client.patch(
        f"/startups/{startup['id']}/stage",
        json={"stage": "bmc"},
        headers=headers,
    )
    assert set_response.status_code == 200
    assert set_response.json()["current_stage"] == "bmc"


async def test_create_startup_rejects_token_for_missing_user(client: httpx.AsyncClient) -> None:
    missing_user_id = uuid.uuid4()
    response = await client.post(
        "/startups",
        json={"name": "Ghost startup"},
        headers=_auth_headers(missing_user_id),
    )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "invalid_token"


async def test_create_startup_derives_user_id_from_verified_token(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await _create_user(session_factory)

    response = await client.post(
        "/startups",
        json={"name": "TutorOS"},
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 201
    assert response.json()["user_id"] == str(user_id)


async def test_list_startups_returns_only_current_users_startups(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await _create_user(session_factory)
    other_user_id = await _create_user(session_factory)
    headers = _auth_headers(user_id)
    own_startup_id = (
        await client.post("/startups", json={"name": "TutorOS"}, headers=headers)
    ).json()["id"]
    other_startup_id = await _create_startup(
        session_factory,
        other_user_id,
        name="Other user's startup",
    )

    response = await client.get("/startups", headers=headers)

    assert response.status_code == 200
    startups = response.json()["startups"]
    assert [startup["id"] for startup in startups] == [own_startup_id]
    assert all(startup["user_id"] == str(user_id) for startup in startups)
    assert str(other_startup_id) not in response.text
    assert "Other user's startup" not in response.text


async def test_list_startups_orders_newest_first_with_id_tiebreaker(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await _create_user(session_factory)
    headers = _auth_headers(user_id)
    tied_created_at = datetime(2026, 7, 31, 12, 0, tzinfo=UTC)
    lower_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    higher_id = uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")

    async with session_factory() as session:
        session.add_all(
            [
                Startup(
                    id=lower_id,
                    user_id=user_id,
                    name="Lower id",
                    created_at=tied_created_at,
                ),
                Startup(
                    id=higher_id,
                    user_id=user_id,
                    name="Higher id",
                    created_at=tied_created_at,
                ),
            ]
        )
        await session.commit()

    response = await client.get("/startups", headers=headers)

    assert response.status_code == 200
    assert [startup["id"] for startup in response.json()["startups"]] == [
        str(higher_id),
        str(lower_id),
    ]


async def test_existing_routes_reject_invalid_access_token(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/startups",
        json={"name": "TutorOS"},
        headers={"Authorization": "Bearer not-a-jwt"},
    )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "invalid_token"


async def test_existing_routes_reject_expired_access_token(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await _create_user(session_factory)
    expired_token = create_access_token(
        user_id,
        settings=_settings(),
        now=datetime.now(UTC) - timedelta(minutes=31),
    )

    response = await client.post(
        "/startups",
        json={"name": "TutorOS"},
        headers={"Authorization": f"Bearer {expired_token}"},
    )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "expired_token"


async def test_chat_route_persists_messages_and_document_with_mocked_llm(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await _create_user(session_factory)
    headers = _auth_headers(user_id)
    startup_id = (
        await client.post("/startups", json={"name": "TutorOS"}, headers=headers)
    ).json()["id"]
    await client.post(f"/startups/{startup_id}/advance-stage", headers=headers)

    client.fake_chat_client.responses = [
        _response(
            None,
            tool_calls=[
                _tool_call(
                    "call-canvas",
                    "generate_lean_canvas",
                    {
                        "problem": "Tutors lose time coordinating lessons.",
                        "solution": "Scheduling automation.",
                        "unique_value_proposition": "Calendar ops for tutoring teams.",
                        "customer_segments": "Independent tutoring centers.",
                    },
                )
            ],
        ),
        _response("I drafted the lean canvas."),
    ]

    chat_response = await client.post(
        f"/startups/{startup_id}/chat",
        json={"message": "Draft the canvas."},
        headers=headers,
    )

    assert chat_response.status_code == 200
    chat_payload = chat_response.json()
    assert chat_payload["message"] == "I drafted the lean canvas."
    assert chat_payload["session_id"]
    assert chat_payload["stage_readiness"] is None

    document_response = await client.get(f"/startups/{startup_id}/documents/lean_canvas", headers=headers)
    assert document_response.status_code == 200
    document = document_response.json()
    assert document["version"] == 1
    assert document["content"]["problem"] == "Tutors lose time coordinating lessons."

    async with session_factory() as session:
        messages = (
            await session.execute(
                select(ChatMessage).where(ChatMessage.session_id == uuid.UUID(chat_payload["session_id"]))
                .order_by(ChatMessage.sequence)
            )
        ).scalars().all()
        turns = (await session.execute(select(AgentTurn))).scalars().all()
        llm_calls = (await session.execute(select(LlmCall).order_by(LlmCall.sequence))).scalars().all()
        tool_calls = (await session.execute(select(ToolCallLog))).scalars().all()

    assert [(message.role, message.content) for message in messages] == [
        ("user", "Draft the canvas."),
        ("tool", messages[1].content),
        ("assistant", "I drafted the lean canvas."),
    ]
    assert json.loads(messages[1].content)["persistence"]["status"] == "persisted"
    assert messages[1].tool_call_data == {"tool_call_id": "call-canvas"}
    assert messages[2].tool_call_data[0]["tool_name"] == "generate_lean_canvas"
    assert len(turns) == 1
    assert turns[0].startup_id == uuid.UUID(startup_id)
    assert turns[0].session_id == uuid.UUID(chat_payload["session_id"])
    assert turns[0].stage == "lean_canvas"
    assert turns[0].status == "success"
    assert turns[0].tool_call_count == 1
    assert len(llm_calls) == 2
    assert {llm_call.turn_id for llm_call in llm_calls} == {turns[0].id}
    assert [llm_call.status for llm_call in llm_calls] == ["success", "success"]
    assert len(tool_calls) == 1
    assert tool_calls[0].turn_id == turns[0].id
    assert tool_calls[0].tool_name == "generate_lean_canvas"
    assert tool_calls[0].status == "ok"

    client.fake_chat_client.responses = [_response("Let us refine the customer segment.")]
    followup_response = await client.post(
        f"/startups/{startup_id}/chat",
        json={"message": "What should I improve?"},
        headers=headers,
    )

    assert followup_response.status_code == 200
    replayed_roles = [
        message["role"]
        for message in client.fake_chat_client.requests[-1]["messages"]
        if message["role"] != "system"
    ]
    assert replayed_roles == ["user", "assistant", "user"]


async def test_chat_route_records_recovered_llm_error_as_successful_turn(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await _create_user(session_factory)
    headers = _auth_headers(user_id)
    startup_id = (
        await client.post("/startups", json={"name": "TutorOS"}, headers=headers)
    ).json()["id"]
    client.fake_chat_client.responses = [
        LLMProviderError(
            "provider down",
            "The AI coach is temporarily unavailable. Please try again in a moment.",
        )
    ]

    response = await client.post(
        f"/startups/{startup_id}/chat",
        json={"message": "Hello"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["message"] == "The AI coach is temporarily unavailable. Please try again in a moment."
    assert response.json()["stage_readiness"] is None

    async with session_factory() as session:
        turn = (await session.execute(select(AgentTurn))).scalar_one()
        llm_call = (await session.execute(select(LlmCall))).scalar_one()

    assert turn.status == "success"
    assert turn.tool_call_count == 0
    assert llm_call.turn_id == turn.id
    assert llm_call.status == "error"
    assert llm_call.error_code == "LLMProviderError"


async def test_chat_route_keeps_non_research_response_shape_unchanged(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await _create_user(session_factory)
    startup_id = await _create_startup(session_factory, user_id)
    client.fake_chat_client.responses = [_response("Let us clarify the problem first.")]

    response = await client.post(
        f"/startups/{startup_id}/chat",
        json={"message": "Help me shape the idea."},
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "session_id": payload["session_id"],
        "message": "Let us clarify the problem first.",
        "stage_readiness": None,
        "research": None,
    }


async def test_chat_route_records_escaped_exception_as_error_turn(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await _create_user(session_factory)
    headers = _auth_headers(user_id)
    startup_id = (
        await client.post("/startups", json={"name": "TutorOS"}, headers=headers)
    ).json()["id"]
    client.fake_chat_client.responses = [RuntimeError("unexpected failure")]

    with pytest.raises(RuntimeError, match="unexpected failure"):
        await client.post(
            f"/startups/{startup_id}/chat",
            json={"message": "Hello"},
            headers=headers,
        )

    async with session_factory() as session:
        turn = (await session.execute(select(AgentTurn))).scalar_one()
        llm_call = (await session.execute(select(LlmCall))).scalar_one()

    assert turn.status == "error"
    assert turn.tool_call_count == 0
    assert llm_call.turn_id == turn.id
    assert llm_call.status == "error"
    assert llm_call.error_code == "RuntimeError"


async def test_chat_route_succeeds_when_agentops_metrics_writes_fail(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def fail_metrics(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("metrics database unavailable")

    monkeypatch.setattr(
        "app.services.agentops.instrumented_chat_client.record_llm_call",
        fail_metrics,
    )
    monkeypatch.setattr(
        "app.services.agentops.instrumented_tool_dispatcher.record_tool_call",
        fail_metrics,
    )
    monkeypatch.setattr(
        "app.services.agentops.instrumented_orchestrator.start_turn",
        fail_metrics,
    )
    monkeypatch.setattr(
        "app.services.agentops.instrumented_orchestrator.finish_turn",
        fail_metrics,
    )
    user_id = await _create_user(session_factory)
    headers = _auth_headers(user_id)
    startup_id = (
        await client.post("/startups", json={"name": "TutorOS"}, headers=headers)
    ).json()["id"]
    client.fake_chat_client.responses = [
        _response(
            None,
            tool_calls=[
                _tool_call(
                    "call-readiness",
                    "check_stage_readiness",
                    {"current_stage": "idea", "ready": True, "missing_fields": []},
                )
            ],
        ),
        _response("You have enough to move forward."),
    ]

    response = await client.post(
        f"/startups/{startup_id}/chat",
        json={"message": "Are we ready?"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["message"] == "You have enough to move forward."
    assert response.json()["stage_readiness"] == {"ready": True, "missing_fields": []}


async def test_chat_route_reuses_latest_session_when_session_id_absent(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await _create_user(session_factory)
    headers = _auth_headers(user_id)
    startup_id = (
        await client.post("/startups", json={"name": "TutorOS"}, headers=headers)
    ).json()["id"]
    client.fake_chat_client.responses = [_response("First reply."), _response("Second reply.")]

    first = await client.post(
        f"/startups/{startup_id}/chat",
        json={"message": "Hello"},
        headers=headers,
    )
    second = await client.post(
        f"/startups/{startup_id}/chat",
        json={"message": "Again"},
        headers=headers,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["session_id"] == first.json()["session_id"]


async def test_chat_route_returns_null_stage_readiness_for_invalid_readiness_tool_call(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await _create_user(session_factory)
    headers = _auth_headers(user_id)
    startup_id = (
        await client.post("/startups", json={"name": "TutorOS"}, headers=headers)
    ).json()["id"]

    client.fake_chat_client.responses = [
        _response(
            None,
            tool_calls=[
                _tool_call(
                    "call-invalid-readiness",
                    "check_stage_readiness",
                    {
                        "current_stage": "not-a-stage",
                        "ready": True,
                        "missing_fields": [],
                    },
                )
            ],
        ),
        _response("I need to check that again."),
    ]

    response = await client.post(
        f"/startups/{startup_id}/chat",
        json={"message": "Are we ready?"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["message"] == "I need to check that again."
    assert response.json()["stage_readiness"] is None


async def test_chat_messages_route_returns_latest_session_messages_without_tool_rows(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await _create_user(session_factory)
    headers = _auth_headers(user_id)
    startup_id = (
        await client.post("/startups", json={"name": "TutorOS"}, headers=headers)
    ).json()["id"]
    await client.post(f"/startups/{startup_id}/advance-stage", headers=headers)

    client.fake_chat_client.responses = [
        _response(
            None,
            tool_calls=[
                _tool_call(
                    "call-canvas",
                    "generate_lean_canvas",
                    {
                        "problem": "Tutors lose time coordinating lessons.",
                        "solution": "Scheduling automation.",
                        "unique_value_proposition": "Calendar ops for tutoring teams.",
                        "customer_segments": "Independent tutoring centers.",
                    },
                )
            ],
        ),
        _response("I drafted the lean canvas."),
    ]
    chat_response = await client.post(
        f"/startups/{startup_id}/chat",
        json={"message": "Draft it."},
        headers=headers,
    )

    response = await client.get(f"/startups/{startup_id}/chat/messages", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == chat_response.json()["session_id"]
    assert [(message["role"], message["content"]) for message in payload["messages"]] == [
        ("user", "Draft it."),
        ("assistant", "I drafted the lean canvas."),
    ]
    assert [message["sequence"] for message in payload["messages"]] == sorted(
        message["sequence"] for message in payload["messages"]
    )
    assert all(message["created_at"] for message in payload["messages"])


async def test_chat_messages_route_uses_explicit_session_id_and_paginates_by_sequence(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await _create_user(session_factory)
    headers = _auth_headers(user_id)
    startup_id = (
        await client.post("/startups", json={"name": "TutorOS"}, headers=headers)
    ).json()["id"]
    client.fake_chat_client.responses = [
        _response("First reply."),
        _response("Second reply."),
        _response("Third reply."),
    ]

    first_chat = await client.post(
        f"/startups/{startup_id}/chat",
        json={"message": "First"},
        headers=headers,
    )
    session_id = first_chat.json()["session_id"]
    await client.post(
        f"/startups/{startup_id}/chat",
        json={"message": "Second", "session_id": session_id},
        headers=headers,
    )
    await client.post(
        f"/startups/{startup_id}/chat",
        json={"message": "Third", "session_id": session_id},
        headers=headers,
    )

    latest_page = (
        await client.get(
            f"/startups/{startup_id}/chat/messages",
            params={"session_id": session_id, "limit": 2},
            headers=headers,
        )
    ).json()["messages"]

    assert [message["content"] for message in latest_page] == ["Third", "Third reply."]

    older_page_response = await client.get(
        f"/startups/{startup_id}/chat/messages",
        params={
            "session_id": session_id,
            "limit": 2,
            "before_sequence": latest_page[0]["sequence"],
        },
        headers=headers,
    )

    assert older_page_response.status_code == 200
    assert [message["content"] for message in older_page_response.json()["messages"]] == [
        "Second",
        "Second reply.",
    ]


async def test_chat_messages_route_returns_empty_without_creating_session(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await _create_user(session_factory)
    headers = _auth_headers(user_id)
    startup_id = (
        await client.post("/startups", json={"name": "TutorOS"}, headers=headers)
    ).json()["id"]

    response = await client.get(f"/startups/{startup_id}/chat/messages", headers=headers)

    assert response.status_code == 200
    assert response.json() == {"session_id": None, "messages": []}
    async with session_factory() as session:
        session_count = (
            await session.execute(
                select(ChatSession).where(ChatSession.startup_id == uuid.UUID(startup_id))
            )
        ).scalars().all()
    assert session_count == []


async def test_chat_messages_route_rejects_session_id_from_different_startup(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await _create_user(session_factory)
    headers = _auth_headers(user_id)
    first_startup_id = (
        await client.post("/startups", json={"name": "TutorOS"}, headers=headers)
    ).json()["id"]
    second_startup_id = (
        await client.post("/startups", json={"name": "MarketOS"}, headers=headers)
    ).json()["id"]
    secret_message = "Sensitive message from the other startup."
    client.fake_chat_client.responses = [_response(secret_message)]
    other_chat = await client.post(
        f"/startups/{second_startup_id}/chat",
        json={"message": "Private second-startup context."},
        headers=headers,
    )

    response = await client.get(
        f"/startups/{first_startup_id}/chat/messages",
        params={"session_id": other_chat.json()["session_id"]},
        headers=headers,
    )

    assert response.status_code == 404
    assert secret_message not in response.text
    assert "Private second-startup context." not in response.text


async def test_document_routes_reject_unknown_doc_type(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await _create_user(session_factory)
    headers = _auth_headers(user_id)
    startup_id = (
        await client.post("/startups", json={"name": "TutorOS"}, headers=headers)
    ).json()["id"]

    response = await client.get(f"/startups/{startup_id}/documents/not_a_doc", headers=headers)

    assert response.status_code == 400
    assert "Unknown document type" in response.json()["detail"]


async def test_local_profile_startup_and_rename_work_without_auth(client: httpx.AsyncClient) -> None:
    initial_profile = await client.get("/profile")
    assert initial_profile.status_code == 200
    assert initial_profile.json() == {"name": "", "configured": False}

    updated_profile = await client.put("/profile", json={"name": "Nguyễn Thị Nhã Uyên"})
    assert updated_profile.status_code == 200
    assert updated_profile.json() == {"name": "Nguyễn Thị Nhã Uyên", "configured": True}

    created = await client.post("/startups", json={"name": "Startup chưa đặt tên"})
    assert created.status_code == 201
    startup_id = created.json()["id"]

    renamed = await client.patch(f"/startups/{startup_id}", json={"name": "EcoLearn"})
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "EcoLearn"

    listed = await client.get("/startups")
    assert listed.status_code == 200
    assert listed.json()["startups"][0]["name"] == "EcoLearn"


async def test_product_depth_routes_restore_overview_report_and_pitch_without_auth(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    startup_id = uuid.UUID((await client.post("/startups", json={"name": "EcoLearn"})).json()["id"])
    async with session_factory() as session:
        session.add_all([
            LeanCanvas(startup_id=startup_id, version=1, is_current=False, problem="Old problem", solution="Old solution", customer_segments="Students"),
            LeanCanvas(startup_id=startup_id, version=2, is_current=True, problem="Current problem", solution="Current solution", customer_segments="First-year students", revenue_streams="49k/month", cost_structure="Hosting"),
            FundingGuide(startup_id=startup_id, version=1, is_current=True, pitch_outline=[{"slide_title": "Vấn đề", "content": "Sinh viên khó duy trì lịch học."}], funding_stage_recommendation="Bootstrapped MVP"),
        ])
        await session.commit()

    overview = await client.get(f"/startups/{startup_id}/overview")
    assert overview.status_code == 200
    assert overview.json()["completed_documents"] == 2
    assert overview.json()["total_versions"] == 3

    report = await client.get(f"/startups/{startup_id}/report")
    assert report.status_code == 200
    sections = {section["key"]: section for section in report.json()["sections"]}
    assert sections["overview"]["content"]["problem"] == "Current problem"
    assert sections["basic_finance"]["available"] is True

    report_pdf = await client.get(f"/startups/{startup_id}/report/export", params={"format": "pdf", "sections": "overview,basic_finance"})
    assert report_pdf.status_code == 200
    assert report_pdf.content.startswith(b"%PDF-")

    pitch_pdf = await client.get(f"/startups/{startup_id}/pitch-deck/export", params={"format": "pdf"})
    assert pitch_pdf.status_code == 200
    assert pitch_pdf.content.startswith(b"%PDF-")

    restored = await client.post(f"/startups/{startup_id}/documents/lean_canvas/versions/1/restore")
    assert restored.status_code == 200
    assert restored.json()["version"] == 3
    assert restored.json()["content"]["problem"] == "Old problem"
    history = (await client.get(f"/startups/{startup_id}/documents/lean_canvas/history")).json()["documents"]
    assert [item["is_current"] for item in history] == [True, False, False]


@pytest.mark.parametrize(
    ("method", "path", "json_body"),
    [
        ("GET", "/startups/{startup_id}", None),
        ("POST", "/startups/{startup_id}/chat", {"message": "Hello"}),
        ("GET", "/startups/{startup_id}/chat/messages", None),
        ("GET", "/startups/{startup_id}/documents/lean_canvas", None),
        ("GET", "/startups/{startup_id}/documents/lean_canvas/history", None),
        ("POST", "/startups/{startup_id}/advance-stage", None),
        ("PATCH", "/startups/{startup_id}/stage", {"stage": "bmc"}),
    ],
)
async def test_startup_scoped_routes_return_404_for_non_owner(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    method: str,
    path: str,
    json_body: dict[str, Any] | None,
) -> None:
    owner_id = await _create_user(session_factory)
    other_user_id = await _create_user(session_factory)
    startup_id = await _create_startup(session_factory, owner_id)

    response = await client.request(
        method,
        path.format(startup_id=startup_id),
        json=json_body,
        headers=_auth_headers(other_user_id),
    )

    assert response.status_code == 404


async def test_end_to_end_idea_to_lean_canvas_to_bmc_requires_explicit_stage_advancement(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await _create_user(session_factory)
    headers = _auth_headers(user_id)
    startup = (
        await client.post(
            "/startups",
            json={"name": "TutorOS"},
            headers=headers,
        )
    ).json()
    startup_id = startup["id"]

    assert startup["current_stage"] == "idea"

    client.fake_chat_client.responses = [
        _response(
            None,
            tool_calls=[
                _tool_call(
                    "call-idea-ready",
                    "check_stage_readiness",
                    {
                        "current_stage": "idea",
                        "ready": True,
                        "missing_fields": [],
                    },
                )
            ],
        ),
        _response("The idea is ready to move forward."),
    ]
    idea_chat = await client.post(
        f"/startups/{startup_id}/chat",
        json={"message": "Are we ready for lean canvas?"},
        headers=headers,
    )

    assert idea_chat.status_code == 200
    assert idea_chat.json()["stage_readiness"] == {"ready": True, "missing_fields": []}
    assert (await client.get(f"/startups/{startup_id}", headers=headers)).json()["current_stage"] == "idea"

    advance_to_lean = await client.post(f"/startups/{startup_id}/advance-stage", headers=headers)
    assert advance_to_lean.status_code == 200
    assert advance_to_lean.json()["current_stage"] == "lean_canvas"

    client.fake_chat_client.responses = [
        _response(
            None,
            tool_calls=[
                _tool_call(
                    "call-canvas-v1",
                    "generate_lean_canvas",
                    {
                        "problem": "Tutors lose hours coordinating lessons.",
                        "solution": "Automated scheduling and reminders.",
                        "unique_value_proposition": "Calendar ops for tutoring teams.",
                        "customer_segments": "Independent tutoring centers.",
                    },
                )
            ],
        ),
        _response("I drafted the first lean canvas."),
    ]
    first_canvas_chat = await client.post(
        f"/startups/{startup_id}/chat",
        json={"message": "Draft the lean canvas."},
        headers=headers,
    )

    assert first_canvas_chat.status_code == 200
    current_canvas = (await client.get(f"/startups/{startup_id}/documents/lean_canvas", headers=headers)).json()
    assert current_canvas["version"] == 1
    assert current_canvas["is_current"] is True
    assert current_canvas["content"]["problem"] == "Tutors lose hours coordinating lessons."


    client.fake_chat_client.responses = [
        _response(
            None,
            tool_calls=[
                _tool_call(
                    "call-canvas-v2",
                    "generate_lean_canvas",
                    {
                        "problem": "Tutoring teams miss revenue due to manual scheduling.",
                        "solution": "Automated scheduling, reminders, and roster visibility.",
                        "unique_value_proposition": "Operations cockpit for tutoring centers.",
                        "customer_segments": "Multi-location tutoring centers.",
                        "channels": "Owner communities and tutoring associations.",
                    },
                ),
                _tool_call(
                    "call-lean-ready",
                    "check_stage_readiness",
                    {
                        "current_stage": "lean_canvas",
                        "ready": True,
                        "missing_fields": [],
                    },
                ),
            ],
        ),
        _response("I updated the canvas and it is ready for BMC."),
    ]
    second_canvas_chat = await client.post(
        f"/startups/{startup_id}/chat",
        json={"message": "Refine the canvas and check readiness."},
        headers=headers,
    )

    assert second_canvas_chat.status_code == 200
    assert second_canvas_chat.json()["stage_readiness"] == {"ready": True, "missing_fields": []}
    assert (await client.get(f"/startups/{startup_id}", headers=headers)).json()["current_stage"] == "lean_canvas"

    canvas_history = (
        await client.get(f"/startups/{startup_id}/documents/lean_canvas/history", headers=headers)
    ).json()["documents"]
    assert [document["version"] for document in canvas_history] == [2, 1]
    assert [document["is_current"] for document in canvas_history] == [True, False]
    assert canvas_history[0]["content"]["problem"] == (
        "Tutoring teams miss revenue due to manual scheduling."
    )
    assert canvas_history[1]["content"]["problem"] == "Tutors lose hours coordinating lessons."

    advance_to_bmc = await client.post(f"/startups/{startup_id}/advance-stage", headers=headers)
    assert advance_to_bmc.status_code == 200
    assert advance_to_bmc.json()["current_stage"] == "bmc"

    client.fake_chat_client.responses = [
        _response(
            None,
            tool_calls=[
                _tool_call(
                    "call-bmc-v1",
                    "generate_bmc",
                    {
                        "customer_segments": "Multi-location tutoring centers.",
                        "value_propositions": "Lower admin load and fewer missed sessions.",
                        "key_partners": "Tutoring software communities.",
                        "channels": "Founder-led sales and partner webinars.",
                        "revenue_streams": "Monthly subscription per location.",
                    },
                )
            ],
        ),
        _response("I drafted the business model canvas."),
    ]
    bmc_chat = await client.post(
        f"/startups/{startup_id}/chat",
        json={"message": "Create the BMC."},
        headers=headers,
    )

    assert bmc_chat.status_code == 200
    bmc_document = (await client.get(f"/startups/{startup_id}/documents/bmc", headers=headers)).json()
    assert bmc_document["version"] == 1
    assert bmc_document["is_current"] is True
    assert bmc_document["content"]["customer_segments"] == "Multi-location tutoring centers."
    assert bmc_document["content"]["value_propositions"] == (
        "Lower admin load and fewer missed sessions."
    )


async def test_chat_route_succeeds_without_research_configuration_when_no_research_tool_is_called(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    from app.main import app

    app.dependency_overrides[get_settings] = lambda: _settings(
        TAVILY_API_KEY="",
        RESEARCH_ENABLED=False,
    )
    user_id = await _create_user(session_factory)
    startup_id = await _create_startup(session_factory, user_id)
    client.fake_chat_client.responses = [_response("Normal coaching response.")]

    response = await client.post(
        f"/startups/{startup_id}/chat",
        json={"message": "Help me sharpen my idea."},
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Normal coaching response."


async def _create_user(session_factory: async_sessionmaker[AsyncSession]) -> uuid.UUID:
    async with session_factory() as session:
        user = User(name="Route Test User", email=f"{uuid.uuid4()}@example.com")
        session.add(user)
        await session.commit()
        return user.id


async def _create_startup(
    session_factory: async_sessionmaker[AsyncSession],
    user_id: uuid.UUID,
    name: str = "TutorOS",
) -> uuid.UUID:
    async with session_factory() as session:
        startup = Startup(user_id=user_id, name=name)
        session.add(startup)
        await session.commit()
        return startup.id


class FakeChatClient:
    def __init__(self) -> None:
        self.responses: list[Any] = []
        self.requests: list[dict[str, Any]] = []

    async def create_chat_completion(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
    ) -> Any:
        self.requests.append({"messages": messages, "tools": tools, "model": model})
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _response(content: str | None, tool_calls: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": content,
                    "tool_calls": tool_calls,
                }
            }
        ]
    }


def _tool_call(call_id: str, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": call_id,
        "type": "function",
        "function": {
            "name": name,
            "arguments": json.dumps(arguments),
        },
    }


def _auth_headers(user_id: uuid.UUID) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {create_access_token(user_id, settings=_settings())}",
    }


def _settings(**overrides: object) -> Settings:
    values = {
        "DATABASE_URL": "postgresql+asyncpg://postgres:postgres@localhost:5432/coaching",
        "OPENROUTER_API_KEY": "test-key",
        "OPENROUTER_BASE_URL": "https://openrouter.test/api/v1",
        "OPENROUTER_MODEL": "test-model",
        "OPENROUTER_HTTP_REFERER": "http://localhost:8000",
        "OPENROUTER_X_TITLE": "AI Startup Coach",
        "CHAT_HISTORY_LIMIT": 20,
        "LLM_MAX_RETRIES": 2,
        "LLM_RETRY_BACKOFF_SECONDS": 0,
        "TAVILY_API_KEY": "test-research-key",
        "JWT_SECRET": "route-test-secret-with-at-least-thirty-two-bytes",
        "JWT_ALGORITHM": "HS256",
        "ACCESS_TOKEN_EXPIRE_MINUTES": 30,
        "REFRESH_TOKEN_EXPIRE_DAYS": 7,
    }
    values.update(overrides)
    return Settings(**values)


def _asyncpg_url(url: str) -> str:
    if url.startswith("postgresql+psycopg2://"):
        return url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def _reset_app_db_session() -> None:
    db_session._engine = None
    db_session._session_local = None
