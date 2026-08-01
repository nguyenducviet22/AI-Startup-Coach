import argparse
import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Source-tree CI/dev tooling: run from a checkout with `python -m evals.run`.
# The eval suite is intentionally not part of the installed application wheel.
from app.core.config import ROOT_DIR, Settings
from app.services.context_builder import StartupContext
from app.services.orchestrator import AgentOrchestrator, OrchestratorResult
from app.services.skill_loader import SkillLoader
from app.services.tool_dispatcher import ToolDispatcher

FIXTURES_DIR = ROOT_DIR / "evals" / "fixtures"
DEFAULT_OUTPUT_PATH = ROOT_DIR / "evals" / "artifacts" / "agentops-eval-results.json"


@dataclass(frozen=True)
class EvalCaseResult:
    case_id: str
    stage: str
    passed: bool
    errors: list[str]
    tool_calls: list[str]
    stage_readiness: dict[str, Any] | None
    db_required: bool
    stage_advance_service_used: bool


class ScriptedChatClient:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self._responses = list(responses)
        self.requests: list[dict[str, Any]] = []

    async def create_chat_completion(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        self.requests.append({"messages": messages, "tools": tools, "model": model})
        if not self._responses:
            raise AssertionError("Fixture did not provide enough scripted LLM responses.")
        return _response_from_fixture(self._responses.pop(0))


async def run_eval_suite(
    *,
    fixtures_dir: Path = FIXTURES_DIR,
    output_path: Path | None = DEFAULT_OUTPUT_PATH,
) -> dict[str, Any]:
    cases = load_cases(fixtures_dir)
    results = [await run_eval_case(case) for case in cases]
    summary = {
        "suite": "agentops_baseline",
        "db_required": False,
        "artifact_format": "json",
        "total": len(results),
        "passed": sum(1 for result in results if result.passed),
        "failed": sum(1 for result in results if not result.passed),
        "results": [_result_to_dict(result) for result in results],
    }
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(summary, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    return summary


def load_cases(fixtures_dir: Path = FIXTURES_DIR) -> list[dict[str, Any]]:
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(fixtures_dir.glob("*.json"))
    ]


async def run_eval_case(case: dict[str, Any]) -> EvalCaseResult:
    startup = StartupContext(
        startup_id=case["startup"]["startup_id"],
        user_id=case["startup"]["user_id"],
        current_stage=case["stage"],
        name=case["startup"].get("name"),
    )
    original_stage = startup.current_stage
    client = ScriptedChatClient(case["llm_responses"])
    orchestrator = AgentOrchestrator(
        chat_client=client,
        tool_dispatcher=ToolDispatcher(document_service=None),
        skill_loader=SkillLoader(),
        settings=_settings(),
    )
    result = await orchestrator.handle_turn(
        startup=startup,
        history=case.get("history", []),
        user_message=case["student_messages"][0],
        current_document=case.get("current_document"),
    )

    errors = _assert_case(case=case, result=result, original_stage=original_stage, final_stage=startup.current_stage)
    return EvalCaseResult(
        case_id=case["case_id"],
        stage=case["stage"],
        passed=not errors,
        errors=errors,
        tool_calls=[entry["tool_name"] for entry in result.tool_call_data],
        stage_readiness=result.stage_readiness,
        db_required=False,
        # Structural invariant: this runner only wires AgentOrchestrator and
        # ToolDispatcher, neither of which depends on StageService today.
        stage_advance_service_used=False,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run deterministic AI Startup Coach eval fixtures.")
    parser.add_argument(
        "--fixtures-dir",
        type=Path,
        default=FIXTURES_DIR,
        help="Directory containing JSON eval fixtures.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Path for the JSON eval summary artifact.",
    )
    args = parser.parse_args()
    summary = asyncio.run(run_eval_suite(fixtures_dir=args.fixtures_dir, output_path=args.output))
    print(json.dumps(summary, ensure_ascii=True, indent=2))
    if summary["failed"]:
        raise SystemExit(1)


def _assert_case(
    *,
    case: dict[str, Any],
    result: OrchestratorResult,
    original_stage: str,
    final_stage: str,
) -> list[str]:
    errors: list[str] = []
    expected_tool_calls = case["expected"]["tool_calls"]
    actual_tool_names = [entry["tool_name"] for entry in result.tool_call_data]
    expected_tool_names = [entry["tool_name"] for entry in expected_tool_calls]
    if actual_tool_names != expected_tool_names:
        errors.append(f"Expected tool calls {expected_tool_names}, got {actual_tool_names}.")

    for expected in expected_tool_calls:
        matching = [
            entry for entry in result.tool_call_data if entry["tool_name"] == expected["tool_name"]
        ]
        if not matching:
            continue
        tool_result = matching[0]["result"]
        if tool_result.get("ok") is not True:
            errors.append(f"Tool {expected['tool_name']} returned non-ok result: {tool_result}.")
            continue
        arguments = tool_result.get("arguments", {})
        for field in expected["required_fields"]:
            if _missing_required_argument(arguments, field):
                errors.append(f"Tool {expected['tool_name']} missing required field '{field}'.")

    expected_readiness = case["expected"].get("stage_readiness")
    if expected_readiness is not None:
        if not _well_formed_readiness(result.stage_readiness):
            errors.append(f"Stage readiness is not well formed: {result.stage_readiness}.")
        elif result.stage_readiness != expected_readiness:
            errors.append(f"Expected readiness {expected_readiness}, got {result.stage_readiness}.")

    if final_stage != original_stage:
        errors.append(f"Stage advanced from {original_stage} to {final_stage}.")

    return errors


def _response_from_fixture(response: dict[str, Any]) -> dict[str, Any]:
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": response.get("content"),
                    "tool_calls": [
                        _tool_call_from_fixture(tool_call)
                        for tool_call in response.get("tool_calls", [])
                    ],
                }
            }
        ]
    }


