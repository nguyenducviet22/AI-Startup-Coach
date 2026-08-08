import argparse
import asyncio
import json
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

# Source-tree CI/dev tooling: run from a checkout with `python -m evals.run`.
# The eval suite is intentionally not part of the installed application wheel.
from app.core.config import ROOT_DIR, Settings
from app.research.schemas import EvidenceRecord, ResearchResult
from app.services.context_builder import StartupContext
from app.services.orchestrator import AgentOrchestrator, OrchestratorResult
from app.services.research_prompt import ResearchSkillLoader
from app.services.research_service import ResearchAccountingOutcome, ResearchServiceResult
from app.services.skill_loader import SkillLoader
from app.services.tool_dispatcher import ResearchExecutionContext, ToolDispatcher
from app.services.research_response_policy import apply_research_response_policy

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


@dataclass(frozen=True)
class EvalTurnResult:
    result: OrchestratorResult


class FixtureResearchService:
    """DB-free research use case returning only fixture-normalized evidence."""

    def __init__(self, evidence: list[dict[str, Any]]) -> None:
        self._evidence = [EvidenceRecord.model_validate(record) for record in evidence]
        self.calls: list[dict[str, Any]] = []

    async def execute(self, **kwargs: Any) -> ResearchServiceResult:
        self.calls.append(kwargs)
        request = kwargs["request"]
        retrieved_at = self._evidence[0].retrieved_at
        subject = request.query or "|".join(str(url) for url in request.urls)
        return ResearchServiceResult(
            result=ResearchResult(
                provider_request_id="fixture-research-request",
                evidence=self._evidence,
                cache_hit=False,
                cache_key="fixture-research-cache-key",
                retrieved_at=retrieved_at,
                served_at=retrieved_at,
            ),
            accounting=ResearchAccountingOutcome(
                provider="fixture",
                operation="extract" if request.urls else "search",
                query_fingerprint=subject,
                provider_call_made=True,
                cache_hit=False,
                credits_reserved=1,
                credits_charged=1,
                provider_request_id="fixture-research-request",
            ),
        )


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
    try:
        research_service = _fixture_research_service(case)
    except ValidationError as exc:
        fields = [".".join(str(part) for part in error["loc"]) for error in exc.errors()]
        return EvalCaseResult(
            case_id=case["case_id"],
            stage=case["stage"],
            passed=False,
            errors=[f"Research fixture evidence is invalid at: {', '.join(fields)}."],
            tool_calls=[],
            stage_readiness=None,
            db_required=False,
            stage_advance_service_used=False,
        )
    except ValueError as exc:
        return EvalCaseResult(
            case_id=case["case_id"],
            stage=case["stage"],
            passed=False,
            errors=[f"Research fixture evidence is invalid: {exc}."],
            tool_calls=[],
            stage_readiness=None,
            db_required=False,
            stage_advance_service_used=False,
        )
    research_context = _research_context(case, startup)
    orchestrator = AgentOrchestrator(
        chat_client=client,
        tool_dispatcher=ToolDispatcher(
            document_service=None,
            research_service=research_service,
            research_context=research_context,
        ),
        skill_loader=ResearchSkillLoader(SkillLoader()),
        settings=_settings(),
    )
    turns = await _run_turns(case=case, orchestrator=orchestrator, startup=startup)
    errors = _assert_case(
        case=case,
        turns=turns,
        original_stage=original_stage,
        final_stage=startup.current_stage,
    )
    last_turn = turns[-1]
    return EvalCaseResult(
        case_id=case["case_id"],
        stage=case["stage"],
        passed=not errors,
        errors=errors,
        tool_calls=[entry["tool_name"] for turn in turns for entry in turn.result.tool_call_data],
        stage_readiness=last_turn.result.stage_readiness,
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
    turns: list[EvalTurnResult],
    original_stage: str,
    final_stage: str,
) -> list[str]:
    errors: list[str] = []
    expected_turns = case["expected"].get("turns") or [case["expected"]]
    if len(turns) != len(expected_turns):
        errors.append(f"Expected {len(expected_turns)} turns, got {len(turns)}.")

    for index, (turn, expected) in enumerate(zip(turns, expected_turns, strict=False)):
        _assert_turn(index=index, result=turn.result, expected=expected, errors=errors)

    _assert_research_grounding(case=case, turns=turns, errors=errors)

    if case["expected"].get("no_stage_auto_advance", True) and final_stage != original_stage:
        errors.append(f"Stage advanced from {original_stage} to {final_stage}.")

    return errors


def _assert_turn(
    *,
    index: int,
    result: OrchestratorResult,
    expected: dict[str, Any],
    errors: list[str],
) -> None:
    expected_tool_calls = expected["tool_calls"]
    actual_tool_names = [entry["tool_name"] for entry in result.tool_call_data]
    expected_tool_names = [entry["tool_name"] for entry in expected_tool_calls]
    if actual_tool_names != expected_tool_names:
        errors.append(
            f"Turn {index + 1}: expected tool calls {expected_tool_names}, got {actual_tool_names}."
        )

    if "research_web" in actual_tool_names and any(name.startswith("generate_") for name in actual_tool_names):
        errors.append("Research and document generation must be in separate turns.")

    for expected_call in expected_tool_calls:
        matching = [
            entry
            for entry in result.tool_call_data
            if entry["tool_name"] == expected_call["tool_name"]
        ]
        if not matching:
            continue
        tool_result = matching[0]["result"]
        if tool_result.get("ok") is not True:
            errors.append(
                f"Tool {expected_call['tool_name']} returned non-ok result: {tool_result}."
            )
            continue
        arguments = tool_result.get("arguments", {})
        for field in expected_call["required_fields"]:
            if _missing_required_argument(arguments, field):
                errors.append(
                    f"Tool {expected_call['tool_name']} missing required field '{field}'."
                )

    expected_readiness = expected.get("stage_readiness")
    if expected_readiness is not None:
        if not _well_formed_readiness(result.stage_readiness):
            errors.append(f"Stage readiness is not well formed: {result.stage_readiness}.")
        elif result.stage_readiness != expected_readiness:
            errors.append(f"Expected readiness {expected_readiness}, got {result.stage_readiness}.")


