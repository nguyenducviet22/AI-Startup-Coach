import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.community.postgres import PostgresContainer

import app.db.base  # noqa: F401
from app.api.routes import get_settings
from app.core.config import Settings
from app.core.security import hash_refresh_token
from app.db.session import get_db_session
from app.main import app
from app.models.auth import RefreshToken
from app.models.base import Base


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
    async def override_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_settings] = _settings

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client

    app.dependency_overrides.clear()


async def test_signup_returns_token_bundle(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/auth/signup",
        json={"name": "Test User", "email": "Test@Example.com", "password": "secret123"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["user"]["email"] == "test@example.com"
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 1800


async def test_signup_duplicate_email_returns_structured_conflict(client: httpx.AsyncClient) -> None:
    await client.post(
        "/auth/signup",
        json={"name": "Test User", "email": "Test@Example.com", "password": "secret123"},
    )

    response = await client.post(
        "/auth/signup",
        json={"name": "Other User", "email": "test@example.com", "password": "secret123"},
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": {
            "field": "email",
            "code": "email_taken",
            "message": "Email is already registered.",
        }
    }


async def test_signup_rejects_short_password_with_validation_error(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/auth/signup",
        json={"name": "Test User", "email": "test@example.com", "password": "short"},
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "password"]
    assert response.json()["detail"][0]["type"] == "string_too_short"


async def test_login_returns_token_bundle(client: httpx.AsyncClient) -> None:
    await client.post(
        "/auth/signup",
        json={"name": "Test User", "email": "test@example.com", "password": "secret123"},
    )

    response = await client.post(
        "/auth/login",
        json={"email": "TEST@EXAMPLE.COM", "password": "secret123"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["email"] == "test@example.com"
    assert body["access_token"]
    assert body["refresh_token"]


async def test_login_invalid_credentials_returns_structured_unauthorized(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post(
        "/auth/login",
        json={"email": "missing@example.com", "password": "wrongpass"},
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": {
            "field": None,
            "code": "invalid_credentials",
            "message": "Email or password is incorrect.",
        }
    }


async def test_refresh_rotates_and_returns_new_token_bundle(client: httpx.AsyncClient) -> None:
    signup = await _signup(client)
    old_refresh_token = signup["refresh_token"]

    response = await client.post("/auth/refresh", json={"refresh_token": old_refresh_token})

    assert response.status_code == 200
    body = response.json()
    assert body["user"] == signup["user"]
    assert body["refresh_token"] != old_refresh_token
    assert body["access_token"]


async def test_refresh_missing_token_returns_structured_unauthorized(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post("/auth/refresh", json={"refresh_token": ""})

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "missing_token"


async def test_refresh_invalid_token_returns_structured_unauthorized(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post("/auth/refresh", json={"refresh_token": "not-real"})

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "invalid_token"


async def test_refresh_expired_token_returns_structured_unauthorized(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    signup = await _signup(client)
    async with session_factory() as session:
        token = await _get_refresh_token(session, signup["refresh_token"])
        token.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await session.commit()

    response = await client.post("/auth/refresh", json={"refresh_token": signup["refresh_token"]})

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "expired_token"


async def test_refresh_reused_token_returns_structured_unauthorized(
    client: httpx.AsyncClient,
) -> None:
    signup = await _signup(client)
    await client.post("/auth/refresh", json={"refresh_token": signup["refresh_token"]})

    response = await client.post("/auth/refresh", json={"refresh_token": signup["refresh_token"]})

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "refresh_reused"


async def test_logout_revokes_current_session(client: httpx.AsyncClient) -> None:
    signup = await _signup(client)

    response = await client.post("/auth/logout", json={"refresh_token": signup["refresh_token"]})

    assert response.status_code == 200
    assert response.json() == {"revoked": True}


async def test_refresh_revoked_token_returns_structured_unauthorized(
    client: httpx.AsyncClient,
) -> None:
    signup = await _signup(client)
    await client.post("/auth/logout", json={"refresh_token": signup["refresh_token"]})

    response = await client.post("/auth/refresh", json={"refresh_token": signup["refresh_token"]})

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "refresh_revoked"


async def test_logout_invalid_token_returns_structured_unauthorized(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post("/auth/logout", json={"refresh_token": "not-real"})

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "invalid_token"


async def _signup(client: httpx.AsyncClient) -> dict:
    response = await client.post(
        "/auth/signup",
        json={
            "name": "Test User",
            "email": f"{uuid.uuid4()}@example.com",
            "password": "secret123",
        },
    )
    assert response.status_code == 201
    return response.json()


async def _get_refresh_token(session: AsyncSession, raw_token: str) -> RefreshToken:
    result = await session.execute(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw_token))
    )
    return result.scalar_one()


def _settings() -> Settings:
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
        JWT_SECRET="auth-route-test-secret-with-at-least-thirty-two-bytes",
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
