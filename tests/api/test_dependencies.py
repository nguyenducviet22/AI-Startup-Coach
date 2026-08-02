from app.api.dependencies import get_chat_client
from app.core.config import Settings
from app.llm.openrouter import OpenRouterChatClient


def _settings() -> Settings:
    return Settings(
        JWT_SECRET="dependency-test-secret-with-at-least-thirty-two-bytes",
        LLM_BASE_URL="http://localhost:20128/v1",
        LLM_MODEL="proxy-model",
        LLM_API_KEY="proxy-key",
        OPENROUTER_API_KEY="",
        OPENROUTER_BASE_URL="https://openrouter.test/api/v1/",
        OPENROUTER_MODEL="replace-with-openrouter-model-slug",
        OPENROUTER_MAX_TOKENS=2048,
    )


def test_get_chat_client_uses_request_openrouter_key_without_mutating_global_settings() -> None:
    settings = _settings()

    client = get_chat_client(settings=settings, openrouter_api_key="  sk-user-key  ")

    assert isinstance(client, OpenRouterChatClient)
    assert client.settings.llm_provider == "openrouter"
    assert client.settings.llm_api_key == "sk-user-key"
    assert client.settings.llm_base_url == "https://openrouter.test/api/v1"
    assert client.settings.llm_model == "openrouter/auto"
    assert client.settings.llm_max_tokens == 2048
    assert settings.llm_api_key == "proxy-key"


def test_get_chat_client_keeps_configured_provider_when_request_key_is_missing() -> None:
    settings = _settings()

    client = get_chat_client(settings=settings, openrouter_api_key=None)

    assert isinstance(client, OpenRouterChatClient)
    assert client.settings is settings
    assert client.settings.llm_api_key == "proxy-key"
