import pytest

from app.domain.stages import (
    ALL_STAGES,
    COMPLETED_STAGE,
    COACHING_STAGES,
    InvalidStageError,
    get_next_stage,
    is_completed_stage,
    validate_stage,
)


@pytest.mark.parametrize("stage", ALL_STAGES)
def test_validate_stage_accepts_known_stages(stage: str) -> None:
    assert validate_stage(stage) == stage


def test_validate_stage_rejects_unknown_stage() -> None:
    with pytest.raises(InvalidStageError) as exc_info:
        validate_stage("traction")

    assert exc_info.value.stage == "traction"
    assert "Invalid startup stage 'traction'" in str(exc_info.value)


def test_get_next_stage_follows_ordered_state_machine() -> None:
    transitions = {
        stage: get_next_stage(stage)
        for stage in COACHING_STAGES
    }

    assert transitions == {
        "idea": "lean_canvas",
        "lean_canvas": "bmc",
        "bmc": "swot",
        "swot": "product_plan",
        "product_plan": "marketing",
        "marketing": "funding",
        "funding": COMPLETED_STAGE,
    }


def test_completed_stage_has_no_next_stage() -> None:
    assert get_next_stage("completed") is None
    assert is_completed_stage("completed")
