import json
from typing import Any

from app.core.config import Settings
from app.llm.openrouter import LLMProviderError
from app.services.context_builder import StartupContext
from app.services.orchestrator import AgentOrchestrator


class FakeChatClient:
    def __init__(self, responses: list[Any]) -> None:
        self.responses = responses
        self.requests: list[dict[str, Any]] = []

    async def create_chat_completion(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
    ) -> Any:
        self.requests.append({"messages": messages, "tools": tools, "model": model})
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class FakeSkillLoader:
    def load(self, current_stage: str) -> str:
        return f"skill for {current_stage}"


async def test_orchestrator_calls_llm_with_stage_filtered_tools() -> None:
    client = FakeChatClient([_response("Ask one sharper customer question.")])
    orchestrator = AgentOrchestrator(chat_client=client, skill_loader=FakeSkillLoader(), settings=_settings())

    result = await orchestrator.handle_message(
        startup=StartupContext("startup-1", "user-1", "idea", "TutorOS"),
        history=[],
        user_message="I want to build tools for tutors.",
    )

    assert result == "Ask one sharper customer question."
    assert [tool["function"]["name"] for tool in client.requests[0]["tools"]] == [
        "check_stage_readiness"
    ]
    assert client.requests[0]["messages"][0]["role"] == "system"
    assert "skill for idea" in client.requests[0]["messages"][0]["content"]


async def test_orchestrator_preserves_markdown_and_newlines_from_llm() -> None:
    content = (
        "Great start with SkillBridge!\n\n"
        "1. **Origin**  \n"
        "   Where did this idea come from?\n\n"
        "What inspired you to create SkillBridge?"
    )
    client = FakeChatClient([_response(content)])
    orchestrator = AgentOrchestrator(chat_client=client, skill_loader=FakeSkillLoader(), settings=_settings())

    result = await orchestrator.handle_message(
        startup=StartupContext("startup-1", "user-1", "idea", "SkillBridge"),
        history=[],
        user_message="I want to help students build skills.",
    )

    assert result == content


async def test_orchestrator_handles_tool_calls_and_returns_final_response() -> None:
    client = FakeChatClient(
        [
            _response(
                None,
                tool_calls=[
                    _tool_call(
                        "call-1",
                        "generate_lean_canvas",
                        {
                            "problem": "Tutors lose time coordinating lessons.",
                            "solution": "Scheduling automation.",
                            "unique_value_proposition": "Calendar ops for tutoring teams.",
                            "customer_segments": "Independent tutoring centers.",
                        },
                    )
                ],
            ),
            _response("I drafted the lean canvas fields from what you shared."),
        ]
    )
    orchestrator = AgentOrchestrator(chat_client=client, skill_loader=FakeSkillLoader(), settings=_settings())

    result = await orchestrator.handle_message(
        startup=StartupContext("startup-1", "user-1", "lean_canvas", "TutorOS"),
        history=[{"role": "assistant", "content": "Earlier context"}],
        user_message="Draft the canvas.",
        current_document={"problem": "initial"},
    )

    assert result == "I drafted the lean canvas fields from what you shared."
    assert len(client.requests) == 2
    tool_result = client.requests[1]["messages"][-1]
    assert tool_result["role"] == "tool"
    assert tool_result["tool_call_id"] == "call-1"
    payload = json.loads(tool_result["content"])
    assert payload["ok"] is True
    assert payload["persistence"]["status"] == "deferred"


