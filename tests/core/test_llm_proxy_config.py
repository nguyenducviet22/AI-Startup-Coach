import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_non_local_environment_requires_explicit_proxy_base_url() -> None:
    with pytest.raises(ValidationError, match="LLM_PROXY_BASE_URL is required"):
        Settings(
            _env_file=None,
            APP_ENV="production",
            JWT_SECRET="config-test-secret-with-at-least-thirty-two-bytes",
        )


def test_non_local_does_not_fallback_to_explicit_openrouter_base_url() -> None:
    with pytest.raises(ValidationError, match="LLM_PROXY_BASE_URL is required"):
        Settings(
            _env_file=None,
            APP_ENV="production",
            OPENROUTER_BASE_URL="https://openrouter.ai/api/v1",
            JWT_SECRET="config-test-secret-with-at-least-thirty-two-bytes",
        )


def test_non_local_rejects_placeholder_proxy_model() -> None:
    with pytest.raises(ValidationError, match="LLM_PROXY_MODEL must be explicitly configured"):
        Settings(
            _env_file=None,
            APP_ENV="production",
            LLM_PROXY_BASE_URL="https://9router.example/v1",
            JWT_SECRET="config-test-secret-with-at-least-thirty-two-bytes",
        )


def test_non_local_rejects_placeholder_9router_model() -> None:
    with pytest.raises(ValidationError, match="LLM_PROXY_MODEL must be explicitly configured"):
        Settings(
            _env_file=None,
            APP_ENV="production",
            LLM_PROXY_BASE_URL="https://9router.example/v1",
            LLM_PROXY_MODEL="replace-with-9router-model-id",
            JWT_SECRET="config-test-secret-with-at-least-thirty-two-bytes",
        )


def test_local_environment_defaults_to_local_9router() -> None:
    settings = Settings(
        _env_file=None,
        APP_ENV="local",
        JWT_SECRET="config-test-secret-with-at-least-thirty-two-bytes",
    )

    assert settings.llm_proxy_base_url == "http://localhost:20128/v1"
