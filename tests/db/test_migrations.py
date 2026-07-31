import asyncio

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine
from testcontainers.community.postgres import PostgresContainer

from app.core.config import ROOT_DIR, get_settings


def test_alembic_upgrade_head_creates_auth_tables(monkeypatch) -> None:
    with PostgresContainer("postgres:16-alpine") as postgres:
        async_url = _asyncpg_url(postgres.get_connection_url())
        monkeypatch.setenv("DATABASE_URL", async_url)
        monkeypatch.setenv("JWT_SECRET", "migration-test-secret-with-at-least-thirty-two-bytes")
        get_settings.cache_clear()

        alembic_config = Config(str(ROOT_DIR / "alembic.ini"))
        command.upgrade(alembic_config, "head")

        try:
            table_names, columns_by_table = asyncio.run(_inspect_schema(async_url))
        finally:
            get_settings.cache_clear()

        assert "auth_credentials" in table_names
        assert "refresh_tokens" in table_names
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


async def _inspect_schema(url: str) -> tuple[list[str], dict[str, set[str]]]:
    engine = create_async_engine(url)
    try:
        async with engine.connect() as connection:
            return await connection.run_sync(_inspect_schema_sync)
    finally:
        await engine.dispose()


def _inspect_schema_sync(connection) -> tuple[list[str], dict[str, set[str]]]:
    inspector = inspect(connection)
    table_names = inspector.get_table_names()
    columns_by_table = {
        table_name: {column["name"] for column in inspector.get_columns(table_name)}
        for table_name in ("auth_credentials", "refresh_tokens")
    }
    return table_names, columns_by_table


def _asyncpg_url(url: str) -> str:
    if url.startswith("postgresql+psycopg2://"):
        return url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url
