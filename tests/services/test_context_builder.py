from app.core.config import Settings
from app.services.context_builder import StartupContext, build_context_messages, build_system_prompt


class FakeSkillLoader:
    def __init__(self, content: str) -> None:
        self.content = content
        self.loaded_stage: str | None = None

    def load(self, current_stage: str) -> str:
        self.loaded_stage = current_stage
        return self.content


def test_build_system_prompt_includes_rules_skill_and_current_document() -> None:
    startup = StartupContext(
        startup_id="startup-1",
        user_id="user-1",
        current_stage="lean_canvas",
        name="TutorOS",
    )

    prompt = build_system_prompt(
        startup=startup,
        skill_content="# Skill: Lean Canvas\nAsk for canvas details.",
        current_document={"problem": "Tutors lack scheduling flow."},
    )

    assert "# Base Coaching Rules" in prompt
    assert "Do not auto-advance" in prompt
    assert "# Skill: Lean Canvas" in prompt
    assert "current_stage: lean_canvas" in prompt
    assert '"problem": "Tutors lack scheduling flow."' in prompt


def test_build_context_messages_truncates_oldest_history_and_preserves_system_prompt() -> None:
    history = [
        {"role": "user", "content": f"old-{index}"}
        for index in range(5)
    ]
    skill_loader = FakeSkillLoader("dynamic skill content")

    messages = build_context_messages(
        startup=StartupContext(startup_id="startup-1", user_id="user-1", current_stage="idea"),
        history=history,
        user_message="new user turn",
        skill_loader=skill_loader,
        settings=_settings(chat_history_limit=3),
    )

    assert skill_loader.loaded_stage == "idea"
    assert messages[0]["role"] == "system"
    assert "dynamic skill content" in messages[0]["content"]
    assert [message["content"] for message in messages[1:]] == [
        "old-2",
        "old-3",
        "old-4",
        "new user turn",
    ]


def test_build_context_messages_preserves_history_order_after_truncation() -> None:
    history = [
        {"role": "user" if index % 2 == 0 else "assistant", "content": str(index)}
        for index in range(8)
    ]

    messages = build_context_messages(
        startup=StartupContext(startup_id="startup-1", user_id="user-1", current_stage="bmc"),
        history=history,
        user_message="latest",
        skill_loader=FakeSkillLoader("bmc skill"),
        settings=_settings(chat_history_limit=4),
    )

    assert [message["content"] for message in messages] == [
        messages[0]["content"],
        "4",
        "5",
        "6",
        "7",
        "latest",
    ]


def test_build_context_messages_keeps_system_prompt_when_history_limit_is_zero() -> None:
    messages = build_context_messages(
        startup=StartupContext(startup_id="startup-1", user_id="user-1", current_stage="swot"),
        history=[{"role": "assistant", "content": "older"}],
        user_message="latest",
        skill_loader=FakeSkillLoader("swot skill"),
        settings=_settings(chat_history_limit=0),
    )

    assert [message["role"] for message in messages] == ["system", "user"]
    assert messages[1]["content"] == "latest"


def _settings(chat_history_limit: int) -> Settings:
    return Settings(
        DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/coaching",
        OPENROUTER_API_KEY="test-key",
        OPENROUTER_BASE_URL="https://openrouter.test/api/v1",
        OPENROUTER_MODEL="test-model",
        OPENROUTER_HTTP_REFERER="http://localhost:8000",
        OPENROUTER_X_TITLE="AI Startup Coach",
        CHAT_HISTORY_LIMIT=chat_history_limit,
        LLM_MAX_RETRIES=2,
        LLM_RETRY_BACKOFF_SECONDS=0,
    )
