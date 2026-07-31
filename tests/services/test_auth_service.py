import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.community.postgres import PostgresContainer

import app.db.base  # noqa: F401
from app.core.config import Settings
from app.core.security import hash_refresh_token
from app.models.auth import AuthCredential, RefreshToken
from app.models.base import Base
from app.models.user import User
from app.services.auth_service import AuthService, AuthServiceError


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


async def test_signup_normalizes_email_and_rejects_case_insensitive_duplicate(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        service = AuthService(session, settings=_settings())
        result = await service.signup(
            name="Test User",
            email="Test@Example.com",
            password="password-one",
        )

        assert result["user"]["email"] == "test@example.com"

        with pytest.raises(AuthServiceError) as exc_info:
            await service.signup(
                name="Second User",
                email="test@example.com",
                password="password-two",
            )

        assert exc_info.value.detail.to_dict() == {
            "field": "email",
            "code": "email_taken",
            "message": "Email is already registered.",
        }

    async with session_factory() as verify_session:
        user_count = await verify_session.scalar(select(func.count()).select_from(User))
        credential_count = await verify_session.scalar(select(func.count()).select_from(AuthCredential))

    assert user_count == 1
    assert credential_count == 1


async def test_login_normalizes_email_and_creates_new_token_family(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        service = AuthService(session, settings=_settings())
        signup_result = await service.signup(
            name="Test User",
            email="test@example.com",
            password="correct-password",
        )
        login_result = await service.login(email="TEST@EXAMPLE.COM", password="correct-password")

        assert login_result["user"] == signup_result["user"]
        assert login_result["refresh_token"] != signup_result["refresh_token"]

    async with session_factory() as verify_session:
        tokens = (await verify_session.execute(select(RefreshToken))).scalars().all()

    assert len(tokens) == 2
    assert len({token.family_id for token in tokens}) == 2


async def test_login_rejects_bad_credentials_with_structured_error(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        service = AuthService(session, settings=_settings())
        await service.signup(
            name="Test User",
            email="test@example.com",
            password="correct-password",
        )

        with pytest.raises(AuthServiceError) as exc_info:
            await service.login(email="test@example.com", password="wrong-password")

    assert exc_info.value.detail.to_dict() == {
        "field": None,
        "code": "invalid_credentials",
        "message": "Email or password is incorrect.",
    }


async def test_refresh_rotates_token_and_consumes_old_token(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    settings = _settings()
    async with session_factory() as session:
        service = AuthService(session, settings=settings)
        signup_result = await service.signup(
            name="Test User",
            email="test@example.com",
            password="correct-password",
        )
        old_refresh_token = signup_result["refresh_token"]
        refresh_result = await service.refresh(old_refresh_token)

        assert refresh_result["refresh_token"] != old_refresh_token
        assert refresh_result["access_token"]

    async with session_factory() as verify_session:
        old_token = await _get_refresh_token(verify_session, old_refresh_token)
        new_token = await _get_refresh_token(verify_session, refresh_result["refresh_token"])

    assert old_token.consumed_at is not None
    assert old_token.replaced_by_token_id == new_token.id
    assert new_token.parent_token_id == old_token.id
    assert new_token.family_id == old_token.family_id
    assert new_token.revoked_at is None


async def test_refresh_reuse_invalidates_entire_token_family(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        service = AuthService(session, settings=_settings())
        signup_result = await service.signup(
            name="Test User",
            email="test@example.com",
            password="correct-password",
        )
        old_refresh_token = signup_result["refresh_token"]
        await service.refresh(old_refresh_token)

        with pytest.raises(AuthServiceError) as exc_info:
            await service.refresh(old_refresh_token)

    assert exc_info.value.detail.code == "refresh_reused"

    async with session_factory() as verify_session:
        family_id = (await _get_refresh_token(verify_session, old_refresh_token)).family_id
        family_tokens = (
            await verify_session.execute(
                select(RefreshToken).where(RefreshToken.family_id == family_id)
            )
        ).scalars().all()

    assert len(family_tokens) == 2
    assert all(token.revoked_at is not None for token in family_tokens)
    assert any(token.reuse_detected_at is not None for token in family_tokens)


async def test_concurrent_refresh_reuse_revokes_family_deterministically(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    settings = _settings()
    async with session_factory() as setup_session:
        signup_result = await AuthService(setup_session, settings=settings).signup(
            name="Test User",
            email="test@example.com",
            password="correct-password",
        )
    refresh_token = signup_result["refresh_token"]

    async with session_factory() as lock_session:
        await lock_session.begin()
        locked_token = (
            await lock_session.execute(
                select(RefreshToken)
                .where(RefreshToken.token_hash == hash_refresh_token(refresh_token))
                .with_for_update()
            )
        ).scalar_one()

        started = [asyncio.Event(), asyncio.Event()]

        async def refresh_in_separate_transaction(index: int) -> dict[str, object]:
            async with session_factory() as task_session:
                started[index].set()
                return await AuthService(task_session, settings=settings).refresh(refresh_token)

        first_task = asyncio.create_task(refresh_in_separate_transaction(0))
        second_task = asyncio.create_task(refresh_in_separate_transaction(1))

        await asyncio.wait_for(started[0].wait(), timeout=5)
        await asyncio.wait_for(started[1].wait(), timeout=5)
        await asyncio.sleep(0.2)

        assert not first_task.done()
        assert not second_task.done()

        await lock_session.commit()

    results = await asyncio.wait_for(
        asyncio.gather(first_task, second_task, return_exceptions=True),
        timeout=10,
    )
    successes = [result for result in results if isinstance(result, dict)]
    failures = [result for result in results if isinstance(result, AuthServiceError)]

    assert len(successes) == 1
    assert len(failures) == 1
    assert successes[0]["refresh_token"] != refresh_token
    assert failures[0].detail.code == "refresh_reused"

    async with session_factory() as verify_session:
        family_tokens = (
            await verify_session.execute(
                select(RefreshToken).where(RefreshToken.family_id == locked_token.family_id)
            )
        ).scalars().all()

    assert len(family_tokens) == 2
    assert all(token.revoked_at is not None for token in family_tokens)
    assert any(token.reuse_detected_at is not None for token in family_tokens)


async def test_logout_revokes_token_family_and_blocks_subsequent_refresh(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        service = AuthService(session, settings=_settings())
        signup_result = await service.signup(
            name="Test User",
            email="test@example.com",
            password="correct-password",
        )
        refresh_token = signup_result["refresh_token"]

        assert await service.logout(refresh_token) == {"revoked": True}

        with pytest.raises(AuthServiceError) as exc_info:
            await service.refresh(refresh_token)

    assert exc_info.value.detail.code == "refresh_revoked"

    async with session_factory() as verify_session:
        token = await _get_refresh_token(verify_session, refresh_token)

    assert token.revoked_at is not None


async def test_refresh_rejects_expired_refresh_token(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        service = AuthService(session, settings=_settings())
        signup_result = await service.signup(
            name="Test User",
            email="test@example.com",
            password="correct-password",
        )
        token = (
            await session.execute(
                select(RefreshToken).where(
                    RefreshToken.token_hash == hash_refresh_token(signup_result["refresh_token"])
                )
            )
        ).scalar_one()
        token.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await session.commit()

        with pytest.raises(AuthServiceError) as exc_info:
            await service.refresh(signup_result["refresh_token"])

    assert exc_info.value.detail.to_dict() == {
        "field": "refresh_token",
        "code": "expired_token",
        "message": "Refresh token has expired.",
    }


async def test_refresh_rejects_missing_and_invalid_tokens(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        service = AuthService(session, settings=_settings())

        with pytest.raises(AuthServiceError) as missing_exc_info:
            await service.refresh("")
        with pytest.raises(AuthServiceError) as invalid_exc_info:
            await service.refresh("not-a-real-refresh-token")

    assert missing_exc_info.value.detail.code == "missing_token"
    assert invalid_exc_info.value.detail.code == "invalid_token"


async def test_password_credential_check_constraint_is_enforced_by_database(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        user = User(name="Broken Credential User", email=f"{uuid.uuid4()}@example.com")
        session.add(user)
        await session.flush()
        session.add(
            AuthCredential(
                user_id=user.id,
                provider="password",
                provider_subject=user.email,
                password_hash=None,
            )
        )

        with pytest.raises(IntegrityError):
            await session.flush()


async def test_auth_credential_user_provider_unique_constraint_is_enforced_by_database(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        user = User(name="Duplicate Provider User", email=f"{uuid.uuid4()}@example.com")
        session.add(user)
        await session.flush()
        session.add(
            AuthCredential(
                user_id=user.id,
                provider="password",
                provider_subject=user.email,
                password_hash="hash-one",
            )
        )
        await session.flush()
        session.add(
            AuthCredential(
                user_id=user.id,
                provider="password",
                provider_subject=f"other-{user.email}",
                password_hash="hash-two",
            )
        )

        with pytest.raises(IntegrityError):
            await session.flush()


async def test_auth_credential_provider_subject_unique_constraint_is_enforced_by_database(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    shared_subject = f"{uuid.uuid4()}@example.com"
    async with session_factory() as session:
        first_user = User(name="First Credential User", email=f"first-{shared_subject}")
        second_user = User(name="Second Credential User", email=f"second-{shared_subject}")
        session.add_all([first_user, second_user])
        await session.flush()
        session.add(
            AuthCredential(
                user_id=first_user.id,
                provider="password",
                provider_subject=shared_subject,
                password_hash="hash-one",
            )
        )
        await session.flush()
        session.add(
            AuthCredential(
                user_id=second_user.id,
                provider="password",
                provider_subject=shared_subject,
                password_hash="hash-two",
            )
        )

        with pytest.raises(IntegrityError):
            await session.flush()


async def _get_refresh_token(session: AsyncSession, raw_token: str) -> RefreshToken:
    result = await session.execute(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw_token))
    )
    token = result.scalar_one()
    session.expunge(token)
    return token


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
        JWT_SECRET="auth-service-test-secret-with-at-least-thirty-two-bytes",
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
