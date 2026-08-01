import asyncio

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine
from testcontainers.community.postgres import PostgresContainer

from app.core.config import ROOT_DIR, get_settings


def test_alembic_upgrade_head_creates_auth_and_agentops_tables(monkeypatch) -> None:
    with PostgresContainer("postgres:16-alpine") as postgres:
        async_url = _asyncpg_url(postgres.get_connection_url())
        monkeypatch.setenv("DATABASE_URL", async_url)
        monkeypatch.setenv("JWT_SECRET", "migration-test-secret-with-at-least-thirty-two-bytes")
        get_settings.cache_clear()

        alembic_config = Config(str(ROOT_DIR / "alembic.ini"))
        command.upgrade(alembic_config, "head")

        try:
            table_names, columns_by_table, nullable_by_table, indexes_by_table = asyncio.run(_inspect_schema(async_url))
        finally:
            get_settings.cache_clear()

        assert "auth_credentials" in table_names
        assert "refresh_tokens" in table_names
        assert "agent_turns" in table_names
        assert "llm_calls" in table_names
        assert "tool_calls_log" in table_names
        assert "alert_events" in table_names
        assert columns_by_table["auth_credentials"] == {
            "id",
            "user_id",
            "provider",
            "provider_subject",
            "password_hash",
            "created_at",
            "updated_at",
        }
        assert columns_by_table["refresh_tokens"] == {
            "id",
            "sequence",
            "family_id",
            "user_id",
            "credential_id",
            "token_hash",
            "parent_token_id",
            "created_at",
            "expires_at",
            "consumed_at",
            "revoked_at",
            "reuse_detected_at",
            "replaced_by_token_id",
        }
        assert columns_by_table["agent_turns"] == {
            "id",
            "sequence",
            "startup_id",
            "session_id",
            "stage",
            "tool_call_count",
            "status",
            "latency_ms",
            "created_at",
        }
        assert columns_by_table["llm_calls"] == {
            "id",
            "sequence",
            "turn_id",
            "startup_id",
            "session_id",
            "stage",
            "model",
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "cost_usd",
            "pricing_unknown",
            "latency_ms",
            "status",
            "error_code",
            "created_at",
        }
        assert columns_by_table["tool_calls_log"] == {
            "id",
            "sequence",
            "turn_id",
            "startup_id",
            "tool_name",
            "stage",
            "latency_ms",
            "status",
            "error_type",
            "created_at",
        }
        assert columns_by_table["alert_events"] == {
            "id",
            "sequence",
            "metric_name",
            "scope",
            "threshold",
            "observed_value",
            "window_seconds",
            "severity",
            "triggered_at",
            "resolved_at",
        }
        assert indexes_by_table["llm_calls"] >= {
            ("ix_llm_calls_created_at", ("created_at",)),
            ("ix_llm_calls_stage_created_at", ("stage", "created_at")),
        }
        assert indexes_by_table["tool_calls_log"] >= {
            ("ix_tool_calls_log_created_at", ("created_at",)),
            ("ix_tool_calls_log_stage_created_at", ("stage", "created_at")),
        }
        assert nullable_by_table["llm_calls"]["turn_id"] is False
        assert nullable_by_table["tool_calls_log"]["turn_id"] is False


async def _inspect_schema(
    url: str,
) -> tuple[list[str], dict[str, set[str]], dict[str, dict[str, bool]], dict[str, set[tuple[str, tuple[str, ...]]]]]:
    engine = create_async_engine(url)
    try:
        async with engine.connect() as connection:
            return await connection.run_sync(_inspect_schema_sync)
    finally:
        await engine.dispose()


def _inspect_schema_sync(
    connection,
) -> tuple[list[str], dict[str, set[str]], dict[str, dict[str, bool]], dict[str, set[tuple[str, tuple[str, ...]]]]]:
    inspector = inspect(connection)
    table_names = inspector.get_table_names()
    columns_by_table = {
        table_name: {column["name"] for column in inspector.get_columns(table_name)}
        for table_name in (
            "auth_credentials",
            "refresh_tokens",
            "agent_turns",
            "llm_calls",
            "tool_calls_log",
            "alert_events",
        )
    }
    nullable_by_table = {
        table_name: {
            column["name"]: column["nullable"]
            for column in inspector.get_columns(table_name)
        }
        for table_name in ("llm_calls", "tool_calls_log")
    }
    indexes_by_table = {
        table_name: {
            (index["name"], tuple(index["column_names"]))
            for index in inspector.get_indexes(table_name)
        }
        for table_name in ("llm_calls", "tool_calls_log")
    }
    return table_names, columns_by_table, nullable_by_table, indexes_by_table


def _asyncpg_url(url: str) -> str:
    if url.startswith("postgresql+psycopg2://"):
        return url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url
