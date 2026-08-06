from datetime import UTC, date, datetime
from typing import Any

import httpx
import pytest

from app.core.config import Settings
from app.research.errors import ResearchProviderError
from app.research.protocol import ResearchProvider
from app.research.tavily import TavilyResearchProvider


class FakeHttpClient:
    def __init__(self, outcomes: list[Any]) -> None:
        self.outcomes = outcomes
        self.requests: list[dict[str, Any]] = []

    async def post(self, path: str, **kwargs: Any) -> httpx.Response:
        self.requests.append({"path": path, **kwargs})
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


async def no_sleep(_: float) -> None:
    return None


async def test_search_normalizes_evidence_and_disables_generated_answer() -> None:
    http = FakeHttpClient(
        [
            _response(
                200,
                {
                    "request_id": "search-123",
                    "usage": {"credits": 1},
                    "results": [
                        {
                            "url": "https://www.example.gov/rule",
                            "title": "Official rule",
                            "content": "source text",
                        }
                    ],
                },
            )
        ]
    )
    adapter = TavilyResearchProvider(settings=_settings(), http_client=http, sleep=no_sleep)

    result = await adapter.search(
        query="licensing",
        topic="legal",
        search_depth="basic",
        max_results=5,
        include_domains=["example.gov"],
        start_date=None,
        end_date=None,
    )

    assert http.requests[0]["path"] == "/search"
    assert http.requests[0]["json"]["include_answer"] is False
    assert result.request_id == "search-123"
    assert result.credits_used == 1
    assert str(result.evidence[0].url) == "https://www.example.gov/rule"
    assert result.evidence[0].legal_or_regulatory is True
    assert result.evidence[0].authority.value == "official"
    assert result.evidence[0].retrieved_at.tzinfo == UTC


async def test_search_normalizes_news_publication_date() -> None:
    http = FakeHttpClient(
        [
            _response(
                200,
                {
                    "results": [
                        {
                            "url": "https://news.example.com/story",
                            "title": "News",
                            "content": "reporting",
                            "published_date": "2026-08-01T12:30:00Z",
                        }
                    ]
                },
            )
        ]
    )
    adapter = TavilyResearchProvider(settings=_settings(), http_client=http)

    result = await adapter.search(
        query="funding",
        topic="news",
        search_depth="basic",
        max_results=1,
        include_domains=[],
        start_date=date(2026, 8, 1),
        end_date=None,
    )

    assert result.evidence[0].published_at == datetime(2026, 8, 1, 12, 30, tzinfo=UTC)
    assert http.requests[0]["json"]["start_date"] == "2026-08-01"


async def test_extract_normalizes_valid_urls_and_rejects_malformed_provider_urls() -> None:
    http = FakeHttpClient(
        [
            _response(
                200,
                {
                    "request_id": "extract-123",
                    "results": [
                        {"url": "ftp://invalid.example/file", "content": "not evidence"},
                        {
                            "url": "https://founder.example/about",
                            "title": "About",
                            "content": "A" * 1_100,
                        },
                    ],
                },
            )
        ]
    )
    adapter = TavilyResearchProvider(settings=_settings(), http_client=http)

    result = await adapter.extract(
        urls=["ftp://bad.example/file", "https://founder.example/about"],
        query=None,
        extract_depth="basic",
    )

    assert http.requests[0]["json"]["urls"] == ["https://founder.example/about"]
    assert len(result.evidence) == 1
    assert str(result.evidence[0].url) == "https://founder.example/about"
    assert len(result.evidence[0].excerpt) == 1_000


async def test_extract_rejects_only_malformed_urls_before_request() -> None:
    http = FakeHttpClient([])
    adapter = TavilyResearchProvider(settings=_settings(), http_client=http)

    with pytest.raises(ResearchProviderError) as exc_info:
        await adapter.extract(urls=["javascript:alert(1)", "not-a-url"], query=None, extract_depth="basic")

    assert exc_info.value.code == "provider_malformed_response"
    assert http.requests == []


