import uuid

import pytest

from app.core.config import ROOT_DIR
from evals.run import load_cases, run_eval_case, run_eval_suite


@pytest.mark.parametrize("case", load_cases())
async def test_agentops_eval_fixture_case_passes(case: dict) -> None:
    result = await run_eval_case(case)

    assert result.passed is True
    assert result.errors == []
    assert result.tool_calls == [
        expected["tool_name"] for expected in case["expected"]["tool_calls"]
    ]
    assert result.stage_readiness == case["expected"]["stage_readiness"]
    assert result.db_required is False
    assert result.stage_advance_service_used is False


async def test_agentops_eval_suite_writes_json_artifact() -> None:
    output_path = ROOT_DIR / ".tmp" / f"agentops-eval-results-{uuid.uuid4()}.json"

    summary = await run_eval_suite(output_path=output_path)

    assert summary["suite"] == "agentops_baseline"
    assert summary["artifact_format"] == "json"
    assert summary["db_required"] is False
    assert summary["total"] == 3
    assert summary["passed"] == 3
    assert summary["failed"] == 0
    assert output_path.read_text(encoding="utf-8").startswith("{\n")
    output_path.unlink()
