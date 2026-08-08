import asyncio
import inspect
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import get_args

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from testcontainers.community.postgres import PostgresContainer

from app.core.config import ROOT_DIR, Settings, get_settings
from app.db import session as db_session
from app.models.agentops import AgentTurn, AlertEvent, LlmCall, ToolCallLog
from app.models.chat import ChatSession
from app.models.research import ResearchCall
from app.models.startup import Startup
from app.models.user import User
from app.services.agentops import pricing
from app.services.agentops import alerting_service
from app.services.agentops.alerting_service import evaluate_error_rate
from app.services.agentops.instrumented_tool_dispatcher import InstrumentedToolDispatcher
from app.services.agentops.llm_metrics_service import record_llm_call
from app.services.agentops.tool_metrics_service import record_tool_call
from app.services.agentops.turn_metrics_service import finish_turn, start_turn
from app.services.tool_dispatcher import ToolDispatcher
from app.services import research_errors
from app.research.errors import ProviderErrorCode


@pytest.fixture(scope="module")
def postgres_url() -> AsyncIterator[str]:
    with PostgresContainer("postgres:16-alpine") as postgres:
        yield _asyncpg_url(postgres.get_connection_url())


@pytest.fixture()
def agentops_database(monkeypatch: pytest.MonkeyPatch, postgres_url: str) -> AsyncIterator[str]:
    monkeypatch.setenv("DATABASE_URL", postgres_url)
    monkeypatch.setenv("JWT_SECRET", "agentops-service-test-secret-with-at-least-thirty-two-bytes")
    get_settings.cache_clear()
    _reset_app_db_session()

    asyncio.run(_reset_schema(postgres_url))
    command.upgrade(Config(str(ROOT_DIR / "alembic.ini")), "head")

    yield postgres_url

    _reset_app_db_session()
    get_settings.cache_clear()


async def test_start_turn_then_finish_turn_round_trips_through_database(agentops_database: str) -> None:
    startup_id, session_id = await _create_startup_and_session()
    turn_id = uuid.uuid4()

    await start_turn(turn_id, startup_id, session_id, "idea")

    async with db_session.get_session_local()() as session:
        pending_turn = await session.get(AgentTurn, turn_id)

    assert pending_turn is not None
    assert pending_turn.status == "pending"
    assert pending_turn.tool_call_count == 0
    assert pending_turn.latency_ms == 0

    await finish_turn(turn_id, "success", latency_ms=321, tool_call_count=2)

    async with db_session.get_session_local()() as session:
        finished_turn = await session.get(AgentTurn, turn_id)

    assert finished_turn is not None
    assert finished_turn.status == "success"
    assert finished_turn.latency_ms == 321
    assert finished_turn.tool_call_count == 2


async def test_record_llm_call_and_tool_call_insert_expected_rows(agentops_database: str) -> None:
    startup_id, session_id = await _create_startup_and_session()
    turn_id = uuid.uuid4()
    await start_turn(turn_id, startup_id, session_id, "lean_canvas")

    await record_llm_call(
        turn_id=turn_id,
        startup_id=startup_id,
        session_id=session_id,
        stage="lean_canvas",
        model="openai/gpt-4o-mini",
        prompt_tokens=1000,
        completion_tokens=500,
        total_tokens=1500,
        cost_usd=Decimal("0.000450"),
        pricing_unknown=False,
        latency_ms=250,
        status="success",
        error_code=None,
    )
    await record_tool_call(
        turn_id=turn_id,
        startup_id=startup_id,
        tool_name="update_lean_canvas",
        stage="lean_canvas",
        latency_ms=42,
        status="ok",
        error_type=None,
    )

    async with db_session.get_session_local()() as session:
        llm_calls = (await session.execute(select(LlmCall))).scalars().all()
        tool_calls = (await session.execute(select(ToolCallLog))).scalars().all()

    assert len(llm_calls) == 1
    assert llm_calls[0].turn_id == turn_id
    assert llm_calls[0].startup_id == startup_id
    assert llm_calls[0].session_id == session_id
    assert llm_calls[0].stage == "lean_canvas"
    assert llm_calls[0].model == "openai/gpt-4o-mini"
    assert llm_calls[0].prompt_tokens == 1000
    assert llm_calls[0].completion_tokens == 500
    assert llm_calls[0].total_tokens == 1500
    assert llm_calls[0].cost_usd == Decimal("0.000450")
    assert llm_calls[0].pricing_unknown is False
    assert llm_calls[0].latency_ms == 250
    assert llm_calls[0].status == "success"
    assert llm_calls[0].error_code is None

    assert len(tool_calls) == 1
    assert tool_calls[0].turn_id == turn_id
    assert tool_calls[0].startup_id == startup_id
    assert tool_calls[0].tool_name == "update_lean_canvas"
    assert tool_calls[0].stage == "lean_canvas"
    assert tool_calls[0].latency_ms == 42
    assert tool_calls[0].status == "ok"
    assert tool_calls[0].error_type is None


