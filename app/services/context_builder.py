import json
from dataclasses import dataclass
from typing import Any

from app.core.config import Settings, get_settings
from app.domain.stages import validate_stage
from app.services.skill_loader import SkillLoader

BASE_COACHING_RULES = """You are the AI Startup Coach backend orchestrator.
Coach the student through one startup-building stage at a time.
Ask concise, practical questions when required information is missing.
Use only the tools exposed for the startup's current stage.
Do not auto-advance the startup stage; stage transitions happen only after explicit confirmation through the API.
Keep generated documents structured, actionable, and suitable for persistence by the backend.

Response formatting rules:
- Use valid Markdown.
- Put every numbered item on a separate line.
- Add one blank line between major sections.
- Never place multiple numbered items in the same paragraph.
- Use headings or bold labels consistently.
- Put the final question in a separate paragraph.
- Ask only one main question at a time."""


@dataclass(frozen=True)
class StartupContext:
    startup_id: str
    user_id: str
    current_stage: str
    name: str | None = None


def build_system_prompt(
    *,
    startup: StartupContext,
    skill_content: str,
    current_document: Any | None = None,
) -> str:
    stage = validate_stage(startup.current_stage)
    startup_name = startup.name or "Unnamed startup"

    sections = [
        "# Base Coaching Rules",
        BASE_COACHING_RULES,
        "# Startup State",
        f"startup_id: {startup.startup_id}\nuser_id: {startup.user_id}\nname: {startup_name}\ncurrent_stage: {stage}",
        "# Current Stage Skill",
        skill_content,
    ]
    if current_document is not None:
        sections.extend(["# Current Stage Document", _format_current_document(current_document)])
    return "\n\n".join(sections)


def truncate_history(
    history: list[dict[str, Any]],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    if limit < 0:
        raise ValueError("history limit must be greater than or equal to 0")
    if limit == 0:
        return []
    return history[-limit:]


def build_context_messages(
    *,
    startup: StartupContext,
    history: list[dict[str, Any]],
    user_message: str,
    current_document: Any | None = None,
    skill_loader: SkillLoader | None = None,
    settings: Settings | None = None,
) -> list[dict[str, Any]]:
    effective_settings = settings or get_settings()
    loader = skill_loader or SkillLoader()
    skill_content = loader.load(startup.current_stage)
    system_prompt = build_system_prompt(
        startup=startup,
        skill_content=skill_content,
        current_document=current_document,
    )
    return [
        {"role": "system", "content": system_prompt},
        *truncate_history(history, limit=effective_settings.chat_history_limit),
        {"role": "user", "content": user_message},
    ]


def _format_current_document(current_document: Any) -> str:
    if isinstance(current_document, str):
        return current_document
    return json.dumps(current_document, ensure_ascii=True, indent=2, sort_keys=True, default=str)
