from app.services.research_prompt import RESEARCH_PROMPT_POLICY, ResearchSkillLoader
from app.core.config import Settings
from app.services.context_builder import StartupContext
from app.services.orchestrator import AgentOrchestrator
from app.services.skill_loader import SkillLoader


class FakeSkillLoader:
    def load(self, current_stage: str) -> str:
        return f"Base skill for {current_stage}."


def test_research_prompt_decorates_stage_content_with_grounding_and_two_turn_policy() -> None:
    content = ResearchSkillLoader(FakeSkillLoader()).load("lean_canvas")  # type: ignore[arg-type]

    assert content.startswith("Base skill for lean_canvas.")
    assert RESEARCH_PROMPT_POLICY in content
    assert "cite each factual claim" in content
    assert "mandatory disclaimer" in content
    assert "two-turn flow" in content
    assert "same tool-call batch" in content


class PromptCapturingChatClient:
    def __init__(self) -> None:
        self.requests: list[dict] = []

    async def create_chat_completion(self, **kwargs):
        self.requests.append(kwargs)
        return {"choices": [{"message": {"content": "Coach response", "tool_calls": []}}]}


async def test_research_prompt_reaches_orchestrator_system_prompt() -> None:
    client = PromptCapturingChatClient()
    orchestrator = AgentOrchestrator(
        chat_client=client,
        skill_loader=ResearchSkillLoader(SkillLoader()),
        settings=Settings(
            _env_file=None,
            JWT_SECRET="research-prompt-test-secret-with-at-least-thirty-two-bytes",
            LLM_BASE_URL="http://localhost:20128/v1",
            LLM_MODEL="proxy-model",
            LLM_API_KEY="proxy-key",
        ),
    )

    await orchestrator.handle_turn(
        startup=StartupContext("startup", "user", "idea", "TutorOS"),
        history=[],
        user_message="Help me validate this idea.",
    )

    assert RESEARCH_PROMPT_POLICY in client.requests[0]["messages"][0]["content"]
