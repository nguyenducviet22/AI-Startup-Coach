import asyncio

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine
from testcontainers.community.postgres import PostgresContainer

from app.core.config import ROOT_DIR, get_settings


def test_alembic_upgrade_head_creates_auth_agentops_and_research_tables(monkeypatch) -> None:
    with PostgresContainer("postgres:16-alpine") as postgres:
        async_url = _asyncpg_url(postgres.get_connection_url())
        monkeypatch.setenv("DATABASE_URL", async_url)
        monkeypatch.setenv("JWT_SECRET", "migration-test-secret-with-at-least-thirty-two-bytes")
        get_settings.cache_clear()

        alembic_config = Config(str(ROOT_DIR / "alembic.ini"))
        command.upgrade(alembic_config, "head")

        try:
            (
                table_names,
                columns_by_table,
                nullable_by_table,
                indexes_by_table,
                foreign_keys_by_table,
                unique_constraints_by_table,
                identity_columns_by_table,
            ) = asyncio.run(_inspect_schema(async_url))
        finally:
            get_settings.cache_clear()

        assert "auth_credentials" in table_names
        assert "refresh_tokens" in table_names
        assert "agent_turns" in table_names
        assert "llm_calls" in table_names
        assert "tool_calls_log" in table_names
        assert "alert_events" in table_names
        assert "research_calls" in table_names
        assert "research_cache_entries" in table_names
        assert "research_quota_reservations" in table_names
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
        assert columns_by_table["research_calls"] == {
            "id",
            "sequence",
            "turn_id",
            "startup_id",
            "user_id",
            "session_id",
            "stage",
            "provider",
            "operation",
            "category",
            "query_fingerprint",
            "provider_request_id",
            "cache_hit",
            "provider_call_made",
            "credits_reserved",
            "credits_charged",
            "cost_usd",
            "pricing_unknown",
            "latency_ms",
            "status",
            "error_code",
            "created_at",
        }
        assert columns_by_table["research_cache_entries"] == {
            "id",
            "sequence",
            "startup_id",
            "research_call_id",
            "cache_key",
            "operation",
            "category",
            "payload",
            "retrieved_at",
            "expires_at",
            "created_at",
            "updated_at",
        }
        assert columns_by_table["research_quota_reservations"] == {
            "id",
            "sequence",
            "user_id",
            "session_id",
            "reserved_calls",
            "reserved_credits",
            "charged_credits",
            "released_credits",
            "status",
            "created_at",
            "reconciled_at",
            "released_at",
        }
        assert indexes_by_table["llm_calls"] >= {
            ("ix_llm_calls_created_at", ("created_at",)),
            ("ix_llm_calls_stage_created_at", ("stage", "created_at")),
        }
        assert indexes_by_table["tool_calls_log"] >= {
            ("ix_tool_calls_log_created_at", ("created_at",)),
            ("ix_tool_calls_log_stage_created_at", ("stage", "created_at")),
        }
        assert indexes_by_table["research_calls"] >= {
            ("ix_research_calls_startup_created_at", ("startup_id", "created_at")),
            ("ix_research_calls_user_created_at", ("user_id", "created_at")),
            ("ix_research_calls_session_created_at", ("session_id", "created_at")),
            ("ix_research_calls_stage_category_created_at", ("stage", "category", "created_at")),
            ("ix_research_calls_turn_id", ("turn_id",)),
        }
        assert indexes_by_table["research_cache_entries"] >= {
            ("ix_research_cache_entries_expires_at", ("expires_at",)),
        }
        assert indexes_by_table["research_quota_reservations"] >= {
            ("ix_research_quota_reservations_user_created_at", ("user_id", "created_at")),
            ("ix_research_quota_reservations_session_created_at", ("session_id", "created_at")),
        }
        assert nullable_by_table["llm_calls"]["turn_id"] is False
        assert nullable_by_table["tool_calls_log"]["turn_id"] is False
        assert nullable_by_table["research_calls"]["turn_id"] is True
        assert nullable_by_table["research_cache_entries"]["research_call_id"] is True
        assert foreign_keys_by_table["research_cache_entries"] >= {
            ("fk_research_cache_entries_startup_id_startups", ("startup_id",), "startups"),
            (
                "fk_research_cache_entries_research_call_id_research_calls",
                ("research_call_id",),
                "research_calls",
            ),
        }
        assert foreign_keys_by_table["research_calls"] >= {
            ("fk_research_calls_turn_id_agent_turns", ("turn_id",), "agent_turns"),
            ("fk_research_calls_startup_id_startups", ("startup_id",), "startups"),
            ("fk_research_calls_user_id_users", ("user_id",), "users"),
            ("fk_research_calls_session_id_chat_sessions", ("session_id",), "chat_sessions"),
        }
        assert foreign_keys_by_table["research_quota_reservations"] >= {
            ("fk_research_quota_reservations_user_id_users", ("user_id",), "users"),
            ("fk_research_quota_reservations_session_id_chat_sessions", ("session_id",), "chat_sessions"),
        }
        assert (
            "uq_research_cache_entries_startup_id_cache_key",
            ("startup_id", "cache_key"),
        ) in unique_constraints_by_table["research_cache_entries"]
        for table_name in (
            "research_calls",
            "research_cache_entries",
            "research_quota_reservations",
        ):
            assert "sequence" in identity_columns_by_table[table_name]