def test_unknown_or_disabled_model_pricing_returns_unknown_not_zero() -> None:
    enabled_settings = _settings(agentops_pricing_enabled=True)
    disabled_settings = _settings(agentops_pricing_enabled=False)

    assert pricing.get_cost("unknown/provider-model", 1000, 1000, settings=enabled_settings) == (None, True)
    assert pricing.get_cost("openai/gpt-4o-mini", 1000, 1000, settings=disabled_settings) == (None, True)


async def test_llm_and_tool_turn_id_not_null_constraints_are_enforced(agentops_database: str) -> None:
    startup_id, session_id = await _create_startup_and_session()

    with pytest.raises(IntegrityError):
        await record_llm_call(
            turn_id=None,  # type: ignore[arg-type]
            startup_id=startup_id,
            session_id=session_id,
            stage="idea",
            model="openai/gpt-4o-mini",
            prompt_tokens=1,
            completion_tokens=1,
            total_tokens=2,
            cost_usd=None,
            pricing_unknown=True,
            latency_ms=10,
            status="success",
            error_code=None,
        )

    with pytest.raises(IntegrityError):
        await record_tool_call(
            turn_id=None,  # type: ignore[arg-type]
            startup_id=startup_id,
            tool_name="update_lean_canvas",
            stage="idea",
            latency_ms=10,
            status="ok",
            error_type=None,
        )


async def test_metrics_write_survives_unrelated_session_rollback(agentops_database: str) -> None:
    startup_id, session_id = await _create_startup_and_session()
    turn_id = uuid.uuid4()

    await start_turn(turn_id, startup_id, session_id, "idea")

    try:
        async with db_session.get_session_local()() as unrelated_session:
            unrelated_session.add(User(name="Rolled Back", email=f"{uuid.uuid4()}@example.com"))
            await unrelated_session.flush()
            raise RuntimeError("simulate request failure after metrics commit")
    except RuntimeError:
        pass

    async with db_session.get_session_local()() as verify_session:
        persisted_turn = await verify_session.get(AgentTurn, turn_id)
        rolled_back_user = await verify_session.scalar(
            select(User).where(User.name == "Rolled Back")
        )

    assert persisted_turn is not None
    assert persisted_turn.status == "pending"
    assert rolled_back_user is None


async def test_instrumented_tool_dispatcher_records_real_validation_error_status(
    agentops_database: str,
) -> None:
    startup_id, session_id = await _create_startup_and_session()
    turn_id = uuid.uuid4()
    await start_turn(turn_id, startup_id, session_id, "swot")
    dispatcher = InstrumentedToolDispatcher(
        wrapped=ToolDispatcher(),
        turn_id=turn_id,
        startup_id=startup_id,
        stage="swot",
    )

    result = await dispatcher.execute(
        tool_name="generate_swot",
        current_stage="swot",
        startup_id=startup_id,
        arguments={
            "strengths": [],
            "weaknesses": [],
            "opportunities": [],
            "threats": [],
        },
    )

    async with db_session.get_session_local()() as session:
        tool_call = await session.scalar(
            select(ToolCallLog).where(ToolCallLog.turn_id == turn_id)
        )

    assert result["ok"] is False
    assert result["error"]["type"] == "tool_validation_error"
    assert tool_call is not None
    assert tool_call.status == "validation_error"
    assert tool_call.error_type == "tool_validation_error"


