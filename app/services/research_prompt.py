"""Composition-only policy for research-capable coaching prompts."""

from app.services.skill_loader import SkillLoader


RESEARCH_PROMPT_POLICY = """

Research policy:
- When using research_web, cite each factual claim with the returned source ID and URL, and state retrieval dates.
- Separate evidence from uncertainty; do not present unverified or conflicting evidence as fact.
- Legal or regulatory research must include the returned mandatory disclaimer and must not be presented as legal advice.
- Research-dependent document generation is a two-turn flow: first call research_web and present the evidence; only a later founder turn may call a generate_* tool using that evidence.
- Do not emit research_web and a research-dependent generate_* tool in the same tool-call batch. If both are emitted anyway, do not claim the generated document was research-informed.
""".strip()


class ResearchSkillLoader:
    """Decorates an existing loader without modifying the orchestrator."""

    def __init__(self, wrapped: SkillLoader) -> None:
        self._wrapped = wrapped

    def load(self, current_stage: str) -> str:
        return f"{self._wrapped.load(current_stage)}\n\n{RESEARCH_PROMPT_POLICY}"
