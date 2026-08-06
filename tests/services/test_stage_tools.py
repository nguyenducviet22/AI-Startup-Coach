import pytest

from app.domain.stages import InvalidStageError
from app.services.stage_tools import get_openai_tools_for_stage, get_tool_names_for_stage


@pytest.mark.parametrize(
    ("stage", "expected_tools"),
    [
        ("idea", ("research_web", "check_stage_readiness")),
        ("lean_canvas", ("generate_lean_canvas", "research_web", "check_stage_readiness")),
        ("bmc", ("generate_bmc", "research_web", "check_stage_readiness")),
        ("swot", ("generate_swot", "research_web", "check_stage_readiness")),
        ("product_plan", ("generate_product_plan", "research_web", "check_stage_readiness")),
        ("marketing", ("generate_marketing_strategy", "research_web", "check_stage_readiness")),
        ("funding", ("generate_funding_guide", "research_web", "check_stage_readiness")),
        ("completed", ()),
    ],
)
def test_get_tool_names_for_stage_exposes_only_current_stage_tools(
    stage: str,
    expected_tools: tuple[str, ...],
) -> None:
    assert get_tool_names_for_stage(stage) == expected_tools


def test_get_tool_names_for_stage_rejects_invalid_stage() -> None:
    with pytest.raises(InvalidStageError):
        get_tool_names_for_stage("traction")


def test_get_openai_tools_for_stage_uses_standard_function_tool_format() -> None:
    tools = get_openai_tools_for_stage("lean_canvas")

    assert [tool["function"]["name"] for tool in tools] == [
        "generate_lean_canvas",
        "research_web",
        "check_stage_readiness",
    ]
    assert all(tool["type"] == "function" for tool in tools)
