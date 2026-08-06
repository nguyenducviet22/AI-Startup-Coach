import json
from typing import Any

from pydantic import ValidationError

from app.tools.definitions import TOOL_MODELS


def validate_tool_arguments(tool_name: str, arguments: dict[str, Any] | str) -> dict[str, Any]:
    model = TOOL_MODELS.get(tool_name)
    if model is None:
        return _validation_error(
            tool_name=tool_name,
            message=f"Unknown tool '{tool_name}'.",
            details=[{"field": "", "message": "Tool is not registered.", "code": "unknown_tool"}],
        )

    try:
        data = json.loads(arguments) if isinstance(arguments, str) else arguments
    except json.JSONDecodeError as exc:
        return _validation_error(
            tool_name=tool_name,
            message=f"Invalid JSON arguments for tool '{tool_name}'.",
            details=[{"field": "", "message": exc.msg, "code": "json_invalid"}],
        )

    try:
        validated = model.model_validate(data)
    except ValidationError as exc:
        return _validation_error(
            tool_name=tool_name,
            message=f"Invalid arguments for tool '{tool_name}'. Please correct the schema and try again.",
            details=[
                {
                    "field": ".".join(str(part) for part in error["loc"]),
                    "message": error["msg"],
                    "code": error["type"],
                }
                for error in exc.errors()
            ],
        )

    cross_field_details = _cross_field_errors(tool_name, validated.model_dump())
    if cross_field_details:
        return _validation_error(
            tool_name=tool_name,
            message=f"Invalid arguments for tool '{tool_name}'. Please correct the schema and try again.",
            details=cross_field_details,
        )

    return {
        "ok": True,
        "tool_name": tool_name,
        "arguments": validated.model_dump(),
    }


def _cross_field_errors(tool_name: str, arguments: dict[str, Any]) -> list[dict[str, str]]:
    if tool_name != "research_web":
        return []

    query = arguments.get("query")
    urls = arguments.get("urls")
    details: list[dict[str, str]] = []
    if not query and not urls:
        details.append(
            {
                "field": "query",
                "code": "research_query_or_urls_required",
                "message": "Provide a non-empty query or at least one founder URL.",
            }
        )
    if query and urls:
        details.append(
            {
                "field": "urls",
                "code": "research_query_urls_conflict",
                "message": "Provide either a query or founder URLs, not both.",
            }
        )
    if arguments.get("category") == "legal" and not arguments.get("jurisdiction"):
        details.append(
            {
                "field": "jurisdiction",
                "code": "research_jurisdiction_required",
                "message": "A jurisdiction is required for legal or regulatory research.",
            }
        )
    return details


def _validation_error(tool_name: str, message: str, details: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "ok": False,
        "tool_name": tool_name,
        "error": {
            "type": "tool_validation_error",
            "message": message,
            "details": details,
        },
    }
