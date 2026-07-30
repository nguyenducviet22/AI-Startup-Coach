import pytest

from app.services.skill_loader import (
    COMPLETED_STAGE_PROMPT,
    STAGE_SKILL_FILES,
    SkillLoader,
    SkillNotFoundError,
    load_skill_content,
)


@pytest.mark.parametrize("stage", sorted(STAGE_SKILL_FILES))
def test_loads_existing_skill_file_for_each_coaching_stage(stage: str) -> None:
    content = load_skill_content(stage)

    assert content.startswith("# Skill:")
    assert len(content) > 100


def test_completed_stage_uses_builtin_completion_prompt() -> None:
    content = load_skill_content("completed")

    assert content == COMPLETED_STAGE_PROMPT
    assert "completed" in content.lower()
    assert "advancing" in content.lower()


def test_loads_skill_file_independent_of_current_working_directory(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    content = SkillLoader().load("idea")

    assert content.startswith("# Skill: Idea")
    assert "startup idea" in content.lower()


def test_missing_skill_file_raises_distinct_error(tmp_path) -> None:
    loader = SkillLoader(skills_dir=tmp_path)

    with pytest.raises(SkillNotFoundError) as exc_info:
        loader.load("lean_canvas")

    assert exc_info.value.stage == "lean_canvas"
    assert exc_info.value.path == tmp_path / "lean_canvas.md"
    assert "Skill file for stage 'lean_canvas' was not found" in str(exc_info.value)