async def test_global_llm_error_rate_alert_inserts_alert_event(agentops_database: str) -> None:
    now = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
    startup_id, session_id = await _create_startup_and_session()
    turn_id = await _create_agent_turn(startup_id, session_id, "idea")
    await _insert_llm_call(
        turn_id=turn_id,
        startup_id=startup_id,
        session_id=session_id,
        stage="idea",
        status="success",
        created_at=now - timedelta(seconds=10),
    )
    await _insert_llm_call(
        turn_id=turn_id,
        startup_id=startup_id,
        session_id=session_id,
        stage="idea",
        status="error",
        created_at=now - timedelta(seconds=20),
    )

    result = await evaluate_error_rate(
        metric_name="llm_error_rate",
        scope=None,
        window_seconds=60,
        threshold=Decimal("0.5"),
        now=now,
    )

    async with db_session.get_session_local()() as session:
        alerts = (await session.execute(select(AlertEvent))).scalars().all()

    assert result.total_count == 2
    assert result.error_count == 1
    assert result.observed_value == Decimal("0.5")
    assert result.alert_inserted is True
    assert result.severity == "warning"
    assert len(alerts) == 1
    assert alerts[0].metric_name == "llm_error_rate"
    assert alerts[0].scope is None
    assert alerts[0].threshold == Decimal("0.5")
    assert alerts[0].observed_value == Decimal("0.5")
    assert alerts[0].window_seconds == 60
    assert alerts[0].severity == "warning"


async def test_stage_scoped_tool_error_rate_counts_only_requested_stage(
    agentops_database: str,
) -> None:
    now = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
    startup_id, session_id = await _create_startup_and_session()
    swot_turn_id = await _create_agent_turn(startup_id, session_id, "swot")
    bmc_turn_id = await _create_agent_turn(startup_id, session_id, "bmc")
    await _insert_tool_call(
        turn_id=swot_turn_id,
        startup_id=startup_id,
        stage="swot",
        status="ok",
        created_at=now - timedelta(seconds=5),
    )
    await _insert_tool_call(
        turn_id=swot_turn_id,
        startup_id=startup_id,
        stage="swot",
        status="persistence_error",
        created_at=now - timedelta(seconds=10),
    )
    await _insert_tool_call(
        turn_id=bmc_turn_id,
        startup_id=startup_id,
        stage="bmc",
        status="error",
        created_at=now - timedelta(seconds=15),
    )

    result = await evaluate_error_rate(
        metric_name="tool_error_rate",
        scope="swot",
        window_seconds=60,
        threshold=Decimal("0.5"),
        now=now,
    )

    async with db_session.get_session_local()() as session:
        alerts = (await session.execute(select(AlertEvent))).scalars().all()

    assert result.total_count == 2
    assert result.error_count == 1
    assert result.observed_value == Decimal("0.5")
    assert result.alert_inserted is True
    assert len(alerts) == 1
    assert alerts[0].metric_name == "tool_error_rate"
    assert alerts[0].scope == "swot"


async def test_tool_error_rate_excludes_validation_and_not_allowed_from_errors(
    agentops_database: str,
) -> None:
    now = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
    startup_id, session_id = await _create_startup_and_session()
    turn_id = await _create_agent_turn(startup_id, session_id, "lean_canvas")
    for status in ("ok", "validation_error", "not_allowed"):
        await _insert_tool_call(
            turn_id=turn_id,
            startup_id=startup_id,
            stage="lean_canvas",
            status=status,
            created_at=now - timedelta(seconds=5),
        )

    result = await evaluate_error_rate(
        metric_name="tool_error_rate",
        scope="lean_canvas",
        window_seconds=60,
        threshold=Decimal("0.01"),
        now=now,
    )

    async with db_session.get_session_local()() as session:
        alert_count = await session.scalar(select(func.count()).select_from(AlertEvent))

    assert result.total_count == 3
    assert result.error_count == 0
    assert result.observed_value == Decimal("0")
    assert result.alert_inserted is False
    assert alert_count == 0


