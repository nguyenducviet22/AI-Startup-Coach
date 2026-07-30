import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.community.postgres import PostgresContainer

import app.db.base  # noqa: F401
from app.api.dependencies import get_chat_client
from app.db.session import get_db_session
from app.main import app
from app.models.base import Base
from app.models.chat import ChatMessage
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
) -> AsyncIterator[httpx.AsyncClient]:
    fake_chat_client = FakeChatClient()

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_chat_client] = lambda: fake_chat_client

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as test_client:
        test_client.fake_chat_client = fake_chat_client
        yield test_client

    app.dependency_overrides.clear()


async def test_startup_routes_create_get_advance_and_set_stage(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await _create_user(session_factory)

    create_response = await client.post(
        "/startups",
        json={"user_id": str(user_id), "name": "TutorOS"},
    )
    assert create_response.status_code == 201
    startup = create_response.json()
    assert startup["user_id"] == str(user_id)
    assert startup["current_stage"] == "idea"

    get_response = await client.get(f"/startups/{startup['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "TutorOS"

    advance_response = await client.post(f"/startups/{startup['id']}/advance-stage")
    assert advance_response.status_code == 200
    assert advance_response.json()["current_stage"] == "lean_canvas"

    set_response = await client.patch(
        f"/startups/{startup['id']}/stage",
        json={"stage": "bmc"},
    )
    assert set_response.status_code == 200
    assert set_response.json()["current_stage"] == "bmc"


async def test_create_startup_rejects_missing_user(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/startups",
        json={"user_id": str(uuid.uuid4()), "name": "Ghost startup"},
    )

    assert response.status_code == 404
    assert "User" in response.json()["detail"]


async def test_chat_route_persists_messages_and_document_with_mocked_llm(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await _create_user(session_factory)
    startup_id = (
        await client.post("/startups", json={"user_id": str(user_id), "name": "TutorOS"})
    ).json()["id"]
    await client.post(f"/startups/{startup_id}/advance-stage")

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
        json={"user_id": str(user_id), "message": "Draft the canvas."},
    )

    assert chat_response.status_code == 200
    chat_payload = chat_response.json()
    assert chat_payload["message"] == "I drafted the lean canvas."
    assert chat_payload["session_id"]

    document_response = await client.get(f"/startups/{startup_id}/documents/lean_canvas")
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

    assert [(message.role, message.content) for message in messages] == [
        ("user", "Draft the canvas."),
        ("tool", messages[1].content),
        ("assistant", "I drafted the lean canvas."),
    ]
    assert json.loads(messages[1].content)["persistence"]["status"] == "persisted"
    assert messages[1].tool_call_data == {"tool_call_id": "call-canvas"}
    assert messages[2].tool_call_data[0]["tool_name"] == "generate_lean_canvas"

    client.fake_chat_client.responses = [_response("Let us refine the customer segment.")]
    followup_response = await client.post(
        f"/startups/{startup_id}/chat",
        json={"user_id": str(user_id), "message": "What should I improve?"},
    )

    assert followup_response.status_code == 200
    replayed_roles = [
        message["role"]
        for message in client.fake_chat_client.requests[-1]["messages"]
        if message["role"] != "system"
    ]
    assert replayed_roles == ["user", "assistant", "user"]


async def test_chat_route_reuses_latest_session_when_session_id_absent(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await _create_user(session_factory)
    startup_id = (
        await client.post("/startups", json={"user_id": str(user_id), "name": "TutorOS"})
    ).json()["id"]
    client.fake_chat_client.responses = [_response("First reply."), _response("Second reply.")]

    first = await client.post(
        f"/startups/{startup_id}/chat",
        json={"user_id": str(user_id), "message": "Hello"},
    )
    second = await client.post(
        f"/startups/{startup_id}/chat",
        json={"user_id": str(user_id), "message": "Again"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["session_id"] == first.json()["session_id"]


async def test_document_routes_reject_unknown_doc_type(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await _create_user(session_factory)
    startup_id = (
        await client.post("/startups", json={"user_id": str(user_id), "name": "TutorOS"})
    ).json()["id"]

    response = await client.get(f"/startups/{startup_id}/documents/not_a_doc")

    assert response.status_code == 400
    assert "Unknown document type" in response.json()["detail"]


async def test_end_to_end_idea_to_lean_canvas_to_bmc_requires_explicit_stage_advancement(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await _create_user(session_factory)
    startup = (
        await client.post(
            "/startups",
            json={"user_id": str(user_id), "name": "TutorOS"},
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
        json={"user_id": str(user_id), "message": "Are we ready for lean canvas?"},
    )

    assert idea_chat.status_code == 200
    assert (await client.get(f"/startups/{startup_id}")).json()["current_stage"] == "idea"

    advance_to_lean = await client.post(f"/startups/{startup_id}/advance-stage")
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
        json={"user_id": str(user_id), "message": "Draft the lean canvas."},
    )

    assert first_canvas_chat.status_code == 200
    current_canvas = (await client.get(f"/startups/{startup_id}/documents/lean_canvas")).json()
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
        json={"user_id": str(user_id), "message": "Refine the canvas and check readiness."},
    )

    assert second_canvas_chat.status_code == 200
    assert (await client.get(f"/startups/{startup_id}")).json()["current_stage"] == "lean_canvas"

    canvas_history = (
        await client.get(f"/startups/{startup_id}/documents/lean_canvas/history")
    ).json()["documents"]
    assert [document["version"] for document in canvas_history] == [2, 1]
    assert [document["is_current"] for document in canvas_history] == [True, False]
    assert canvas_history[0]["content"]["problem"] == (
        "Tutoring teams miss revenue due to manual scheduling."
    )
    assert canvas_history[1]["content"]["problem"] == "Tutors lose hours coordinating lessons."

    advance_to_bmc = await client.post(f"/startups/{startup_id}/advance-stage")
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
        json={"user_id": str(user_id), "message": "Create the BMC."},
    )

    assert bmc_chat.status_code == 200
    bmc_document = (await client.get(f"/startups/{startup_id}/documents/bmc")).json()
    assert bmc_document["version"] == 1
    assert bmc_document["is_current"] is True
    assert bmc_document["content"]["customer_segments"] == "Multi-location tutoring centers."
    assert bmc_document["content"]["value_propositions"] == (
        "Lower admin load and fewer missed sessions."
    )


async def _create_user(session_factory: async_sessionmaker[AsyncSession]) -> uuid.UUID:
    async with session_factory() as session:
        user = User(name="Route Test User", email=f"{uuid.uuid4()}@example.com")
        session.add(user)
        await session.commit()
        return user.id


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
        return self.responses.pop(0)


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


def _asyncpg_url(url: str) -> str:
    if url.startswith("postgresql+psycopg2://"):
        return url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url