def _assert_research_grounding(
    *, case: dict[str, Any], turns: list[EvalTurnResult], errors: list[str]
) -> None:
    grounding = case["expected"].get("research_grounding")
    if grounding is None:
        return
    research_turn_index = grounding["research_turn"]
    generation_turn_index = grounding["generation_turn"]
    if research_turn_index >= len(turns) or generation_turn_index >= len(turns):
        errors.append("Research grounding references a turn that was not executed.")
        return

    research_turn = turns[research_turn_index].result
    research_entries = [
        entry
        for entry in research_turn.tool_call_data
        if entry["tool_name"] == "research_web" and entry["result"].get("ok") is True
    ]
    if len(research_entries) != 1:
        errors.append("Research-only turn must contain exactly one successful research_web call.")
        return

    research = research_entries[0]["result"].get("research")
    evidence = research.get("evidence") if isinstance(research, dict) else None
    if not isinstance(evidence, list):
        errors.append("Research result is missing evidence records.")
        return
    source_ids = set(grounding["source_ids"])
    evidence_ids: set[str] = set()
    for record in evidence:
        if not isinstance(record, dict):
            errors.append("Evidence record must be an object.")
            continue
        source_id = record.get("source_id")
        if not isinstance(source_id, str) or not source_id.strip():
            errors.append("Evidence record is missing a source_id.")
            continue
        evidence_ids.add(source_id)
        if not isinstance(record.get("url"), str) or not record["url"].startswith(("http://", "https://")):
            errors.append(f"Evidence '{source_id}' is missing a valid direct URL.")
        if not isinstance(record.get("retrieved_at"), str) or not record["retrieved_at"].endswith(("Z", "+00:00")):
            errors.append(f"Evidence '{source_id}' is missing an original UTC retrieved_at timestamp.")

    if evidence_ids != source_ids:
        errors.append(f"Expected grounded source IDs {sorted(source_ids)}, got {sorted(evidence_ids)}.")

    generation_turn = turns[generation_turn_index].result
    if not any(entry["tool_name"].startswith("generate_") for entry in generation_turn.tool_call_data):
        errors.append("The later turn must generate a document using the research evidence.")
    citations = _citations(generation_turn.content)
    if not source_ids.issubset(citations):
        errors.append(
            f"Later document-generation response is missing valid source citations {sorted(source_ids)}."
        )


async def _run_turns(
    *, case: dict[str, Any], orchestrator: AgentOrchestrator, startup: StartupContext
) -> list[EvalTurnResult]:
    history = list(case.get("history", []))
    turns: list[EvalTurnResult] = []
    prior_tool_call_data: list[dict[str, Any]] = []
    for message in case["student_messages"]:
        result = await orchestrator.handle_turn(
            startup=startup,
            history=history,
            user_message=message,
            current_document=case.get("current_document"),
        )
        policy = apply_research_response_policy(
            result.content,
            result.tool_call_data,
            prior_tool_call_data=prior_tool_call_data,
        )
        policy_result = OrchestratorResult(
            content=policy.content,
            stage_readiness=result.stage_readiness,
            tool_messages=result.tool_messages,
            tool_call_data=result.tool_call_data,
        )
        turns.append(EvalTurnResult(result=policy_result))
        prior_tool_call_data.extend(result.tool_call_data)
        history.extend(
            [
                {"role": "user", "content": message},
                {"role": "assistant", "content": policy.content},
            ]
        )
    return turns


def _fixture_research_service(case: dict[str, Any]) -> FixtureResearchService | None:
    evidence = case.get("research_evidence")
    if evidence is None:
        return None
    if not isinstance(evidence, list):
        raise ValueError("research_evidence must be a list when provided.")
    if not evidence:
        raise ValueError("research_evidence must include at least one evidence record.")
    return FixtureResearchService(evidence)


def _research_context(case: dict[str, Any], startup: StartupContext) -> ResearchExecutionContext | None:
    if "research_evidence" not in case:
        return None
    return ResearchExecutionContext(
        startup_id=uuid.uuid5(uuid.NAMESPACE_URL, startup.startup_id),
        user_id=uuid.uuid5(uuid.NAMESPACE_URL, startup.user_id),
        session_id=uuid.uuid5(uuid.NAMESPACE_URL, f"{case['case_id']}:session"),
        turn_id=uuid.uuid5(uuid.NAMESPACE_URL, f"{case['case_id']}:turn"),
        stage=startup.current_stage,
    )


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


def _citations(content: str) -> set[str]:
    return set(re.findall(r"\[([^\]]+)\]", content))


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