async def test_error_rate_below_threshold_does_not_insert_alert(agentops_database: str) -> None:
    now = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
    startup_id, session_id = await _create_startup_and_session()
    turn_id = await _create_agent_turn(startup_id, session_id, "idea")
    await _insert_llm_call(
        turn_id=turn_id,
        startup_id=startup_id,
        session_id=session_id,
        stage="idea",
        status="success",
        created_at=now - timedelta(seconds=10),
    )
    await _insert_llm_call(
        turn_id=turn_id,
        startup_id=startup_id,
        session_id=session_id,
        stage="idea",
        status="error",
        created_at=now - timedelta(seconds=20),
    )

    result = await evaluate_error_rate(
        metric_name="llm_error_rate",
        scope=None,
        window_seconds=60,
        threshold=Decimal("0.75"),
        now=now,
    )

    async with db_session.get_session_local()() as session:
        alert_count = await session.scalar(select(func.count()).select_from(AlertEvent))

    assert result.total_count == 2
    assert result.error_count == 1
    assert result.observed_value == Decimal("0.5")
    assert result.alert_inserted is False
    assert alert_count == 0


async def test_error_rate_zero_volume_returns_not_enough_data_without_alert(
    agentops_database: str,
) -> None:
    now = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)

    result = await evaluate_error_rate(
        metric_name="llm_error_rate",
        scope=None,
        window_seconds=60,
        threshold=Decimal("0.5"),
        now=now,
    )

    async with db_session.get_session_local()() as session:
        alert_count = await session.scalar(select(func.count()).select_from(AlertEvent))

    assert result.total_count == 0
    assert result.error_count == 0
    assert result.observed_value is None
    assert result.alert_inserted is False
    assert result.reason == "not_enough_data"
    assert alert_count == 0


async def test_non_research_error_rate_requires_explicit_threshold_and_window() -> None:
    with pytest.raises(ValueError, match="required for non-research"):
        await evaluate_error_rate(metric_name="llm_error_rate", scope=None)


async def test_research_error_rate_zero_volume_returns_not_enough_data_without_alert(
    agentops_database: str,
) -> None:
    now = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)

    result = await evaluate_error_rate(
        metric_name="research_error_rate",
        scope=None,
        window_seconds=60,
        threshold=Decimal("0.5"),
        now=now,
    )

    assert result.total_count == 0
    assert result.error_count == 0
    assert result.observed_value is None
    assert result.alert_inserted is False
    assert result.reason == "not_enough_data"


async def test_stage_scoped_research_error_rate_counts_only_requested_stage(
    agentops_database: str,
) -> None:
    now = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
    startup_id, _ = await _create_startup_and_session()
    await _insert_research_call(
        startup_id=startup_id,
        stage="swot",
        status="error",
        error_code="provider_timeout",
        provider_call_made=True,
        cache_hit=False,
        created_at=now - timedelta(seconds=5),
    )
    await _insert_research_call(
        startup_id=startup_id,
        stage="bmc",
        status="error",
        error_code="provider_unavailable",
        provider_call_made=True,
        cache_hit=False,
        created_at=now - timedelta(seconds=5),
    )

    result = await evaluate_error_rate(
        metric_name="research_error_rate",
        scope="swot",
        window_seconds=60,
        threshold=Decimal("1"),
        now=now,
    )

    assert result.total_count == 1
    assert result.error_count == 1
    assert result.observed_value == Decimal("1")
    assert result.alert_inserted is True