async def test_orchestrator_processes_multiple_tool_calls_before_final_response() -> None:
    client = FakeChatClient(
        [
            _response(
                None,
                tool_calls=[
                    _tool_call(
                        "call-canvas",
                        "generate_lean_canvas",
                        {
                            "problem": "Tutors lose time coordinating lessons.",
                            "solution": "Scheduling automation.",
                            "unique_value_proposition": "Calendar ops for tutoring teams.",
                            "customer_segments": "Independent tutoring centers.",
                        },
                    ),
                    _tool_call(
                        "call-readiness",
                        "check_stage_readiness",
                        {"current_stage": "lean_canvas", "ready": True, "missing_fields": []},
                    ),
                ],
            ),
            _response("I drafted the canvas and you have enough to confirm moving on."),
        ]
    )
    orchestrator = AgentOrchestrator(chat_client=client, skill_loader=FakeSkillLoader(), settings=_settings())

    result = await orchestrator.handle_message(
        startup=StartupContext("startup-1", "user-1", "lean_canvas", "TutorOS"),
        history=[],
        user_message="Draft the canvas and check readiness.",
    )

    assert result == "I drafted the canvas and you have enough to confirm moving on."
    assert len(client.requests) == 2

    second_call_messages = client.requests[1]["messages"]
    tool_result_messages = [
        message for message in second_call_messages if message["role"] == "tool"
    ]
    assert [message["tool_call_id"] for message in tool_result_messages] == [
        "call-canvas",
        "call-readiness",
    ]
    assert [json.loads(message["content"])["tool_name"] for message in tool_result_messages] == [
        "generate_lean_canvas",
        "check_stage_readiness",
    ]
    assert tool_result_messages == second_call_messages[-2:]


async def test_orchestrator_exposes_stage_readiness_from_tool_result() -> None:
    client = FakeChatClient(
        [
            _response(
                None,
                tool_calls=[
                    _tool_call(
                        "call-readiness",
                        "check_stage_readiness",
                        {"current_stage": "idea", "ready": True, "missing_fields": []},
                    ),
                ],
            ),
            _response("You have enough to move forward. Shall we advance?"),
        ]
    )
    orchestrator = AgentOrchestrator(chat_client=client, skill_loader=FakeSkillLoader(), settings=_settings())

    result = await orchestrator.handle_turn(
        startup=StartupContext("startup-1", "user-1", "idea"),
        history=[],
        user_message="Is this enough?",
    )

    assert result.content == "You have enough to move forward. Shall we advance?"
    assert result.stage_readiness == {"ready": True, "missing_fields": []}


async def test_orchestrator_ignores_invalid_stage_readiness_tool_result() -> None:
    client = FakeChatClient(
        [
            _response(
                None,
                tool_calls=[
                    _tool_call(
                        "call-readiness",
                        "check_stage_readiness",
                        {"current_stage": "not-a-stage", "ready": True, "missing_fields": []},
                    ),
                ],
            ),
            _response("I need to re-check the stage details."),
        ]
    )
    orchestrator = AgentOrchestrator(chat_client=client, skill_loader=FakeSkillLoader(), settings=_settings())

    result = await orchestrator.handle_turn(
        startup=StartupContext("startup-1", "user-1", "idea"),
        history=[],
        user_message="Is this enough?",
    )

    assert result.content == "I need to re-check the stage details."
    assert result.stage_readiness is None
    payload = json.loads(client.requests[1]["messages"][-1]["content"])
    assert payload["ok"] is False


async def test_orchestrator_uses_last_stage_readiness_tool_result() -> None:
    client = FakeChatClient(
        [
            _response(
                None,
                tool_calls=[
                    _tool_call(
                        "call-readiness-first",
                        "check_stage_readiness",
                        {
                            "current_stage": "lean_canvas",
                            "ready": False,
                            "missing_fields": ["channels"],
                        },
                    ),
                    _tool_call(
                        "call-canvas",
                        "generate_lean_canvas",
                        {
                            "problem": "Tutors lose time coordinating lessons.",
                            "solution": "Scheduling automation.",
                            "unique_value_proposition": "Calendar ops for tutoring teams.",
                            "customer_segments": "Independent tutoring centers.",
                            "channels": "Tutor communities.",
                        },
                    ),
                    _tool_call(
                        "call-readiness-last",
                        "check_stage_readiness",
                        {"current_stage": "lean_canvas", "ready": True, "missing_fields": []},
                    ),
                ],
            ),
            _response("I updated the canvas and it is ready."),
        ]
    )
    orchestrator = AgentOrchestrator(chat_client=client, skill_loader=FakeSkillLoader(), settings=_settings())

    result = await orchestrator.handle_turn(
        startup=StartupContext("startup-1", "user-1", "lean_canvas"),
        history=[],
        user_message="Update and check readiness.",
    )

    assert result.stage_readiness == {"ready": True, "missing_fields": []}


