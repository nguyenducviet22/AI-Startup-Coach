import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.community.postgres import PostgresContainer

import app.db.base  # noqa: F401
from app.models.base import Base
from app.models.chat import ChatMessage, ChatSession
from app.models.documents import LeanCanvas
from app.models.startup import Startup
from app.models.user import User
from app.services.chat_service import ChatService, ChatSessionNotFoundError
from app.services.document_service import (
    DocumentService,
    StartupNotFoundError,
    UnknownDocumentTypeError,
)
from app.services.startup_overview_service import StartupOverviewService
from app.services.startup_report_service import StartupReportService


@pytest.fixture(scope="module")
def postgres_url() -> AsyncIterator[str]:
    with PostgresContainer("postgres:16-alpine") as postgres:
        url = postgres.get_connection_url()
        yield _asyncpg_url(url)


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


async def test_document_service_creates_new_current_version_without_losing_history(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    startup_id = await _create_startup(session_factory)

    async with session_factory() as session:
        service = DocumentService(session)
        first = await service.save_document(
            startup_id=startup_id,
            doc_type="lean_canvas",
            data=_lean_canvas_payload(problem="Manual scheduling wastes tutor time."),
        )
        second = await service.save_document(
            startup_id=startup_id,
            doc_type="lean_canvas",
            data=_lean_canvas_payload(problem="Lesson coordination is scattered."),
        )

        current = await service.get_current_document(startup_id=startup_id, doc_type="lean_canvas")
        history = await service.get_document_history(startup_id=startup_id, doc_type="lean_canvas")

    assert first["version"] == 1
    assert second["version"] == 2
    assert current is not None
    assert current["version"] == 2
    assert current["content"]["problem"] == "Lesson coordination is scattered."
    assert [entry["version"] for entry in history] == [2, 1]


async def test_document_service_persists_long_funding_recommendation(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    startup_id = await _create_startup(session_factory)
    recommendation = "Bootstrap validation first, then consider grants, competitions, accelerators, or pre-seed funding after demonstrating repeat usage and vendor willingness to pay."

    async with session_factory() as session:
        service = DocumentService(session)
        document = await service.save_document(
            startup_id=startup_id,
            doc_type="funding_guide",
            data={
                "pitch_outline": [{"slide_title": "The ask", "content": "Validate the MVP."}],
                "valuation_notes": "Use educational ranges only and consult an advisor before discussing terms.",
                "funding_stage_recommendation": recommendation,
            },
        )
        history = await service.get_document_history(
            startup_id=startup_id,
            doc_type="funding_guide",
        )

    assert document["content"]["funding_stage_recommendation"] == recommendation
    assert history[0]["content"]["funding_stage_recommendation"] == recommendation
    assert [entry["is_current"] for entry in history] == [True]


async def test_document_service_restores_old_content_as_a_new_current_version(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    startup_id = await _create_startup(session_factory)

    async with session_factory() as session:
        service = DocumentService(session)
        await service.save_document(
            startup_id=startup_id,
            doc_type="lean_canvas",
            data=_lean_canvas_payload(problem="Original problem."),
        )
        await service.save_document(
            startup_id=startup_id,
            doc_type="lean_canvas",
            data=_lean_canvas_payload(problem="New problem."),
        )

        restored = await service.restore_document_version(
            startup_id=startup_id,
            doc_type="lean_canvas",
            version=1,
        )
        history = await service.get_document_history(startup_id=startup_id, doc_type="lean_canvas")

    assert restored["version"] == 3
    assert restored["is_current"] is True
    assert restored["content"]["problem"] == "Original problem."
    assert [entry["version"] for entry in history] == [3, 2, 1]
    assert [entry["is_current"] for entry in history] == [True, False, False]


async def test_startup_overview_counts_documents_versions_and_recent_updates(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    startup_id = await _create_startup(session_factory)
    async with session_factory() as session:
        documents = DocumentService(session)
        await documents.save_document(
            startup_id=startup_id,
            doc_type="lean_canvas",
            data=_lean_canvas_payload(problem="First."),
        )
        await documents.save_document(
            startup_id=startup_id,
            doc_type="lean_canvas",
            data=_lean_canvas_payload(problem="Second."),
        )
        await documents.save_document(
            startup_id=startup_id,
            doc_type="swot",
            data={"strengths": ["Fast"], "weaknesses": [], "opportunities": [], "threats": []},
        )
        overview = await StartupOverviewService(session).get_overview(startup_id)

    assert overview["journey_completed_steps"] == 1
    assert overview["journey_total_steps"] == 8
    assert overview["completed_documents"] == 2
    assert overview["total_documents"] == 6
    assert overview["total_versions"] == 3
    assert [item["doc_type"] for item in overview["recent_updates"]][:2] == ["swot", "lean_canvas"]


async def test_startup_report_derives_overview_and_finance_from_current_documents(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    startup_id = await _create_startup(session_factory)
    async with session_factory() as session:
        documents = DocumentService(session)
        await documents.save_document(
            startup_id=startup_id,
            doc_type="lean_canvas",
            data={**_lean_canvas_payload(problem="Students lose focus."), "revenue_streams": "49k/month", "cost_structure": "Hosting"},
        )
        report = await StartupReportService(session).get_report(startup_id)

    sections = {section["key"]: section for section in report["sections"]}
    assert sections["overview"]["available"] is True
    assert sections["overview"]["content"]["problem"] == "Students lose focus."
    assert sections["basic_finance"]["available"] is True
    assert sections["basic_finance"]["content"] == {
        "revenue_streams": "49k/month",
        "cost_structure": "Hosting",
        "marketing_budget": None,
    }
    assert sections["swot"]["available"] is False


async def test_document_service_serializes_concurrent_writes_to_one_current_row(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    startup_id = await _create_startup(session_factory)

    async with session_factory() as lock_session:
        await lock_session.begin()
        await lock_session.execute(select(Startup.id).where(Startup.id == startup_id).with_for_update())

        task_one = asyncio.create_task(
            _write_lean_canvas(session_factory, startup_id, "First queued write.")
        )
        task_two = asyncio.create_task(
            _write_lean_canvas(session_factory, startup_id, "Second queued write.")
        )

        await asyncio.sleep(0.2)
        assert not task_one.done()
        assert not task_two.done()
        await lock_session.commit()

        results = await asyncio.wait_for(asyncio.gather(task_one, task_two), timeout=10)

    assert sorted(result["version"] for result in results) == [1, 2]

    async with session_factory() as verify_session:
        current_count = await verify_session.scalar(
            select(func.count())
            .select_from(LeanCanvas)
            .where(LeanCanvas.startup_id == startup_id, LeanCanvas.is_current.is_(True))
        )
        rows = (
            await verify_session.execute(
                select(LeanCanvas).where(LeanCanvas.startup_id == startup_id).order_by(LeanCanvas.version)
            )
        ).scalars().all()

    assert current_count == 1
    assert [row.version for row in rows] == [1, 2]
    assert [row.is_current for row in rows].count(True) == 1


async def test_document_service_supports_doc_type_aliases(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    startup_id = await _create_startup(session_factory)

    async with session_factory() as session:
        service = DocumentService(session)
        saved = await service.save_document(
            startup_id=startup_id,
            doc_type="marketing",
            data={
                "target_audience": "Independent tutoring centers",
                "channels": ["Founder-led outbound"],
                "key_messages": "Spend more time teaching.",
                "budget_estimate": "$500/month",
            },
        )

    assert saved["doc_type"] == "marketing_strategy"
    assert saved["content"]["channels"] == ["Founder-led outbound"]


async def test_document_service_raises_startup_not_found_for_missing_startup(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    missing_startup_id = uuid.uuid4()

    async with session_factory() as session:
        service = DocumentService(session)

        with pytest.raises(StartupNotFoundError) as exc_info:
            await service.save_document(
                startup_id=missing_startup_id,
                doc_type="lean_canvas",
                data=_lean_canvas_payload(problem="This startup does not exist."),
            )

    assert exc_info.value.startup_id == missing_startup_id


async def test_document_service_raises_unknown_document_type_for_invalid_doc_type(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    startup_id = await _create_startup(session_factory)

    async with session_factory() as session:
        service = DocumentService(session)

        with pytest.raises(UnknownDocumentTypeError) as save_exc_info:
            await service.save_document(
                startup_id=startup_id,
                doc_type="not_a_document",
                data={},
            )

        with pytest.raises(UnknownDocumentTypeError) as read_exc_info:
            await service.get_current_document(
                startup_id=startup_id,
                doc_type="not_a_document",
            )

    assert save_exc_info.value.doc_type == "not_a_document"
    assert read_exc_info.value.doc_type == "not_a_document"


async def test_chat_service_reuses_latest_session_and_preserves_message_order(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    startup_id = await _create_startup(session_factory)

    async with session_factory() as session:
        service = ChatService(session)
        first = await service.get_or_create_session(startup_id=startup_id)
        reused = await service.get_or_create_session(startup_id=startup_id)

        await service.save_message(session_id=first.id, role="user", content="Hello")
        await service.save_message(session_id=first.id, role="assistant", content="Let us shape the idea.")
        history = await service.get_recent_messages(session_id=first.id, limit=10)

    assert reused.id == first.id
    assert [(message["role"], message["content"]) for message in history] == [
        ("user", "Hello"),
        ("assistant", "Let us shape the idea."),
    ]


async def test_chat_service_orders_messages_by_sequence_when_timestamps_tie(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    startup_id = await _create_startup(session_factory)
    tied_timestamp = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)

    async with session_factory() as session:
        service = ChatService(session)
        chat_session = await service.get_or_create_session(startup_id=startup_id)
        session.add_all(
            [
                ChatMessage(
                    session_id=chat_session.id,
                    role="user",
                    content="First message",
                    created_at=tied_timestamp,
                ),
                ChatMessage(
                    session_id=chat_session.id,
                    role="assistant",
                    content="Second message",
                    created_at=tied_timestamp,
                ),
            ]
        )
        await session.commit()

        history = await service.get_recent_messages(session_id=chat_session.id, limit=10)

    assert [(message["role"], message["content"]) for message in history] == [
        ("user", "First message"),
        ("assistant", "Second message"),
    ]


async def test_chat_service_reuses_latest_session_by_sequence_when_timestamps_tie(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    startup_id = await _create_startup(session_factory)
    tied_timestamp = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)

    async with session_factory() as session:
        first = ChatSession(startup_id=startup_id, created_at=tied_timestamp)
        second = ChatSession(startup_id=startup_id, created_at=tied_timestamp)
        session.add_all([first, second])
        await session.commit()

        reused = await ChatService(session).get_or_create_session(startup_id=startup_id)

    assert reused.id == second.id


async def test_chat_service_rejects_session_from_another_startup(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    startup_id = await _create_startup(session_factory)
    other_startup_id = await _create_startup(session_factory)

    async with session_factory() as session:
        service = ChatService(session)
        session_for_first_startup = await service.get_or_create_session(startup_id=startup_id)

        with pytest.raises(ChatSessionNotFoundError):
            await service.get_or_create_session(
                startup_id=other_startup_id,
                session_id=session_for_first_startup.id,
            )


async def _write_lean_canvas(
    session_factory: async_sessionmaker[AsyncSession],
    startup_id: uuid.UUID,
    problem: str,
) -> dict:
    async with session_factory() as session:
        return await DocumentService(session).save_document(
            startup_id=startup_id,
            doc_type="lean_canvas",
            data=_lean_canvas_payload(problem=problem),
        )


async def _create_startup(session_factory: async_sessionmaker[AsyncSession]) -> uuid.UUID:
    async with session_factory() as session:
        user = User(name="Test User", email=f"{uuid.uuid4()}@example.com")
        session.add(user)
        await session.flush()
        startup = Startup(user_id=user.id, name="TutorOS")
        session.add(startup)
        await session.commit()
        return startup.id


def _lean_canvas_payload(problem: str) -> dict[str, str]:
    return {
        "problem": problem,
        "solution": "Scheduling automation.",
        "unique_value_proposition": "Calendar operations for tutoring teams.",
        "unfair_advantage": "",
        "customer_segments": "Independent tutoring centers.",
        "key_metrics": "",
        "channels": "",
        "cost_structure": "",
        "revenue_streams": "",
    }


def _asyncpg_url(url: str) -> str:
    if url.startswith("postgresql+psycopg2://"):
        return url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url