async def test_research_error_rate_excludes_cache_validation_and_quota_rejections(
    agentops_database: str,
) -> None:
    now = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
    startup_id, _ = await _create_startup_and_session()
    for status, error_code, provider_call_made, cache_hit in (
        ("success", None, False, True),
        ("error", "research_validation_error", False, False),
        ("error", "research_rate_limited", False, False),
        ("error", "provider_request_rejected", True, False),
    ):
        await _insert_research_call(
            startup_id=startup_id,
            stage="idea",
            status=status,
            error_code=error_code,
            provider_call_made=provider_call_made,
            cache_hit=cache_hit,
            created_at=now - timedelta(seconds=5),
        )

    result = await evaluate_error_rate(
        metric_name="research_error_rate",
        scope="idea",
        window_seconds=60,
        threshold=Decimal("0.01"),
        now=now,
    )

    assert result.total_count == 4
    assert result.error_count == 0
    assert result.observed_value == Decimal("0")
    assert result.alert_inserted is False


async def test_error_rate_window_includes_boundary_and_excludes_older_rows(
    agentops_database: str,
) -> None:
    now = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
    startup_id, session_id = await _create_startup_and_session()
    turn_id = await _create_agent_turn(startup_id, session_id, "idea")
    await _insert_llm_call(
        turn_id=turn_id,
        startup_id=startup_id,
        session_id=session_id,
        stage="idea",
        status="error",
        created_at=now - timedelta(seconds=60),
    )
    await _insert_llm_call(
        turn_id=turn_id,
        startup_id=startup_id,
        session_id=session_id,
        stage="idea",
        status="success",
        created_at=now - timedelta(seconds=60, microseconds=1),
    )

    result = await evaluate_error_rate(
        metric_name="llm_error_rate",
        scope=None,
        window_seconds=60,
        threshold=Decimal("1"),
        now=now,
    )

    assert result.total_count == 1
    assert result.error_count == 1
    assert result.observed_value == Decimal("1")
    assert result.alert_inserted is True


def test_agentops_pricing_setting_has_no_duplicate_app_fallback_default() -> None:
    assert Settings.model_fields["agentops_pricing_enabled"].alias == "AGENTOPS_PRICING_ENABLED"
    assert "AGENTOPS_PRICING_ENABLED=true" in (ROOT_DIR / ".env.example").read_text(encoding="utf-8")

    app_references = [
        path.relative_to(ROOT_DIR)
        for path in (ROOT_DIR / "app").rglob("*.py")
        if "AGENTOPS_PRICING_ENABLED" in path.read_text(encoding="utf-8")
    ]
    assert app_references == [Path("app/core/config.py")]
    assert "AGENTOPS_PRICING_ENABLED" not in inspect.getsource(pricing)


def test_research_infrastructure_error_codes_match_provider_failure_contract() -> None:
    provider_error_codes = set(get_args(ProviderErrorCode))
    source = inspect.getsource(research_errors.provider_failure)
    infrastructure_codes = {
        # Provider transport and response failures: retryable or not, they are
        # service-health signals rather than founder/input/configuration errors.
        "provider_timeout",
        "provider_rate_limited",
        "provider_unavailable",
        "provider_malformed_response",
    }
    non_infrastructure_codes = {
        # Caller/provider-request rejection and local configuration state do not
        # measure provider availability and must not inflate this error rate.
        "provider_request_rejected",
        "provider_missing_key",
        "research_disabled",
        "research_misconfigured",
    }

    assert "code=error.code" in source
    assert provider_error_codes == infrastructure_codes | non_infrastructure_codes
    assert research_errors.PROVIDER_INFRASTRUCTURE_ERROR_CODES == infrastructure_codes
    assert research_errors.PROVIDER_ATTEMPT_ERROR_CODES == infrastructure_codes | {
        "provider_request_rejected",
    }
    assert (
        alerting_service.RESEARCH_INFRASTRUCTURE_ERROR_CODES
        == research_errors.PROVIDER_INFRASTRUCTURE_ERROR_CODES
    )


async def _create_startup_and_session() -> tuple[uuid.UUID, uuid.UUID]:
    async with db_session.get_session_local()() as session:
        user = User(name="AgentOps Test User", email=f"{uuid.uuid4()}@example.com")
        session.add(user)
        await session.flush()

        startup = Startup(user_id=user.id, name="AgentOps Test Startup")
        session.add(startup)
        await session.flush()

        chat_session = ChatSession(startup_id=startup.id)
        session.add(chat_session)
        await session.commit()

        return startup.id, chat_session.id


