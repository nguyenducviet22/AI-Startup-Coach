from typing import Any

import httpx
import pytest
from openai import APIStatusError, APITimeoutError

from app.core.config import Settings
from app.llm.openrouter import LLMProviderError, OpenRouterChatClient


class FakeCompletions:
    def __init__(self, outcomes: list[Any]) -> None:
        self.outcomes = outcomes
        self.requests: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> Any:
        self.requests.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FakeChat:
    def __init__(self, completions: FakeCompletions) -> None:
        self.completions = completions


class FakeClient:
    def __init__(self, completions: FakeCompletions) -> None:
        self.chat = FakeChat(completions)


async def fake_sleep(_: float) -> None:
    return None


async def test_openrouter_client_sends_configured_model_messages_and_tools() -> None:
    completions = FakeCompletions(outcomes=[{"ok": True}])
    client = OpenRouterChatClient(
        settings=_settings(),
        client=FakeClient(completions),
        sleep=fake_sleep,
    )

    response = await client.create_chat_completion(
        messages=[{"role": "user", "content": "hello"}],
        tools=[{"type": "function", "function": {"name": "check_stage_readiness"}}],
    )

    assert response == {"ok": True}
    assert completions.requests == [
        {
            "model": "configured-model",
            "messages": [{"role": "user", "content": "hello"}],
            "tools": [{"type": "function", "function": {"name": "check_stage_readiness"}}],
        }
    ]


async def test_openrouter_client_retries_timeout_then_succeeds() -> None:
    timeout = APITimeoutError(request=None)
    completions = FakeCompletions(outcomes=[timeout, timeout, {"ok": True}])
    client = OpenRouterChatClient(
        settings=_settings(llm_max_retries=2),
        client=FakeClient(completions),
        sleep=fake_sleep,
    )

    response = await client.create_chat_completion(messages=[{"role": "user", "content": "hello"}])

    assert response == {"ok": True}
    assert len(completions.requests) == 3


async def test_openrouter_client_retries_transient_status_then_succeeds() -> None:
    completions = FakeCompletions(outcomes=[_api_status_error(503), {"ok": True}])
    client = OpenRouterChatClient(
        settings=_settings(llm_max_retries=2),
        client=FakeClient(completions),
        sleep=fake_sleep,
    )

    response = await client.create_chat_completion(messages=[{"role": "user", "content": "hello"}])

    assert response == {"ok": True}
    assert len(completions.requests) == 2


async def test_openrouter_client_does_not_retry_non_transient_status() -> None:
    completions = FakeCompletions(outcomes=[_api_status_error(401)])
    client = OpenRouterChatClient(
        settings=_settings(llm_max_retries=2),
        client=FakeClient(completions),
        sleep=fake_sleep,
    )

    with pytest.raises(LLMProviderError):
        await client.create_chat_completion(messages=[{"role": "user", "content": "hello"}])

    assert len(completions.requests) == 1


async def test_openrouter_client_raises_provider_error_after_retries_are_exhausted() -> None:
    completions = FakeCompletions(
        outcomes=[
            APITimeoutError(request=None),
            APITimeoutError(request=None),
            APITimeoutError(request=None),
        ]
    )
    client = OpenRouterChatClient(
        settings=_settings(llm_max_retries=2),
        client=FakeClient(completions),
        sleep=fake_sleep,
    )

    with pytest.raises(LLMProviderError) as exc_info:
        await client.create_chat_completion(messages=[{"role": "user", "content": "hello"}])

    assert len(completions.requests) == 3
    assert "temporarily unavailable" in exc_info.value.student_message


def test_openrouter_client_constructs_sdk_client_from_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class CapturingAsyncOpenAI:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)
            self.chat = FakeChat(FakeCompletions(outcomes=[]))

    monkeypatch.setattr("app.llm.openrouter.AsyncOpenAI", CapturingAsyncOpenAI)

    OpenRouterChatClient(settings=_settings())

    assert captured == {
        "api_key": "test-key",
        "base_url": "https://openrouter.test/api/v1",
        "default_headers": {
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": "AI Startup Coach",
        },
    }


def _settings(llm_max_retries: int = 2) -> Settings:
    return Settings(
        DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/coaching",
        OPENROUTER_API_KEY="test-key",
        OPENROUTER_BASE_URL="https://openrouter.test/api/v1",
        OPENROUTER_MODEL="configured-model",
        OPENROUTER_HTTP_REFERER="http://localhost:8000",
        OPENROUTER_X_TITLE="AI Startup Coach",
        CHAT_HISTORY_LIMIT=20,
        LLM_MAX_RETRIES=llm_max_retries,
        LLM_RETRY_BACKOFF_SECONDS=0,
    )


def _api_status_error(status_code: int) -> APIStatusError:
    request = httpx.Request("POST", "https://openrouter.test/api/v1/chat/completions")
    response = httpx.Response(status_code=status_code, request=request)
    return APIStatusError("transient provider failure", response=response, body=None)
