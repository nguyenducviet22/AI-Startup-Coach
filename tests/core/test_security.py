from datetime import UTC, datetime, timedelta
import inspect
import uuid

import pytest
import jwt

from app.core import security
from app.core.config import Settings
from app.core.security import (
    TokenExpiredError,
    TokenInvalidError,
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)


def test_hash_password_verifies_original_password() -> None:
    password_hash = hash_password("correct horse battery staple")

    assert password_hash != "correct horse battery staple"
    assert verify_password("correct horse battery staple", password_hash) is True


def test_verify_password_rejects_bad_password() -> None:
    password_hash = hash_password("correct horse battery staple")

    assert verify_password("wrong password", password_hash) is False


def test_refresh_token_generation_and_hashing_never_returns_raw_token() -> None:
    refresh_token = generate_refresh_token()
    token_hash = hash_refresh_token(refresh_token)

    assert len(refresh_token) >= 64
    assert token_hash != refresh_token
    assert len(token_hash) == 64
    assert hash_refresh_token(refresh_token) == token_hash


def test_create_and_decode_valid_access_token() -> None:
    settings = _settings(jwt_secret="first-secret-with-at-least-thirty-two-bytes", access_token_expire_minutes=30)
    user_id = uuid.uuid4()

    token = create_access_token(user_id, settings=settings)
    payload = decode_access_token(token, settings=settings)

    assert payload["sub"] == str(user_id)
    assert payload["type"] == "access"


def test_decode_access_token_rejects_expired_token() -> None:
    settings = _settings(access_token_expire_minutes=30)
    token = create_access_token(
        uuid.uuid4(),
        settings=settings,
        now=datetime.now(UTC) - timedelta(minutes=31),
    )

    with pytest.raises(TokenExpiredError):
        decode_access_token(token, settings=settings)


def test_decode_access_token_rejects_invalid_token() -> None:
    with pytest.raises(TokenInvalidError):
        decode_access_token("not-a-jwt", settings=_settings())


def test_decode_access_token_rejects_non_access_token_type() -> None:
    settings = _settings()
    refresh_type_token = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "type": "refresh",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    missing_type_token = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(TokenInvalidError):
        decode_access_token(refresh_type_token, settings=settings)
    with pytest.raises(TokenInvalidError):
        decode_access_token(missing_type_token, settings=settings)


def test_security_reads_jwt_values_from_settings_without_hardcoded_fallback() -> None:
    user_id = uuid.uuid4()
    first_settings = _settings(
        jwt_secret="first-secret-with-at-least-thirty-two-bytes",
        access_token_expire_minutes=5,
    )
    second_settings = _settings(
        jwt_secret="second-secret-with-at-least-thirty-two-bytes",
        access_token_expire_minutes=60,
    )

    token = create_access_token(user_id, settings=first_settings)

    assert decode_access_token(token, settings=first_settings)["sub"] == str(user_id)
    with pytest.raises(TokenInvalidError):
        decode_access_token(token, settings=second_settings)

    security_source = inspect.getsource(security)
    assert "first-secret-with-at-least-thirty-two-bytes" not in security_source
    assert "second-secret-with-at-least-thirty-two-bytes" not in security_source
    assert "ACCESS_TOKEN_EXPIRE_MINUTES" not in security_source


def _settings(
    *,
    jwt_secret: str = "unit-test-secret-with-at-least-thirty-two-bytes",
    jwt_algorithm: str = "HS256",
    access_token_expire_minutes: int = 30,
    refresh_token_expire_days: int = 7,
) -> Settings:
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
        JWT_SECRET=jwt_secret,
        JWT_ALGORITHM=jwt_algorithm,
        ACCESS_TOKEN_EXPIRE_MINUTES=access_token_expire_minutes,
        REFRESH_TOKEN_EXPIRE_DAYS=refresh_token_expire_days,
    )
