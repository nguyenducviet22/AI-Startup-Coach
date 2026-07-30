from app.domain.stages import StageName, validate_stage
from app.tools.definitions import get_openai_tool_definitions

CHECK_STAGE_READINESS = "check_stage_readiness"

STAGE_TOOL_NAMES: dict[StageName, tuple[str, ...]] = {
    "idea": (CHECK_STAGE_READINESS,),
    "lean_canvas": ("generate_lean_canvas", CHECK_STAGE_READINESS),
    "bmc": ("generate_bmc", CHECK_STAGE_READINESS),
    "swot": ("generate_swot", CHECK_STAGE_READINESS),
    "product_plan": ("generate_product_plan", CHECK_STAGE_READINESS),
    "marketing": ("generate_marketing_strategy", CHECK_STAGE_READINESS),
    "funding": ("generate_funding_guide", CHECK_STAGE_READINESS),
    "completed": (),
}


def get_tool_names_for_stage(stage: str) -> tuple[str, ...]:
    validated_stage = validate_stage(stage)
    return STAGE_TOOL_NAMES[validated_stage]


def get_openai_tools_for_stage(stage: str) -> list[dict]:
    return get_openai_tool_definitions(list(get_tool_names_for_stage(stage)))
