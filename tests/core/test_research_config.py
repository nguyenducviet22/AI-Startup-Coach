import inspect
from pathlib import Path

import pytest

from app.core.config import ROOT_DIR, Settings


RESEARCH_SETTINGS: dict[str, tuple[str, object]] = {
    "research_enabled": ("RESEARCH_ENABLED", True),
    "research_provider": ("RESEARCH_PROVIDER", "tavily"),
    "tavily_api_key": ("TAVILY_API_KEY", ""),
    "tavily_base_url": ("TAVILY_BASE_URL", "https://api.tavily.com"),
    "research_provider_timeout_seconds": ("RESEARCH_PROVIDER_TIMEOUT_SECONDS", 15.0),
    "research_provider_max_retries": ("RESEARCH_PROVIDER_MAX_RETRIES", 1),
    "research_session_hourly_call_limit": ("RESEARCH_SESSION_HOURLY_CALL_LIMIT", 8),
    "research_session_daily_credit_limit": ("RESEARCH_SESSION_DAILY_CREDIT_LIMIT", 20),
    "research_user_hourly_call_limit": ("RESEARCH_USER_HOURLY_CALL_LIMIT", 20),
    "research_user_daily_credit_limit": ("RESEARCH_USER_DAILY_CREDIT_LIMIT", 60),
    "research_cache_ttl_general_seconds": ("RESEARCH_CACHE_TTL_GENERAL_SECONDS", 21600),
    "research_cache_ttl_news_seconds": ("RESEARCH_CACHE_TTL_NEWS_SECONDS", 3600),
    "research_cache_ttl_pricing_seconds": ("RESEARCH_CACHE_TTL_PRICING_SECONDS", 3600),
    "research_cache_ttl_legal_seconds": ("RESEARCH_CACHE_TTL_LEGAL_SECONDS", 3600),
    "research_default_search_depth": ("RESEARCH_DEFAULT_SEARCH_DEPTH", "basic"),
    "research_max_results": ("RESEARCH_MAX_RESULTS", 5),
    "research_pricing_enabled": ("RESEARCH_PRICING_ENABLED", True),
    "tavily_basic_search_credits": ("TAVILY_BASIC_SEARCH_CREDITS", 1),
    "tavily_advanced_search_credits": ("TAVILY_ADVANCED_SEARCH_CREDITS", 2),
    "tavily_extract_credits_per_five_urls": ("TAVILY_EXTRACT_CREDITS_PER_FIVE_URLS", 1),
    "research_error_alert_threshold": ("RESEARCH_ERROR_ALERT_THRESHOLD", 0.5),
    "research_error_alert_window_seconds": ("RESEARCH_ERROR_ALERT_WINDOW_SECONDS", 300),
}


def test_research_settings_aliases_and_defaults() -> None:
    settings = _settings()

    for field_name, (alias, expected_default) in RESEARCH_SETTINGS.items():
        assert Settings.model_fields[field_name].alias == alias
        assert getattr(settings, field_name) == expected_default


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"RESEARCH_PROVIDER": "other"}, "RESEARCH_PROVIDER"),
        ({"RESEARCH_DEFAULT_SEARCH_DEPTH": "fast"}, "RESEARCH_DEFAULT_SEARCH_DEPTH"),
        ({"RESEARCH_PROVIDER_TIMEOUT_SECONDS": 0}, "RESEARCH_PROVIDER_TIMEOUT_SECONDS"),
        ({"RESEARCH_PROVIDER_MAX_RETRIES": -1}, "RESEARCH_PROVIDER_MAX_RETRIES"),
        ({"RESEARCH_SESSION_HOURLY_CALL_LIMIT": 0}, "RESEARCH_SESSION_HOURLY_CALL_LIMIT"),
        ({"RESEARCH_CACHE_TTL_GENERAL_SECONDS": 0}, "RESEARCH_CACHE_TTL_GENERAL_SECONDS"),
        ({"RESEARCH_MAX_RESULTS": 0}, "RESEARCH_MAX_RESULTS"),
        ({"TAVILY_BASIC_SEARCH_CREDITS": 0}, "TAVILY_BASIC_SEARCH_CREDITS"),
        ({"RESEARCH_ERROR_ALERT_THRESHOLD": 1.1}, "RESEARCH_ERROR_ALERT_THRESHOLD"),
        ({"RESEARCH_ERROR_ALERT_WINDOW_SECONDS": 0}, "RESEARCH_ERROR_ALERT_WINDOW_SECONDS"),
    ],
)
def test_research_settings_reject_invalid_values(overrides: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        _settings(**overrides)


def test_research_settings_aliases_are_not_duplicated_outside_config() -> None:
    config_path = ROOT_DIR / "app" / "core" / "config.py"
    for alias, _ in RESEARCH_SETTINGS.values():
        matches = [
            path
            for path in Path(ROOT_DIR / "app").rglob("*.py")
            if path != config_path and alias in path.read_text(encoding="utf-8")
        ]
        assert matches == [], f"{alias} must be read through Settings, not duplicated in {matches}."


def test_research_defaults_are_declared_only_in_settings() -> None:
    source = inspect.getsource(Settings)
    for field_name, (_, expected_default) in RESEARCH_SETTINGS.items():
        assert Settings.model_fields[field_name].default == expected_default
        assert field_name in source


def _settings(**overrides: object) -> Settings:
    return Settings(
        DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/coaching",
        JWT_SECRET="research-config-test-secret-with-at-least-thirty-two-bytes",
        **overrides,
    )
