from typing import Any

from app.tools.schemas import (
    CheckStageReadinessArgs,
    GenerateBmcArgs,
    GenerateFundingGuideArgs,
    GenerateLeanCanvasArgs,
    GenerateMarketingStrategyArgs,
    GenerateProductPlanArgs,
    GenerateSwotArgs,
    ToolArguments,
)

TOOL_MODELS: dict[str, type[ToolArguments]] = {
    "generate_lean_canvas": GenerateLeanCanvasArgs,
    "generate_bmc": GenerateBmcArgs,
    "generate_swot": GenerateSwotArgs,
    "generate_product_plan": GenerateProductPlanArgs,
    "generate_marketing_strategy": GenerateMarketingStrategyArgs,
    "generate_funding_guide": GenerateFundingGuideArgs,
    "check_stage_readiness": CheckStageReadinessArgs,
}

TOOL_DESCRIPTIONS: dict[str, str] = {
    "generate_lean_canvas": "Create or update the Lean Canvas based on information gathered from the student.",
    "generate_bmc": "Create or update the Business Model Canvas based on the student's validated business model details.",
    "generate_swot": "Create or update a SWOT analysis for the startup.",
    "generate_product_plan": "Create or update the MVP scope, prioritized features, and milestone timeline.",
    "generate_marketing_strategy": "Create or update the startup's marketing strategy.",
    "generate_funding_guide": "Create or update the funding preparation guide and pitch outline.",
    "check_stage_readiness": "Evaluate whether the current information is sufficient to advance to the next stage.",
}


def get_openai_tool_definition(tool_name: str) -> dict[str, Any]:
    model = TOOL_MODELS[tool_name]
    return {
        "type": "function",
        "function": {
            "name": tool_name,
            "description": TOOL_DESCRIPTIONS[tool_name],
            "parameters": model.model_json_schema(),
        },
    }


def get_openai_tool_definitions(tool_names: list[str] | None = None) -> list[dict[str, Any]]:
    names = tool_names or list(TOOL_MODELS)
    return [get_openai_tool_definition(name) for name in names]
