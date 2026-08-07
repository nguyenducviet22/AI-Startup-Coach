import uuid
from datetime import UTC, datetime

from app.core.config import Settings
from app.research.schemas import EvidenceAuthority, EvidenceRecord, LegalNotice, ResearchResult
from app.services.research_errors import ResearchErrorDetail, ResearchServiceError
from app.services.research_service import ResearchAccountingOutcome, ResearchServiceResult
from app.services.tool_dispatcher import ResearchExecutionContext, ToolDispatcher
from app.services.orchestrator import AgentOrchestrator


class FakeDocumentService:
    def __init__(self) -> None:
        self.calls = []

    async def save_tool_document(self, *, startup_id, tool_name, arguments):
        self.calls.append(
            {"startup_id": startup_id, "tool_name": tool_name, "arguments": arguments}
        )
        return {
            "id": "document-1",
            "startup_id": startup_id,
            "doc_type": "lean_canvas",
            "version": 1,
            "is_current": True,
            "created_at": "2026-07-30T00:00:00+00:00",
            "content": arguments,
        }


class FakeResearchService:
    def __init__(self, outcome: ResearchServiceResult | Exception) -> None:
        self.outcome = outcome
        self.calls: list[dict] = []

    async def execute(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def _research_outcome() -> ResearchServiceResult:
    now = datetime(2026, 8, 6, tzinfo=UTC)
    return ResearchServiceResult(
        result=ResearchResult(
            evidence=[
                EvidenceRecord(
                    source_id="source-1",
                    url="https://example.com/source",
                    title="Source",
                    excerpt="Evidence",
                    retrieved_at=now,
                    authority=EvidenceAuthority.UNKNOWN,
                    legal_or_regulatory=True,
                )
            ],
            retrieved_at=now,
            served_at=now,
            legal_notice=LegalNotice(),
        ),
        accounting=ResearchAccountingOutcome(
            provider="fake",
            operation="search",
            query_fingerprint="fingerprint",
            provider_call_made=True,
            cache_hit=False,
            credits_reserved=1,
            credits_charged=1,
            provider_request_id="request-1",
        ),
    )


def _research_context() -> ResearchExecutionContext:
    return ResearchExecutionContext(
        startup_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        turn_id=uuid.uuid4(),
        stage="idea",
    )


async def test_dispatcher_returns_validated_result_without_persisting() -> None:
    result = await ToolDispatcher().execute(
        tool_name="generate_lean_canvas",
        current_stage="lean_canvas",
        arguments={
            "problem": "Tutors lose time coordinating lessons.",
            "solution": "Scheduling automation.",
            "unique_value_proposition": "Calendar ops for tutoring teams.",
            "customer_segments": "Independent tutoring centers.",
        },
    )

    assert result["ok"] is True
    assert result["tool_name"] == "generate_lean_canvas"
    assert result["arguments"]["problem"] == "Tutors lose time coordinating lessons."
    assert result["persistence"]["status"] == "deferred"


async def test_dispatcher_returns_recoverable_validation_error() -> None:
    result = await ToolDispatcher().execute(
        tool_name="generate_swot",
        current_stage="swot",
        arguments={"strengths": [], "weaknesses": [], "opportunities": [], "threats": []},
    )

    assert result["ok"] is False
    assert result["error"]["type"] == "tool_validation_error"
    assert result["error"]["details"][0]["code"] == "too_short"


async def test_dispatcher_rejects_tool_not_available_for_current_stage() -> None:
    result = await ToolDispatcher().execute(
        tool_name="generate_bmc",
        current_stage="idea",
        arguments={"customer_segments": "Tutors", "value_propositions": "Save time"},
    )

    assert result["ok"] is False
    assert result["error"]["type"] == "tool_not_available_for_stage"
    assert result["error"]["details"][0]["code"] == "tool_not_allowed"


async def test_dispatcher_check_stage_readiness_is_validation_only() -> None:
    result = await ToolDispatcher().execute(
        tool_name="check_stage_readiness",
        current_stage="idea",
        arguments={"current_stage": "idea", "ready": True, "missing_fields": []},
    )

    assert result["ok"] is True
    assert result["arguments"]["ready"] is True
    assert result["persistence"]["status"] == "deferred"


async def test_dispatcher_persists_document_when_document_service_is_injected() -> None:
    document_service = FakeDocumentService()
    result = await ToolDispatcher(document_service=document_service).execute(
        tool_name="generate_lean_canvas",
        current_stage="lean_canvas",
        startup_id="startup-1",
        arguments={
            "problem": "Tutors lose time coordinating lessons.",
            "solution": "Scheduling automation.",
            "unique_value_proposition": "Calendar ops for tutoring teams.",
            "customer_segments": "Independent tutoring centers.",
        },
    )

    assert result["ok"] is True
    assert result["persistence"]["status"] == "persisted"
    assert result["persistence"]["document"]["version"] == 1
    assert document_service.calls == [
        {
            "startup_id": "startup-1",
            "tool_name": "generate_lean_canvas",
            "arguments": result["arguments"],
        }
    ]


async def test_dispatcher_readiness_check_stays_validation_only_with_document_service() -> None:
    document_service = FakeDocumentService()
    result = await ToolDispatcher(document_service=document_service).execute(
        tool_name="check_stage_readiness",
        current_stage="idea",
        startup_id="startup-1",
        arguments={"current_stage": "idea", "ready": True, "missing_fields": []},
    )

    assert result["ok"] is True
    assert result["persistence"]["status"] == "deferred"
    assert document_service.calls == []


async def test_dispatcher_executes_research_with_ownership_context_and_legal_shape() -> None:
    research_service = FakeResearchService(_research_outcome())
    context = _research_context()
    result = await ToolDispatcher(
        research_service=research_service,
        research_context=context,
    ).execute(
        tool_name="research_web",
        current_stage="idea",
        arguments={"query": "Vietnam employment law", "category": "legal", "jurisdiction": "Vietnam"},
    )

    assert result["ok"] is True
    assert result["research"]["evidence"][0]["url"] == "https://example.com/source"
    assert result["research"]["evidence"][0]["legal_or_regulatory"] is True
    assert result["research"]["legal_notice"]["required"] is True
    assert research_service.calls[0]["owner"].startup_id == context.startup_id
    assert research_service.calls[0]["owner"].user_id == context.user_id
    assert research_service.calls[0]["owner"].session_id == context.session_id


async def test_dispatcher_returns_structured_research_error() -> None:
    research_service = FakeResearchService(
        ResearchServiceError(
            ResearchErrorDetail("jurisdiction", "research_jurisdiction_required", "A jurisdiction is required.")
        )
    )
    result = await ToolDispatcher(
        research_service=research_service,
        research_context=_research_context(),
    ).execute(
        tool_name="research_web",
        current_stage="idea",
        arguments={"query": "Vietnam employment law", "category": "legal", "jurisdiction": "Vietnam"},
    )

    assert result == {
        "ok": False,
        "tool_name": "research_web",
        "error": {
            "type": "research_service_error",
            "message": "A jurisdiction is required.",
            "details": [
                {
                    "field": "jurisdiction",
                    "code": "research_jurisdiction_required",
                    "message": "A jurisdiction is required.",
                }
            ],
        },
    }


async def test_dispatcher_accepts_url_only_research_without_a_synthetic_query() -> None:
    research_service = FakeResearchService(_research_outcome())
    result = await ToolDispatcher(
        research_service=research_service,
        research_context=_research_context(),
    ).execute(
        tool_name="research_web",
        current_stage="idea",
        arguments={"urls": ["https://example.com/founder-source"]},
    )

    assert result["ok"] is True
    request = research_service.calls[0]["request"]
    assert request.query is None
    assert [str(url) for url in request.urls] == ["https://example.com/founder-source"]


async def test_dispatcher_returns_structured_error_for_malformed_founder_url() -> None:
    result = await ToolDispatcher(
        research_service=FakeResearchService(_research_outcome()),
        research_context=_research_context(),
    ).execute(
        tool_name="research_web",
        current_stage="idea",
        arguments={"urls": ["not-a-url"]},
    )

    assert result["ok"] is False
    assert result["error"]["type"] == "tool_validation_error"
    assert result["error"]["details"][0]["field"] == "urls.0"


class BatchChatClient:
    def __init__(self) -> None:
        self.calls = 0

    async def create_chat_completion(self, **kwargs):
        self.calls += 1
        if self.calls == 1:
            return {
                "choices": [{"message": {"content": None, "tool_calls": [
                    {"id": "research", "function": {"name": "research_web", "arguments": '{"query":"market"}'}},
                    {"id": "document", "function": {"name": "generate_lean_canvas", "arguments": '{"problem":"P","solution":"S","unique_value_proposition":"U","customer_segments":"C"}'}},
                ]}}]
            }
        return {"choices": [{"message": {"content": "Both tool results are available.", "tool_calls": []}}]}


class BatchDispatcher:
    async def execute(self, *, tool_name, **kwargs):
        if tool_name == "research_web":
            return {"ok": True, "tool_name": tool_name, "research": {"evidence": [{"source_id": "s1"}]}}
        return {"ok": True, "tool_name": tool_name, "persistence": {"status": "persisted"}}


class BatchSkillLoader:
    def load(self, current_stage: str) -> str:
        return "Research-dependent document generation is a two-turn flow."


async def test_same_turn_research_and_document_batch_is_not_labeled_research_informed() -> None:
    from app.services.context_builder import StartupContext

    result = await AgentOrchestrator(
        chat_client=BatchChatClient(),
        tool_dispatcher=BatchDispatcher(),  # type: ignore[arg-type]
        skill_loader=BatchSkillLoader(),  # type: ignore[arg-type]
        settings=Settings(
            _env_file=None,
            JWT_SECRET="tool-dispatcher-test-secret-with-at-least-thirty-two-bytes",
        ),
    ).handle_turn(
        startup=StartupContext("startup", "user", "lean_canvas"),
        history=[],
        user_message="Research this market and generate the canvas.",
    )

    assert [entry["tool_name"] for entry in result.tool_call_data] == ["research_web", "generate_lean_canvas"]
    document_result = result.tool_call_data[1]["result"]
    assert "research_informed" not in document_result
    assert "research-informed" not in result.content.lower()