def _tool_call_from_fixture(tool_call: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": tool_call["id"],
        "type": "function",
        "function": {
            "name": tool_call["name"],
            "arguments": json.dumps(tool_call["arguments"], ensure_ascii=True),
        },
    }


def _well_formed_readiness(value: dict[str, Any] | None) -> bool:
    return (
        isinstance(value, dict)
        and isinstance(value.get("ready"), bool)
        and isinstance(value.get("missing_fields"), list)
        and all(isinstance(field, str) for field in value["missing_fields"])
    )


def _missing_required_argument(arguments: dict[str, Any], field: str) -> bool:
    if field not in arguments:
        return True
    value = arguments[field]
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    if isinstance(value, list) and not value and field != "missing_fields":
        return True
    return False


def _result_to_dict(result: EvalCaseResult) -> dict[str, Any]:
    return {
        "case_id": result.case_id,
        "stage": result.stage,
        "passed": result.passed,
        "errors": result.errors,
        "tool_calls": result.tool_calls,
        "stage_readiness": result.stage_readiness,
        "db_required": result.db_required,
        "stage_advance_service_used": result.stage_advance_service_used,
    }


def _settings() -> Settings:
    return Settings(
        DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/coaching",
        OPENROUTER_API_KEY="eval-suite-no-live-key",
        OPENROUTER_BASE_URL="https://openrouter.test/api/v1",
        OPENROUTER_MODEL="eval-scripted-model",
        OPENROUTER_HTTP_REFERER="http://localhost:8000",
        OPENROUTER_X_TITLE="AI Startup Coach",
        CHAT_HISTORY_LIMIT=20,
        LLM_MAX_RETRIES=2,
        LLM_RETRY_BACKOFF_SECONDS=0,
        JWT_SECRET="eval-suite-secret-with-at-least-thirty-two-bytes",
        JWT_ALGORITHM="HS256",
        ACCESS_TOKEN_EXPIRE_MINUTES=30,
        REFRESH_TOKEN_EXPIRE_DAYS=7,
    )


if __name__ == "__main__":
    main()
