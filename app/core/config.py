from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

MODEL_PLACEHOLDERS = frozenset(
    {
        "replace-with-openrouter-model-slug",
        "replace-with-9router-model-id",
    }
)


ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/coaching",
        alias="DATABASE_URL",
    )

    app_environment: str = Field(default="local", alias="APP_ENV")

    llm_proxy_api_key: str = Field(
        default="",
        alias="LLM_PROXY_API_KEY",
    )
    llm_proxy_base_url: str = Field(
        default="",
        alias="LLM_PROXY_BASE_URL",
    )
    llm_proxy_model: str = Field(
        default="",
        alias="LLM_PROXY_MODEL",
    )
    llm_proxy_max_tokens: int = Field(
        default=1024,
        alias="LLM_PROXY_MAX_TOKENS",
    )

    openrouter_api_key: str = Field(default="", alias="OPENROUTER_API_KEY")
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        alias="OPENROUTER_BASE_URL",
    )
    openrouter_model: str = Field(
        default="replace-with-openrouter-model-slug",
        alias="OPENROUTER_MODEL",
    )
    openrouter_max_tokens: int = Field(default=1024, alias="OPENROUTER_MAX_TOKENS")
    openrouter_http_referer: str = Field(
        default="http://localhost:8000",
        alias="OPENROUTER_HTTP_REFERER",
    )
    openrouter_x_title: str = Field(default="AI Startup Coach", alias="OPENROUTER_X_TITLE")

    chat_history_limit: int = Field(default=20, alias="CHAT_HISTORY_LIMIT")
    llm_max_retries: int = Field(default=2, alias="LLM_MAX_RETRIES")
    llm_retry_backoff_seconds: float = Field(default=1.0, alias="LLM_RETRY_BACKOFF_SECONDS")
    agentops_pricing_enabled: bool = Field(default=True, alias="AGENTOPS_PRICING_ENABLED")

    jwt_secret: str = Field(alias="JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=30, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(default=7, alias="REFRESH_TOKEN_EXPIRE_DAYS")

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_llm_proxy_configuration(self) -> "Settings":
        if not self.llm_proxy_api_key.strip():
            self.llm_proxy_api_key = self.openrouter_api_key
        if not self.llm_proxy_model.strip():
            self.llm_proxy_model = self.openrouter_model
        if (
            "llm_proxy_max_tokens" not in self.model_fields_set
            and self.openrouter_max_tokens != 1024
        ):
            self.llm_proxy_max_tokens = self.openrouter_max_tokens
        if not self.llm_proxy_base_url.strip():
            if self.app_environment.strip().lower() == "local":
                self.llm_proxy_base_url = "http://localhost:20128/v1"
            else:
                raise ValueError("LLM_PROXY_BASE_URL is required when APP_ENV is not local.")
        self.llm_proxy_base_url = self.llm_proxy_base_url.strip().rstrip("/")
        if self.app_environment.strip().lower() != "local":
            effective_model = self.llm_proxy_model.strip()
            if not effective_model or effective_model in MODEL_PLACEHOLDERS:
                raise ValueError(
                    "LLM_PROXY_MODEL must be explicitly configured when APP_ENV is not local."
                )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