async def _create_agent_turn(
    startup_id: uuid.UUID,
    session_id: uuid.UUID,
    stage: str,
) -> uuid.UUID:
    turn_id = uuid.uuid4()
    await start_turn(turn_id, startup_id, session_id, stage)
    return turn_id


async def _insert_llm_call(
    *,
    turn_id: uuid.UUID,
    startup_id: uuid.UUID,
    session_id: uuid.UUID,
    stage: str,
    status: str,
    created_at: datetime,
) -> None:
    async with db_session.get_session_local()() as session:
        session.add(
            LlmCall(
                turn_id=turn_id,
                startup_id=startup_id,
                session_id=session_id,
                stage=stage,
                model="openai/gpt-4o-mini",
                prompt_tokens=1,
                completion_tokens=1,
                total_tokens=2,
                cost_usd=None,
                pricing_unknown=True,
                latency_ms=10,
                status=status,
                error_code=None if status == "success" else status,
                created_at=created_at,
            )
        )
        await session.commit()


async def _insert_tool_call(
    *,
    turn_id: uuid.UUID,
    startup_id: uuid.UUID,
    stage: str,
    status: str,
    created_at: datetime,
) -> None:
    async with db_session.get_session_local()() as session:
        session.add(
            ToolCallLog(
                turn_id=turn_id,
                startup_id=startup_id,
                tool_name="generate_lean_canvas",
                stage=stage,
                latency_ms=10,
                status=status,
                error_type=None if status == "ok" else status,
                created_at=created_at,
            )
        )
        await session.commit()


async def _insert_research_call(
    *,
    startup_id: uuid.UUID,
    stage: str,
    status: str,
    error_code: str | None,
    provider_call_made: bool,
    cache_hit: bool,
    created_at: datetime,
) -> None:
    async with db_session.get_session_local()() as session:
        startup = await session.get(Startup, startup_id)
        assert startup is not None
        session.add(
            ResearchCall(
                startup_id=startup_id,
                user_id=startup.user_id,
                session_id=None,
                stage=stage,
                provider="tavily",
                operation="search",
                category="general",
                query_fingerprint="test-fingerprint",
                provider_request_id=None,
                cache_hit=cache_hit,
                provider_call_made=provider_call_made,
                credits_reserved=None,
                credits_charged=0,
                cost_usd=None,
                pricing_unknown=True,
                latency_ms=10,
                status=status,
                error_code=error_code,
                created_at=created_at,
            )
        )
        await session.commit()


async def _reset_schema(url: str) -> None:
    engine = db_session.create_async_engine(url, pool_pre_ping=True)
    try:
        async with engine.begin() as connection:
            await connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            await connection.execute(text("CREATE SCHEMA public"))
            await connection.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
    finally:
        await engine.dispose()


def _reset_app_db_session() -> None:
    db_session._engine = None
    db_session._session_local = None


def _settings(agentops_pricing_enabled: bool) -> Settings:
    return Settings(
        DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/coaching",
        OPENROUTER_API_KEY="test-key",
        OPENROUTER_BASE_URL="https://openrouter.test/api/v1",
        OPENROUTER_MODEL="test-model",
        OPENROUTER_HTTP_REFERER="http://localhost:8000",
        OPENROUTER_X_TITLE="AI Startup Coach",
        CHAT_HISTORY_LIMIT=20,
        LLM_MAX_RETRIES=2,
        LLM_RETRY_BACKOFF_SECONDS=0,
        AGENTOPS_PRICING_ENABLED=agentops_pricing_enabled,
        JWT_SECRET="agentops-settings-test-secret-with-at-least-thirty-two-bytes",
        JWT_ALGORITHM="HS256",
        ACCESS_TOKEN_EXPIRE_MINUTES=30,
        REFRESH_TOKEN_EXPIRE_DAYS=7,
    )


def _asyncpg_url(url: str) -> str:
    if url.startswith("postgresql+psycopg2://"):
        return url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url
