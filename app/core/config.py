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

    llm_provider: str = Field(default="9router", alias="LLM_PROVIDER")
    llm_api_key: str = Field(default="", alias="LLM_API_KEY")
    llm_base_url: str = Field(default="", alias="LLM_BASE_URL")
    llm_model: str = Field(default="", alias="LLM_MODEL")
    llm_max_tokens: int = Field(default=4096, alias="LLM_MAX_TOKENS")

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
        default=4096,
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
    openrouter_max_tokens: int = Field(default=4096, alias="OPENROUTER_MAX_TOKENS")
    openrouter_http_referer: str = Field(
        default="http://localhost:8000",
        alias="OPENROUTER_HTTP_REFERER",
    )
    openrouter_x_title: str = Field(default="AI Startup Coach", alias="OPENROUTER_X_TITLE")

    chat_history_limit: int = Field(default=20, alias="CHAT_HISTORY_LIMIT")
    llm_max_retries: int = Field(default=2, alias="LLM_MAX_RETRIES")
    llm_retry_backoff_seconds: float = Field(default=1.0, alias="LLM_RETRY_BACKOFF_SECONDS")
    agentops_pricing_enabled: bool = Field(default=True, alias="AGENTOPS_PRICING_ENABLED")

    research_enabled: bool = Field(default=True, alias="RESEARCH_ENABLED")
    research_provider: str = Field(default="tavily", alias="RESEARCH_PROVIDER")
    tavily_api_key: str = Field(default="", alias="TAVILY_API_KEY")
    tavily_base_url: str = Field(default="https://api.tavily.com", alias="TAVILY_BASE_URL")
    research_provider_timeout_seconds: float = Field(
        default=15.0,
        alias="RESEARCH_PROVIDER_TIMEOUT_SECONDS",
    )
    research_provider_max_retries: int = Field(default=1, alias="RESEARCH_PROVIDER_MAX_RETRIES")
    research_session_hourly_call_limit: int = Field(
        default=8,
        alias="RESEARCH_SESSION_HOURLY_CALL_LIMIT",
    )
    research_session_daily_credit_limit: int = Field(
        default=20,
        alias="RESEARCH_SESSION_DAILY_CREDIT_LIMIT",
    )
    research_user_hourly_call_limit: int = Field(
        default=20,
        alias="RESEARCH_USER_HOURLY_CALL_LIMIT",
    )
    research_user_daily_credit_limit: int = Field(
        default=60,
        alias="RESEARCH_USER_DAILY_CREDIT_LIMIT",
    )
    research_cache_ttl_general_seconds: int = Field(
        default=21600,
        alias="RESEARCH_CACHE_TTL_GENERAL_SECONDS",
    )
    research_cache_ttl_news_seconds: int = Field(
        default=3600,
        alias="RESEARCH_CACHE_TTL_NEWS_SECONDS",
    )
    research_cache_ttl_pricing_seconds: int = Field(
        default=3600,
        alias="RESEARCH_CACHE_TTL_PRICING_SECONDS",
    )
    research_cache_ttl_legal_seconds: int = Field(
        default=3600,
        alias="RESEARCH_CACHE_TTL_LEGAL_SECONDS",
    )
    research_default_search_depth: str = Field(default="basic", alias="RESEARCH_DEFAULT_SEARCH_DEPTH")
    research_max_results: int = Field(default=5, alias="RESEARCH_MAX_RESULTS")
    research_pricing_enabled: bool = Field(default=True, alias="RESEARCH_PRICING_ENABLED")
    tavily_basic_search_credits: int = Field(default=1, alias="TAVILY_BASIC_SEARCH_CREDITS")
    tavily_advanced_search_credits: int = Field(default=2, alias="TAVILY_ADVANCED_SEARCH_CREDITS")
    tavily_extract_credits_per_five_urls: int = Field(
        default=1,
        alias="TAVILY_EXTRACT_CREDITS_PER_FIVE_URLS",
    )
    research_error_alert_threshold: float = Field(
        default=0.5,
        alias="RESEARCH_ERROR_ALERT_THRESHOLD",
    )
    research_error_alert_window_seconds: int = Field(
        default=300,
        alias="RESEARCH_ERROR_ALERT_WINDOW_SECONDS",
    )

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
    def validate_llm_configuration(self) -> "Settings":
        if "llm_api_key" not in self.model_fields_set and self.llm_proxy_api_key.strip():
            self.llm_api_key = self.llm_proxy_api_key or self.openrouter_api_key
        if "llm_api_key" not in self.model_fields_set and not self.llm_api_key.strip():
            self.llm_api_key = self.openrouter_api_key
        if "llm_model" not in self.model_fields_set and self.llm_proxy_model.strip():
            self.llm_model = self.llm_proxy_model or self.openrouter_model
        if "llm_model" not in self.model_fields_set and not self.llm_model.strip():
            self.llm_model = self.openrouter_model
        if "llm_max_tokens" not in self.model_fields_set:
            if "llm_proxy_max_tokens" in self.model_fields_set:
                self.llm_max_tokens = self.llm_proxy_max_tokens
            elif self.openrouter_max_tokens != 4096:
                self.llm_max_tokens = self.openrouter_max_tokens
        if "llm_base_url" not in self.model_fields_set:
            if "llm_proxy_base_url" in self.model_fields_set and self.llm_proxy_base_url.strip():
                self.llm_base_url = self.llm_proxy_base_url
            elif "openrouter_base_url" in self.model_fields_set:
                self.llm_base_url = self.openrouter_base_url
        if not self.llm_base_url.strip():
            if self.app_environment.strip().lower() == "local":
                self.llm_base_url = "http://localhost:20128/v1"
            else:
                raise ValueError("LLM_BASE_URL is required when APP_ENV is not local.")
        self.llm_base_url = self.llm_base_url.strip().rstrip("/")
        if self.app_environment.strip().lower() != "local":
            effective_model = self.llm_model.strip()
            if not effective_model or effective_model in MODEL_PLACEHOLDERS:
                raise ValueError(
                    "LLM_MODEL must be explicitly configured when APP_ENV is not local."
                )

        self.research_provider = self.research_provider.strip().lower()
        if self.research_provider != "tavily":
            raise ValueError("RESEARCH_PROVIDER must be 'tavily'.")
        self.tavily_base_url = self.tavily_base_url.strip().rstrip("/")
        if not self.tavily_base_url:
            raise ValueError("TAVILY_BASE_URL must not be empty.")
        if self.research_default_search_depth not in {"basic", "advanced"}:
            raise ValueError("RESEARCH_DEFAULT_SEARCH_DEPTH must be 'basic' or 'advanced'.")
        if self.research_provider_timeout_seconds <= 0:
            raise ValueError("RESEARCH_PROVIDER_TIMEOUT_SECONDS must be greater than 0.")
        if self.research_provider_max_retries < 0:
            raise ValueError("RESEARCH_PROVIDER_MAX_RETRIES must be greater than or equal to 0.")
        for field_name in (
            "research_session_hourly_call_limit",
            "research_session_daily_credit_limit",
            "research_user_hourly_call_limit",
            "research_user_daily_credit_limit",
            "research_cache_ttl_general_seconds",
            "research_cache_ttl_news_seconds",
            "research_cache_ttl_pricing_seconds",
            "research_cache_ttl_legal_seconds",
            "research_max_results",
            "tavily_basic_search_credits",
            "tavily_advanced_search_credits",
            "tavily_extract_credits_per_five_urls",
            "research_error_alert_window_seconds",
        ):
            if getattr(self, field_name) <= 0:
                alias = type(self).model_fields[field_name].alias
                raise ValueError(f"{alias} must be greater than 0.")
        if not 0 <= self.research_error_alert_threshold <= 1:
            raise ValueError("RESEARCH_ERROR_ALERT_THRESHOLD must be between 0 and 1.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
