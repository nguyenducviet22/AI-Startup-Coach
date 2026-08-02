import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_llm_variables_are_primary_over_legacy_values() -> None:
    settings = Settings(
        _env_file=None,
        APP_ENV="local",
        LLM_PROVIDER="9router",
        LLM_BASE_URL="http://localhost:20128/v1/",
        LLM_API_KEY="",
        LLM_MODEL="openai/gpt-4o-mini",
        LLM_PROXY_BASE_URL="https://legacy.example/v1",
        LLM_PROXY_API_KEY="legacy-key",
        LLM_PROXY_MODEL="legacy-model",
        JWT_SECRET="config-test-secret-with-at-least-thirty-two-bytes",
    )

    assert settings.llm_provider == "9router"
    assert settings.llm_base_url == "http://localhost:20128/v1"
    assert settings.llm_api_key == ""
    assert settings.llm_model == "openai/gpt-4o-mini"


def test_non_local_environment_requires_explicit_llm_base_url() -> None:
    with pytest.raises(ValidationError, match="LLM_BASE_URL is required"):
        Settings(
            _env_file=None,
            APP_ENV="production",
            JWT_SECRET="config-test-secret-with-at-least-thirty-two-bytes",
        )


def test_non_local_accepts_legacy_openrouter_base_url_as_fallback() -> None:
    settings = Settings(
        _env_file=None,
        APP_ENV="production",
        OPENROUTER_BASE_URL="https://openrouter.ai/api/v1",
        LLM_MODEL="openai/gpt-4o-mini",
        JWT_SECRET="config-test-secret-with-at-least-thirty-two-bytes",
    )
    assert settings.llm_base_url == "https://openrouter.ai/api/v1"


def test_non_local_rejects_missing_llm_model() -> None:
    with pytest.raises(ValidationError, match="LLM_MODEL must be explicitly configured"):
        Settings(
            _env_file=None,
            APP_ENV="production",
            OPENROUTER_BASE_URL="https://openrouter.ai/api/v1",
            JWT_SECRET="config-test-secret-with-at-least-thirty-two-bytes",
        )


def test_non_local_rejects_placeholder_proxy_model() -> None:
    with pytest.raises(ValidationError, match="LLM_MODEL must be explicitly configured"):
        Settings(
            _env_file=None,
            APP_ENV="production",
            LLM_PROXY_BASE_URL="https://9router.example/v1",
            JWT_SECRET="config-test-secret-with-at-least-thirty-two-bytes",
        )


def test_non_local_rejects_placeholder_9router_model() -> None:
    with pytest.raises(ValidationError, match="LLM_MODEL must be explicitly configured"):
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

    assert settings.llm_base_url == "http://localhost:20128/v1"
