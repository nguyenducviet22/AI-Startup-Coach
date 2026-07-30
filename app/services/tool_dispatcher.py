import uuid
from typing import Any

from app.services.document_service import DocumentService, TOOL_DOCUMENT_TYPES
from app.services.stage_tools import get_tool_names_for_stage
from app.tools.validation import validate_tool_arguments


class ToolDispatcher:
    def __init__(self, document_service: DocumentService | None = None) -> None:
        self.document_service = document_service

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
