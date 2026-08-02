from app.services.tool_dispatcher import ToolDispatcher


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
