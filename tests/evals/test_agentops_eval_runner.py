import uuid
from copy import deepcopy

import pytest

from app.core.config import ROOT_DIR
from evals.run import load_cases, run_eval_case, run_eval_suite


@pytest.mark.parametrize("case", load_cases())
async def test_agentops_eval_fixture_case_passes(case: dict) -> None:
    result = await run_eval_case(case)

    assert result.passed is True
    assert result.errors == []
    expected_turns = case["expected"].get("turns") or [case["expected"]]
    assert result.tool_calls == [
        expected["tool_name"]
        for turn in expected_turns
        for expected in turn["tool_calls"]
    ]
    assert result.stage_readiness == expected_turns[-1].get("stage_readiness")
    assert result.db_required is False
    assert result.stage_advance_service_used is False


async def test_agentops_eval_suite_writes_json_artifact() -> None:
    output_path = ROOT_DIR / ".tmp" / f"agentops-eval-results-{uuid.uuid4()}.json"

    summary = await run_eval_suite(output_path=output_path)

    assert summary["suite"] == "agentops_baseline"
    assert summary["artifact_format"] == "json"
    assert summary["db_required"] is False
    assert summary["total"] == 4
    assert summary["passed"] == 4
    assert summary["failed"] == 0
    assert output_path.read_text(encoding="utf-8").startswith("{\n")
    output_path.unlink()


def _research_lean_canvas_case() -> dict:
    return next(case for case in load_cases() if case["case_id"] == "research_lean_canvas")


@pytest.mark.parametrize(
    ("content", "expected_source_ids"),
    [
        ("I drafted the Lean Canvas without a source citation.", ["source-tutoring-market"]),
        ("I drafted the Lean Canvas using [unknown-source].", ["source-tutoring-market"]),
    ],
)
async def test_research_eval_fails_for_missing_or_invalid_source_citation(
    content: str, expected_source_ids: list[str]
) -> None:
    case = deepcopy(_research_lean_canvas_case())
    case["llm_responses"][3]["content"] = content

    result = await run_eval_case(case)

    assert result.passed is False
    assert result.errors == [
        f"Later document-generation response is missing valid source citations {expected_source_ids}."
    ]


@pytest.mark.parametrize("field", ["url", "retrieved_at"])
async def test_research_eval_fails_for_evidence_missing_direct_url_or_retrieval_time(field: str) -> None:
    case = deepcopy(_research_lean_canvas_case())
    case["research_evidence"][0].pop(field)

    result = await run_eval_case(case)

    assert result.passed is False
    assert result.errors == [f"Research fixture evidence is invalid at: {field}."]


async def test_research_eval_rejects_same_turn_research_and_document_generation() -> None:
    case = deepcopy(_research_lean_canvas_case())
    case["llm_responses"][0]["tool_calls"].append(case["llm_responses"][2]["tool_calls"][0])

    result = await run_eval_case(case)

    assert result.passed is False
    assert "Research and document generation must be in separate turns." in result.errors
