import asyncio
import uuid
from typing import Any

from app.core.config import Settings
from app.services.agentops.instrumented_chat_client import InstrumentedChatClient
from app.services.agentops.instrumented_tool_dispatcher import InstrumentedToolDispatcher


async def test_instrumented_chat_client_latency_excludes_metrics_write(monkeypatch) -> None:
    recorded: dict[str, Any] = {}

    async def slow_record_llm_call(**kwargs: Any) -> None:
        recorded.update(kwargs)
        await asyncio.sleep(0.1)

    monkeypatch.setattr(
        "app.services.agentops.instrumented_chat_client.record_llm_call",
        slow_record_llm_call,
    )
    perf_counter_values = iter([1.0, 1.005])
    monkeypatch.setattr(
        "app.services.agentops.instrumented_chat_client.time.perf_counter",
        lambda: next(perf_counter_values),
    )
    wrapped = FakeChatClient(
        response={
            "model": "openai/gpt-4o-mini",
            "usage": {"prompt_tokens": 1000, "completion_tokens": 500, "total_tokens": 1500},
            "choices": [{"message": {"role": "assistant", "content": "Hello"}}],
        }
    )
    client = InstrumentedChatClient(
        wrapped=wrapped,
        turn_id=uuid.uuid4(),
        startup_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        stage="idea",
        settings=_settings(),
    )

    await client.create_chat_completion(messages=[{"role": "user", "content": "Hi"}])

    assert recorded["status"] == "success"
    assert recorded["latency_ms"] == 5
    assert recorded["prompt_tokens"] == 1000
    assert recorded["completion_tokens"] == 500
    assert recorded["total_tokens"] == 1500


async def test_instrumented_chat_client_uses_proxy_model_when_response_omits_model(monkeypatch) -> None:
    recorded: dict[str, Any] = {}

    async def record_llm_call_for_test(**kwargs: Any) -> None:
        recorded.update(kwargs)

    monkeypatch.setattr(
        "app.services.agentops.instrumented_chat_client.record_llm_call",
        record_llm_call_for_test,
    )
    client = InstrumentedChatClient(
        wrapped=FakeChatClient(response={"usage": {}}),
        turn_id=uuid.uuid4(),
        startup_id=uuid.uuid4(),
        session_id=None,
        stage="idea",
        settings=_settings(),
    )

    await client.create_chat_completion(messages=[{"role": "user", "content": "Hi"}])

    assert recorded["model"] == "openai/gpt-4o-mini"


async def test_instrumented_tool_dispatcher_latency_excludes_metrics_write(monkeypatch) -> None:
    recorded: dict[str, Any] = {}

    async def slow_record_tool_call(**kwargs: Any) -> None:
        recorded.update(kwargs)
        await asyncio.sleep(0.1)

    monkeypatch.setattr(
        "app.services.agentops.instrumented_tool_dispatcher.record_tool_call",
        slow_record_tool_call,
    )
    perf_counter_values = iter([2.0, 2.007])
    monkeypatch.setattr(
        "app.services.agentops.instrumented_tool_dispatcher.time.perf_counter",
        lambda: next(perf_counter_values),
    )
    dispatcher = InstrumentedToolDispatcher(
        wrapped=FakeToolDispatcher(result={"ok": True, "tool_name": "check_stage_readiness"}),
        turn_id=uuid.uuid4(),
        startup_id=uuid.uuid4(),
        stage="idea",
    )

    result = await dispatcher.execute(
        tool_name="check_stage_readiness",
        arguments={"current_stage": "idea", "ready": True, "missing_fields": []},
        current_stage="idea",
        startup_id=uuid.uuid4(),
    )

    assert result == {"ok": True, "tool_name": "check_stage_readiness"}
    assert recorded["status"] == "ok"
    assert recorded["latency_ms"] == 7
    assert recorded["tool_name"] == "check_stage_readiness"


class FakeChatClient:
    def __init__(self, response: Any) -> None:
        self.response = response

    async def create_chat_completion(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
    ) -> Any:
        return self.response


class FakeToolDispatcher:
    def __init__(self, result: dict[str, Any]) -> None:
        self.result = result

    async def execute(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any] | str,
        current_stage: str,
        startup_id: uuid.UUID | str | None = None,
    ) -> dict[str, Any]:
        return self.result


def _settings() -> Settings:
    return Settings(
        DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/coaching",
        OPENROUTER_API_KEY="test-key",
        OPENROUTER_BASE_URL="https://openrouter.test/api/v1",
        OPENROUTER_MODEL="test-model",
        LLM_PROXY_API_KEY="proxy-test-key",
        LLM_PROXY_BASE_URL="https://9router.test/v1",
        LLM_PROXY_MODEL="openai/gpt-4o-mini",
        OPENROUTER_HTTP_REFERER="http://localhost:8000",
        OPENROUTER_X_TITLE="AI Startup Coach",
        CHAT_HISTORY_LIMIT=20,
        LLM_MAX_RETRIES=2,
        LLM_RETRY_BACKOFF_SECONDS=0,
        AGENTOPS_PRICING_ENABLED=True,
        JWT_SECRET="instrumentation-test-secret-with-at-least-thirty-two-bytes",
        JWT_ALGORITHM="HS256",
        ACCESS_TOKEN_EXPIRE_MINUTES=30,
        REFRESH_TOKEN_EXPIRE_DAYS=7,
    )