def test_alembic_downgrade_removes_research_tables_indexes_and_constraints(monkeypatch) -> None:
    with PostgresContainer("postgres:16-alpine") as postgres:
        async_url = _asyncpg_url(postgres.get_connection_url())
        monkeypatch.setenv("DATABASE_URL", async_url)
        monkeypatch.setenv("JWT_SECRET", "migration-test-secret-with-at-least-thirty-two-bytes")
        get_settings.cache_clear()

        alembic_config = Config(str(ROOT_DIR / "alembic.ini"))
        command.upgrade(alembic_config, "head")
        command.downgrade(alembic_config, "20260801_0004")

        try:
            table_names, indexes, foreign_keys, unique_constraints = asyncio.run(
                _inspect_research_artifacts(async_url)
            )
        finally:
            get_settings.cache_clear()

        research_tables = {
            "research_calls",
            "research_cache_entries",
            "research_quota_reservations",
        }
        assert research_tables.isdisjoint(table_names)
        assert indexes == set()
        assert foreign_keys == set()
        assert unique_constraints == set()


async def _inspect_research_artifacts(
    url: str,
) -> tuple[set[str], set[str], set[str], set[str]]:
    engine = create_async_engine(url)
    try:
        async with engine.connect() as connection:
            return await connection.run_sync(_inspect_research_artifacts_sync)
    finally:
        await engine.dispose()


def _inspect_research_artifacts_sync(connection) -> tuple[set[str], set[str], set[str], set[str]]:
    inspector = inspect(connection)
    research_tables = {
        "research_calls",
        "research_cache_entries",
        "research_quota_reservations",
    }
    table_names = set(inspector.get_table_names())
    existing_research_tables = research_tables.intersection(table_names)
    indexes = {
        index["name"]
        for table_name in existing_research_tables
        for index in inspector.get_indexes(table_name)
    }
    foreign_keys = {
        foreign_key["name"]
        for table_name in existing_research_tables
        for foreign_key in inspector.get_foreign_keys(table_name)
    }
    unique_constraints = {
        constraint["name"]
        for table_name in existing_research_tables
        for constraint in inspector.get_unique_constraints(table_name)
    }
    return table_names, indexes, foreign_keys, unique_constraints


async def _inspect_schema(
    url: str,
) -> tuple[
    list[str],
    dict[str, set[str]],
    dict[str, dict[str, bool]],
    dict[str, set[tuple[str, tuple[str, ...]]]],
    dict[str, set[tuple[str | None, tuple[str, ...], str]]],
    dict[str, set[tuple[str | None, tuple[str, ...]]]],
    dict[str, set[str]],
]:
    engine = create_async_engine(url)
    try:
        async with engine.connect() as connection:
            return await connection.run_sync(_inspect_schema_sync)
    finally:
        await engine.dispose()


def _inspect_schema_sync(
    connection,
) -> tuple[
    list[str],
    dict[str, set[str]],
    dict[str, dict[str, bool]],
    dict[str, set[tuple[str, tuple[str, ...]]]],
    dict[str, set[tuple[str | None, tuple[str, ...], str]]],
    dict[str, set[tuple[str | None, tuple[str, ...]]]],
    dict[str, set[str]],
]:
    inspector = inspect(connection)
    table_names = inspector.get_table_names()
    inspected_tables = (
        "auth_credentials",
        "refresh_tokens",
        "agent_turns",
        "llm_calls",
        "tool_calls_log",
        "alert_events",
        "research_calls",
        "research_cache_entries",
        "research_quota_reservations",
    )
    columns_by_table = {
        table_name: {column["name"] for column in inspector.get_columns(table_name)}
        for table_name in inspected_tables
    }
    nullable_by_table = {
        table_name: {
            column["name"]: column["nullable"]
            for column in inspector.get_columns(table_name)
        }
        for table_name in ("llm_calls", "tool_calls_log", "research_calls", "research_cache_entries")
    }
    indexes_by_table = {
        table_name: {
            (index["name"], tuple(index["column_names"]))
            for index in inspector.get_indexes(table_name)
        }
        for table_name in (
            "llm_calls",
            "tool_calls_log",
            "research_calls",
            "research_cache_entries",
            "research_quota_reservations",
        )
    }
    foreign_keys_by_table = {
        table_name: {
            (
                foreign_key["name"],
                tuple(foreign_key["constrained_columns"]),
                foreign_key["referred_table"],
            )
            for foreign_key in inspector.get_foreign_keys(table_name)
        }
        for table_name in ("research_calls", "research_cache_entries", "research_quota_reservations")
    }
    unique_constraints_by_table = {
        table_name: {
            (constraint["name"], tuple(constraint["column_names"]))
            for constraint in inspector.get_unique_constraints(table_name)
        }
        for table_name in ("research_cache_entries",)
    }
    identity_columns_by_table = {
        table_name: {
            column["name"]
            for column in inspector.get_columns(table_name)
            if column.get("identity") is not None
        }
        for table_name in ("research_calls", "research_cache_entries", "research_quota_reservations")
    }
    return (
        table_names,
        columns_by_table,
        nullable_by_table,
        indexes_by_table,
        foreign_keys_by_table,
        unique_constraints_by_table,
        identity_columns_by_table,
    )


def _asyncpg_url(url: str) -> str:
    if url.startswith("postgresql+psycopg2://"):
        return url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url
