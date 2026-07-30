import json
from dataclasses import dataclass
from typing import Any

from app.llm.openrouter import ChatCompletionClient, LLMProviderError
from app.services.context_builder import StartupContext, build_context_messages
from app.services.skill_loader import SkillLoader
from app.services.stage_tools import get_openai_tools_for_stage
from app.services.tool_dispatcher import ToolDispatcher


@dataclass(frozen=True)
class OrchestratorResult:
    content: str
    tool_messages: list[dict[str, Any]]
    tool_call_data: list[dict[str, Any]]


class AgentOrchestrator:
    def __init__(
        self,
        *,
        chat_client: ChatCompletionClient,
        tool_dispatcher: ToolDispatcher | None = None,
        skill_loader: SkillLoader | None = None,
    ) -> None:
        self.chat_client = chat_client
        self.tool_dispatcher = tool_dispatcher or ToolDispatcher()
        self.skill_loader = skill_loader or SkillLoader()

    async def handle_message(
        self,
        *,
        startup: StartupContext,
        history: list[dict[str, Any]],
        user_message: str,
        current_document: Any | None = None,
    ) -> str:
        result = await self.handle_turn(
            startup=startup,
            history=history,
            user_message=user_message,
            current_document=current_document,
        )
        return result.content

    async def handle_turn(
        self,
        *,
        startup: StartupContext,
        history: list[dict[str, Any]],
        user_message: str,
        current_document: Any | None = None,
    ) -> OrchestratorResult:
        messages = build_context_messages(
            startup=startup,
            history=history,
            user_message=user_message,
            current_document=current_document,
            skill_loader=self.skill_loader,
        )
        tools = get_openai_tools_for_stage(startup.current_stage)

        try:
            response = await self.chat_client.create_chat_completion(messages=messages, tools=tools)
            assistant_message = _first_assistant_message(response)
            tool_calls = _message_tool_calls(assistant_message)
            tool_messages: list[dict[str, Any]] = []
            tool_call_data: list[dict[str, Any]] = []

            if tool_calls:
                messages.append(_assistant_message_for_history(assistant_message))
                for tool_call in tool_calls:
                    result = await self.tool_dispatcher.execute(
                        tool_name=_tool_call_name(tool_call),
                        arguments=_tool_call_arguments(tool_call),
                        current_stage=startup.current_stage,
                        startup_id=startup.startup_id,
                    )
                    tool_message = _tool_result_message(_tool_call_id(tool_call), result)
                    messages.append(tool_message)
                    tool_messages.append(tool_message)
                    tool_call_data.append(
                        {
                            "tool_call_id": _tool_call_id(tool_call),
                            "tool_name": _tool_call_name(tool_call),
                            "result": result,
                        }
                    )

                response = await self.chat_client.create_chat_completion(messages=messages)
                assistant_message = _first_assistant_message(response)

            return OrchestratorResult(
                content=_message_content(assistant_message) or "",
                tool_messages=tool_messages,
                tool_call_data=tool_call_data,
            )
        except LLMProviderError as exc:
            return OrchestratorResult(
                content=exc.student_message,
                tool_messages=[],
                tool_call_data=[],
            )


def _first_assistant_message(response: Any) -> Any:
    return _get(_get(response, "choices")[0], "message")


def _assistant_message_for_history(message: Any) -> dict[str, Any]:
    history_message: dict[str, Any] = {"role": "assistant", "content": _message_content(message)}
    tool_calls = _message_tool_calls(message)
    if tool_calls:
        history_message["tool_calls"] = tool_calls
    return history_message


def _tool_result_message(tool_call_id: str, result: dict[str, Any]) -> dict[str, Any]:
    return {
        "role": "tool",
        "tool_call_id": tool_call_id,
        "content": json.dumps(result, ensure_ascii=True, sort_keys=True),
    }


def _message_content(message: Any) -> str | None:
    return _get(message, "content")


def _message_tool_calls(message: Any) -> list[Any]:
    return _get(message, "tool_calls") or []


def _tool_call_id(tool_call: Any) -> str:
    return _get(tool_call, "id")


def _tool_call_name(tool_call: Any) -> str:
    return _get(_get(tool_call, "function"), "name")


def _tool_call_arguments(tool_call: Any) -> str:
    return _get(_get(tool_call, "function"), "arguments")


def _get(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value[key]
    return getattr(value, key)
