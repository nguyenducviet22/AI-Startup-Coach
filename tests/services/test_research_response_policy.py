from app.research.schemas import LEGAL_NOTICE
from app.services.research_response_policy import _UNCERTAINTY_MESSAGE, apply_research_response_policy


def _tool_data(*, legal: bool = False) -> list[dict]:
    return [{
        "tool_name": "research_web",
        "result": {
            "ok": True,
            "research": {
                "evidence": [{
                    "source_id": "source-1",
                    "retrieved_at": "2026-08-07T00:00:00+00:00",
                    "legal_or_regulatory": legal,
                }],
            },
        },
    }]


def test_valid_citation_passes_through_unchanged() -> None:
    content = "Evidence supports this [source-1]."

    result = apply_research_response_policy(content, _tool_data())

    assert result.content == content


def test_unsupported_synthesis_is_replaced_with_uncertainty_message() -> None:
    result = apply_research_response_policy("This market will certainly grow.", _tool_data())

    assert result.content == _UNCERTAINTY_MESSAGE


def test_legal_evidence_injects_notice_without_mutating_raw_tool_result() -> None:
    tool_data = _tool_data(legal=True)

    result = apply_research_response_policy("Legal source [source-1].", tool_data)

    assert LEGAL_NOTICE in result.content
    assert result.research["legal_notice"] == LEGAL_NOTICE
    assert "legal_notice" not in tool_data[0]["result"]["research"]


def test_retrieved_at_is_preserved_from_the_tool_result() -> None:
    tool_data = _tool_data()

    result = apply_research_response_policy("Evidence supports this [source-1].", tool_data)

    assert result.research["evidence"][0]["retrieved_at"] == "2026-08-07T00:00:00+00:00"
