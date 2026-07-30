from pathlib import Path

from app.core.config import ROOT_DIR
from app.domain.stages import COMPLETED_STAGE, COACHING_STAGES, validate_stage

COMPLETED_STAGE_PROMPT = (
    "The student has completed the AI Startup Coach sequence. Help them review, refine, "
    "and connect prior work across stages without advancing to another coaching stage."
)

STAGE_SKILL_FILES: dict[str, str] = {
    "idea": "idea.md",
    "lean_canvas": "lean_canvas.md",
    "bmc": "bmc.md",
    "swot": "swot.md",
    "product_plan": "product_plan.md",
    "marketing": "marketing.md",
    "funding": "funding.md",
}


class SkillNotFoundError(RuntimeError):
    def __init__(self, stage: str, path: Path) -> None:
        self.stage = stage
        self.path = path
        super().__init__(f"Skill file for stage '{stage}' was not found at {path}.")


class SkillLoader:
    def __init__(self, skills_dir: Path | str | None = None) -> None:
        self.skills_dir = Path(skills_dir) if skills_dir is not None else ROOT_DIR / "skills"

    def load(self, current_stage: str) -> str:
        stage = validate_stage(current_stage)
        if stage == COMPLETED_STAGE:
            return COMPLETED_STAGE_PROMPT

        filename = STAGE_SKILL_FILES[stage]
        skill_path = self.skills_dir / filename
        if not skill_path.is_file():
            raise SkillNotFoundError(stage, skill_path)

        return skill_path.read_text(encoding="utf-8")


def load_skill_content(current_stage: str) -> str:
    return SkillLoader().load(current_stage)


assert set(STAGE_SKILL_FILES) == set(COACHING_STAGES)
