import json

from app.tools.validation import validate_tool_arguments


def test_valid_lean_canvas_arguments_are_normalized() -> None:
    result = validate_tool_arguments(
        "generate_lean_canvas",
        {
            "problem": "  Missed assignment deadlines  ",
            "solution": "Deadline-aware planning assistant",
            "unique_value_proposition": "Planner for working students",
            "customer_segments": "Part-time students",
        },
    )

    assert result["ok"] is True
    assert result["arguments"]["problem"] == "Missed assignment deadlines"
    assert result["arguments"]["unfair_advantage"] == ""


def test_invalid_lean_canvas_arguments_return_recoverable_error() -> None:
    result = validate_tool_arguments(
        "generate_lean_canvas",
        {
            "problem": "Missed assignment deadlines",
            "solution": "Planning assistant",
            "customer_segments": "Part-time students",
        },
    )

    assert result["ok"] is False
    assert result["error"]["type"] == "tool_validation_error"
    assert result["error"]["details"][0]["field"] == "unique_value_proposition"


def test_valid_product_plan_accepts_nested_objects() -> None:
    result = validate_tool_arguments(
        "generate_product_plan",
        {
            "mvp_scope": "Manual weekly planning digest",
            "features": [
                {"name": "Schedule intake form", "priority": "must-have", "effort": "low"},
                {"name": "Calendar export", "priority": "nice-to-have", "effort": "medium"},
            ],
            "timeline": [{"milestone": "Pilot signup", "target_date": "2026-09-01"}],
        },
    )

    assert result["ok"] is True
    assert result["arguments"]["features"][0]["priority"] == "must-have"


def test_invalid_product_plan_nested_enum_returns_field_path() -> None:
    result = validate_tool_arguments(
        "generate_product_plan",
        {
            "mvp_scope": "Manual weekly planning digest",
            "features": [{"name": "Schedule intake form", "priority": "urgent", "effort": "low"}],
        },
    )

    assert result["ok"] is False
    assert result["error"]["details"][0]["field"] == "features.0.priority"


def test_valid_swot_requires_non_empty_arrays() -> None:
    result = validate_tool_arguments(
        "generate_swot",
        {
            "strengths": ["Specific campus access"],
            "weaknesses": ["Small team"],
            "opportunities": ["University partnerships"],
            "threats": ["Incumbent calendar tools"],
        },
    )

    assert result["ok"] is True


def test_invalid_swot_empty_array_returns_recoverable_error() -> None:
    result = validate_tool_arguments(
        "generate_swot",
        {
            "strengths": [],
            "weaknesses": ["Small team"],
            "opportunities": ["University partnerships"],
            "threats": ["Incumbent calendar tools"],
        },
    )

    assert result["ok"] is False
    assert result["error"]["details"][0]["field"] == "strengths"


def test_check_stage_readiness_validates_stage_names() -> None:
    result = validate_tool_arguments(
        "check_stage_readiness",
        {"current_stage": "lean_canvas", "ready": False, "missing_fields": ["channels"]},
    )

    assert result["ok"] is True


def test_check_stage_readiness_rejects_unknown_stage() -> None:
    result = validate_tool_arguments(
        "check_stage_readiness",
        {"current_stage": "sales", "ready": True},
    )

    assert result["ok"] is False
    assert result["error"]["details"][0]["field"] == "current_stage"


def test_validation_accepts_json_string_arguments() -> None:
    result = validate_tool_arguments(
        "generate_marketing_strategy",
        json.dumps({"target_audience": "Working students", "channels": ["campus clubs"]}),
    )

    assert result["ok"] is True
    assert result["arguments"]["key_messages"] == ""


def test_invalid_json_string_returns_recoverable_error() -> None:
    result = validate_tool_arguments("generate_marketing_strategy", "{bad json")

    assert result["ok"] is False
    assert result["error"]["details"][0]["code"] == "json_invalid"


def test_unknown_tool_returns_recoverable_error() -> None:
    result = validate_tool_arguments("not_a_tool", {})

    assert result["ok"] is False
    assert result["error"]["details"][0]["code"] == "unknown_tool"


def test_all_document_tool_schemas_accept_minimum_valid_payloads() -> None:
    valid_payloads = {
        "generate_bmc": {
            "customer_segments": "Part-time students",
            "value_propositions": "Deadline-aware weekly planning",
        },
        "generate_funding_guide": {
            "pitch_outline": [{"slide_title": "Problem", "content": "Students miss deadlines"}],
        },
    }

    for tool_name, payload in valid_payloads.items():
        assert validate_tool_arguments(tool_name, payload)["ok"] is True
