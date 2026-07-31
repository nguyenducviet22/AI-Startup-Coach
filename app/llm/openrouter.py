import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    OpenAIError,
    RateLimitError,
)

from app.core.config import Settings, get_settings

TRANSIENT_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}
RETRYABLE_EXCEPTIONS = (APITimeoutError, APIConnectionError, RateLimitError)


class ChatCompletionClient(Protocol):
    async def create_chat_completion(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
    ) -> Any:
        ...


class LLMProviderError(RuntimeError):
    def __init__(self, message: str, student_message: str) -> None:
        self.student_message = student_message
        super().__init__(message)


class OpenRouterChatClient:
    def __init__(
        self,
        settings: Settings | None = None,
        client: Any | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.settings = settings or get_settings()
        self.model = self.settings.openrouter_model
        self.max_retries = self.settings.llm_max_retries
        self.backoff_seconds = self.settings.llm_retry_backoff_seconds
        self._sleep = sleep
        self._client = client or AsyncOpenAI(
            api_key=self.settings.openrouter_api_key,
            base_url=self.settings.openrouter_base_url,
            default_headers=self._default_headers(),
        )

    async def create_chat_completion(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
    ) -> Any:
        request: dict[str, Any] = {
            "model": model or self.model,
            "messages": messages,
            "max_tokens": self.settings.openrouter_max_tokens,
        }
        if tools is not None:
            request["tools"] = tools

        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                return await self._client.chat.completions.create(**request)
            except RETRYABLE_EXCEPTIONS as exc:
                last_error = exc
                if not self._can_retry(attempt):
                    break
                await self._sleep(self._retry_delay(attempt))
            except APIStatusError as exc:
                last_error = exc
                if not self._is_transient_status(exc) or not self._can_retry(attempt):
                    break
                await self._sleep(self._retry_delay(attempt))
            except OpenAIError as exc:
                raise self._provider_error(exc) from exc

        raise self._provider_error(last_error)

    def _default_headers(self) -> dict[str, str]:
        headers = {}
        if self.settings.openrouter_http_referer:
            headers["HTTP-Referer"] = self.settings.openrouter_http_referer
        if self.settings.openrouter_x_title:
            headers["X-Title"] = self.settings.openrouter_x_title
        return headers

    def _can_retry(self, attempt: int) -> bool:
        return attempt < self.max_retries

    def _retry_delay(self, attempt: int) -> float:
        return self.backoff_seconds * (2**attempt)

    @staticmethod
    def _is_transient_status(exc: APIStatusError) -> bool:
        return exc.status_code in TRANSIENT_STATUS_CODES

    @staticmethod
    def _provider_error(exc: Exception | None) -> LLMProviderError:
        detail = str(exc) if exc else "Unknown provider error."
        return LLMProviderError(
            f"LLM provider request failed after retries: {detail}",
            "The AI coach is temporarily unavailable. Please try again in a moment.",
        )
