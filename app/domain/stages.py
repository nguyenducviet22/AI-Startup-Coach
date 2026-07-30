from typing import Literal, cast


StageName = Literal[
    "idea",
    "lean_canvas",
    "bmc",
    "swot",
    "product_plan",
    "marketing",
    "funding",
    "completed",
]

COACHING_STAGES: tuple[StageName, ...] = (
    "idea",
    "lean_canvas",
    "bmc",
    "swot",
    "product_plan",
    "marketing",
    "funding",
)
COMPLETED_STAGE: StageName = "completed"
ALL_STAGES: tuple[StageName, ...] = (*COACHING_STAGES, COMPLETED_STAGE)


class InvalidStageError(ValueError):
    def __init__(self, stage: str) -> None:
        self.stage = stage
        valid_stages = ", ".join(ALL_STAGES)
        super().__init__(f"Invalid startup stage '{stage}'. Expected one of: {valid_stages}.")


def validate_stage(stage: str) -> StageName:
    if stage not in ALL_STAGES:
        raise InvalidStageError(stage)
    return cast(StageName, stage)


def is_completed_stage(stage: str) -> bool:
    return validate_stage(stage) == COMPLETED_STAGE


def get_next_stage(stage: str) -> StageName | None:
    validated_stage = validate_stage(stage)
    if validated_stage == COMPLETED_STAGE:
        return None

    current_index = COACHING_STAGES.index(validated_stage)
    if current_index == len(COACHING_STAGES) - 1:
        return COMPLETED_STAGE
    return COACHING_STAGES[current_index + 1]
