from app.tools.validation import validate_tool_arguments


def test_research_tool_requires_query_or_founder_urls() -> None:
    result = validate_tool_arguments("research_web", {"category": "general"})

    assert result["ok"] is False
    assert result["error"]["details"] == [
        {
            "field": "query",
            "code": "research_query_or_urls_required",
            "message": "Provide a non-empty query or at least one founder URL.",
        }
    ]


def test_research_tool_rejects_query_url_conflicts_and_missing_legal_jurisdiction() -> None:
    result = validate_tool_arguments(
        "research_web",
        {
            "query": "Vietnam employment law",
            "urls": ["https://example.com/law"],
            "category": "legal",
        },
    )

    assert result["ok"] is False
    assert {detail["code"] for detail in result["error"]["details"]} == {
        "research_query_urls_conflict",
        "research_jurisdiction_required",
    }


def test_research_tool_exposes_no_provider_credentials_or_accounting_inputs() -> None:
    result = validate_tool_arguments(
        "research_web",
        {
            "query": "Tutor market size",
            "api_key": "not-accepted",
            "cache_key": "not-accepted",
            "credits": 99,
        },
    )

    assert result["ok"] is False
    assert {detail["field"] for detail in result["error"]["details"]} == {
        "api_key",
        "cache_key",
        "credits",
    }