async def test_orchestrator_returns_no_stage_readiness_for_non_readiness_tool_call() -> None:
    client = FakeChatClient(
        [
            _response(
                None,
                tool_calls=[
                    _tool_call(
                        "call-canvas",
                        "generate_lean_canvas",
                        {
                            "problem": "Tutors lose time coordinating lessons.",
                            "solution": "Scheduling automation.",
                            "unique_value_proposition": "Calendar ops for tutoring teams.",
                            "customer_segments": "Independent tutoring centers.",
                        },
                    ),
                ],
            ),
            _response("I drafted the canvas."),
        ]
    )
    orchestrator = AgentOrchestrator(chat_client=client, skill_loader=FakeSkillLoader(), settings=_settings())

    result = await orchestrator.handle_turn(
        startup=StartupContext("startup-1", "user-1", "lean_canvas"),
        history=[],
        user_message="Draft the canvas.",
    )

    assert result.stage_readiness is None


async def test_orchestrator_returns_tool_validation_error_to_model_for_self_correction() -> None:
    client = FakeChatClient(
        [
            _response(
                None,
                tool_calls=[_tool_call("call-1", "generate_swot", {"strengths": []})],
            ),
            _response("I need the missing SWOT fields before drafting."),
        ]
    )
    orchestrator = AgentOrchestrator(chat_client=client, skill_loader=FakeSkillLoader(), settings=_settings())

    result = await orchestrator.handle_message(
        startup=StartupContext("startup-1", "user-1", "swot"),
        history=[],
        user_message="Make a SWOT.",
    )

    assert result == "I need the missing SWOT fields before drafting."
    payload = json.loads(client.requests[1]["messages"][-1]["content"])
    assert payload["ok"] is False
    assert payload["error"]["type"] == "tool_validation_error"


async def test_orchestrator_does_not_advance_stage_when_readiness_is_true() -> None:
    client = FakeChatClient(
        [
            _response(
                None,
                tool_calls=[
                    _tool_call(
                        "call-1",
                        "check_stage_readiness",
                        {"current_stage": "idea", "ready": True, "missing_fields": []},
                    )
                ],
            ),
            _response("You have enough to move forward. Shall we advance?"),
        ]
    )
    startup = StartupContext("startup-1", "user-1", "idea")
    orchestrator = AgentOrchestrator(chat_client=client, skill_loader=FakeSkillLoader(), settings=_settings())

    result = await orchestrator.handle_message(
        startup=startup,
        history=[],
        user_message="I think the idea is clear.",
    )

    assert result == "You have enough to move forward. Shall we advance?"
    assert startup.current_stage == "idea"
    payload = json.loads(client.requests[1]["messages"][-1]["content"])
    assert payload["arguments"]["ready"] is True
    assert payload["persistence"]["status"] == "deferred"


async def test_orchestrator_returns_friendly_message_on_llm_provider_error() -> None:
    client = FakeChatClient(
        [
            LLMProviderError(
                "provider down",
                "The AI coach is temporarily unavailable. Please try again in a moment.",
            )
        ]
    )
    orchestrator = AgentOrchestrator(chat_client=client, skill_loader=FakeSkillLoader(), settings=_settings())

    result = await orchestrator.handle_message(
        startup=StartupContext("startup-1", "user-1", "idea"),
        history=[],
        user_message="hello",
    )

    assert result == "The AI coach is temporarily unavailable. Please try again in a moment."


def _response(content: str | None, tool_calls: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": content,
                    "tool_calls": tool_calls,
                }
            }
        ]
    }


def _tool_call(call_id: str, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": call_id,
        "type": "function",
        "function": {
            "name": name,
            "arguments": json.dumps(arguments),
        },
    }


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
        JWT_SECRET="orchestrator-test-secret-with-at-least-thirty-two-bytes",
        JWT_ALGORITHM="HS256",
        ACCESS_TOKEN_EXPIRE_MINUTES=30,
        REFRESH_TOKEN_EXPIRE_DAYS=7,
    )