async def test_timeout_is_sanitized_after_retry() -> None:
    http = FakeHttpClient([httpx.ReadTimeout("upstream secret"), httpx.ReadTimeout("upstream secret")])
    adapter = TavilyResearchProvider(settings=_settings(RESEARCH_PROVIDER_MAX_RETRIES=1), http_client=http, sleep=no_sleep)

    with pytest.raises(ResearchProviderError) as exc_info:
        await adapter.search(
            query="market",
            topic="general",
            search_depth="basic",
            max_results=1,
            include_domains=[],
            start_date=None,
            end_date=None,
        )

    assert exc_info.value.code == "provider_timeout"
    assert "secret" not in str(exc_info.value)
    assert len(http.requests) == 2


async def test_rate_limit_is_sanitized_without_retry() -> None:
    http = FakeHttpClient([_response(429, {"detail": "upstream secret"})])
    adapter = TavilyResearchProvider(settings=_settings(RESEARCH_PROVIDER_MAX_RETRIES=1), http_client=http)

    with pytest.raises(ResearchProviderError) as exc_info:
        await adapter.search(
            query="market",
            topic="general",
            search_depth="basic",
            max_results=1,
            include_domains=[],
            start_date=None,
            end_date=None,
        )

    assert exc_info.value.code == "provider_rate_limited"
    assert len(http.requests) == 1


async def test_rejected_request_is_sanitized_without_retry() -> None:
    http = FakeHttpClient([_response(401, {"detail": "revoked key"})])
    adapter = TavilyResearchProvider(settings=_settings(RESEARCH_PROVIDER_MAX_RETRIES=1), http_client=http)

    with pytest.raises(ResearchProviderError) as exc_info:
        await adapter.search(
            query="market",
            topic="general",
            search_depth="basic",
            max_results=1,
            include_domains=[],
            start_date=None,
            end_date=None,
        )

    assert exc_info.value.code == "provider_request_rejected"
    assert len(http.requests) == 1


async def test_transient_unavailable_response_retries() -> None:
    http = FakeHttpClient([_response(503, {}), _response(503, {})])
    adapter = TavilyResearchProvider(
        settings=_settings(RESEARCH_PROVIDER_MAX_RETRIES=1),
        http_client=http,
        sleep=no_sleep,
    )

    with pytest.raises(ResearchProviderError) as exc_info:
        await adapter.search(
            query="market",
            topic="general",
            search_depth="basic",
            max_results=1,
            include_domains=[],
            start_date=None,
            end_date=None,
        )

    assert exc_info.value.code == "provider_unavailable"
    assert len(http.requests) == 2


async def test_absent_api_key_is_sanitized_without_request() -> None:
    http = FakeHttpClient([])
    adapter = TavilyResearchProvider(settings=_settings(TAVILY_API_KEY=""), http_client=http)

    with pytest.raises(ResearchProviderError) as exc_info:
        await adapter.search(
            query="market",
            topic="general",
            search_depth="basic",
            max_results=1,
            include_domains=[],
            start_date=None,
            end_date=None,
        )

    assert exc_info.value.code == "provider_missing_key"
    assert http.requests == []


def test_fake_provider_can_implement_the_stable_protocol() -> None:
    class FakeResearchProvider:
        async def search(self, **_: Any) -> Any:
            raise NotImplementedError

        async def extract(self, **_: Any) -> Any:
            raise NotImplementedError

    assert isinstance(FakeResearchProvider(), ResearchProvider)


def _response(status_code: int, payload: dict[str, Any]) -> httpx.Response:
    request = httpx.Request("POST", "https://research.example")
    return httpx.Response(status_code, json=payload, request=request)


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "_env_file": None,
        "JWT_SECRET": "research-test-secret-with-at-least-thirty-two-bytes",
        "LLM_BASE_URL": "http://localhost:20128/v1",
        "LLM_MODEL": "proxy-model",
        "LLM_API_KEY": "proxy-key",
        "TAVILY_API_KEY": "test-key",
        "TAVILY_BASE_URL": "https://research.example",
        "RESEARCH_PROVIDER_MAX_RETRIES": 0,
    }
    values.update(overrides)
    return Settings(**values)
