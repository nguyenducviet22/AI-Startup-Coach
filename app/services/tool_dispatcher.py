import uuid
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from app.research.schemas import ResearchRequest
from app.services.document_service import DocumentService, TOOL_DOCUMENT_TYPES
from app.services.research_errors import ResearchServiceError
from app.services.research_service import ResearchOwnerContext, ResearchService
from app.services.stage_tools import get_tool_names_for_stage
from app.tools.validation import validate_tool_arguments


@dataclass(frozen=True)
class ResearchExecutionContext:
    startup_id: uuid.UUID
    user_id: uuid.UUID
    session_id: uuid.UUID | None
    turn_id: uuid.UUID | None
    stage: str


class ToolDispatcher:
    def __init__(
        self,
        document_service: DocumentService | None = None,
        research_service: ResearchService | None = None,
        research_context: ResearchExecutionContext | None = None,
    ) -> None:
        self.document_service = document_service
        self.research_service = research_service
        self.research_context = research_context

    async def execute(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any] | str,
        current_stage: str,
        startup_id: uuid.UUID | str | None = None,
    ) -> dict[str, Any]:
        allowed_tools = get_tool_names_for_stage(current_stage)
        if tool_name not in allowed_tools:
            return {
                "ok": False,
                "tool_name": tool_name,
                "error": {
                    "type": "tool_not_available_for_stage",
                    "message": (
                        f"Tool '{tool_name}' is not available for stage '{current_stage}'. "
                        "Use only the tools exposed for the current stage."
                    ),
                    "details": [
                        {
                            "field": "tool_name",
                            "message": f"Allowed tools: {', '.join(allowed_tools) or '(none)'}.",
                            "code": "tool_not_allowed",
                        }
                    ],
                },
            }

        validation_result = validate_tool_arguments(tool_name, arguments)
        if not validation_result["ok"]:
            return validation_result

        if tool_name == "research_web":
            return await self._execute_research(validation_result["arguments"])

        if self.document_service is not None and tool_name in TOOL_DOCUMENT_TYPES:
            if startup_id is None:
                return {
                    "ok": False,
                    "tool_name": tool_name,
                    "error": {
                        "type": "tool_persistence_error",
                        "message": "A startup_id is required to persist document tool results.",
                        "details": [
                            {
                                "field": "startup_id",
                                "message": "Provide startup_id when using a persistence-backed dispatcher.",
                                "code": "missing_startup_id",
                            }
                        ],
                    },
                }

            document = await self.document_service.save_tool_document(
                startup_id=startup_id,
                tool_name=tool_name,
                arguments=validation_result["arguments"],
            )
            return {
                "ok": True,
                "tool_name": tool_name,
                "arguments": validation_result["arguments"],
                "persistence": {
                    "status": "persisted",
                    "document": document,
                },
            }

        return {
            "ok": True,
            "tool_name": tool_name,
            "arguments": validation_result["arguments"],
            "persistence": {
                "status": "deferred",
                "message": "Arguments validated; database persistence is deferred to Phase 5.",
            },
        }

    async def _execute_research(self, arguments: dict[str, Any]) -> dict[str, Any]:
        if self.research_service is None or self.research_context is None:
            return {
                "ok": False,
                "tool_name": "research_web",
                "error": {
                    "type": "research_unavailable",
                    "message": "Research is not configured for this coaching turn.",
                    "details": [
                        {
                            "field": "research",
                            "code": "research_execution_context_missing",
                            "message": "Research requires startup ownership context.",
                        }
                    ],
                },
            }

        try:
            request = ResearchRequest(
                query=arguments["query"],
                urls=arguments["urls"],
                category=arguments["category"],
                search_depth=arguments["search_depth"],
                max_results=arguments["max_results"],
                include_domains=arguments["include_domains"],
                start_date=arguments["start_date"],
                end_date=arguments["end_date"],
                jurisdiction=arguments["jurisdiction"],
                force_refresh=arguments["force_refresh"],
            )
        except ValidationError as exc:
            return {
                "ok": False,
                "tool_name": "research_web",
                "error": {
                    "type": "tool_validation_error",
                    "message": "Invalid research request.",
                    "details": [
                        {
                            "field": ".".join(str(part) for part in error["loc"]),
                            "code": error["type"],
                            "message": error["msg"],
                        }
                        for error in exc.errors()
                    ],
                },
            }
        try:
            outcome = await self.research_service.execute(
                owner=ResearchOwnerContext(
                    startup_id=self.research_context.startup_id,
                    user_id=self.research_context.user_id,
                    session_id=self.research_context.session_id,
                ),
                request=request,
            )
        except ResearchServiceError as exc:
            return {
                "ok": False,
                "tool_name": "research_web",
                "error": {
                    "type": "research_service_error",
                    "message": exc.detail.message,
                    "details": [exc.detail.to_dict()],
                },
            }

        return {
            "ok": True,
            "tool_name": "research_web",
            "research": outcome.result.model_dump(mode="json"),
        }
