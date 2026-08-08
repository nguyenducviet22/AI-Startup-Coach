from decimal import Decimal

from app.core.config import Settings, get_settings


_PRICE_PER_MILLION_TOKENS: dict[str, tuple[Decimal, Decimal]] = {
    "anthropic/claude-3.5-haiku": (Decimal("0.80"), Decimal("4.00")),
    "openai/gpt-4o-mini": (Decimal("0.15"), Decimal("0.60")),
}
_TOKENS_PER_MILLION = Decimal("1000000")
_TAVILY_USD_PER_CREDIT = Decimal("0.008")


def get_cost(
    model: str,
    prompt_tokens: int | None,
    completion_tokens: int | None,
    settings: Settings | None = None,
) -> tuple[Decimal | None, bool]:
    active_settings = settings or get_settings()
    if not active_settings.agentops_pricing_enabled:
        return None, True

    prices = _PRICE_PER_MILLION_TOKENS.get(model)
    if prices is None:
        return None, True

    input_price, output_price = prices
    prompt_count = Decimal(prompt_tokens or 0)
    completion_count = Decimal(completion_tokens or 0)
    cost = ((prompt_count * input_price) + (completion_count * output_price)) / _TOKENS_PER_MILLION
    return cost.quantize(Decimal("0.000001")), False


def get_research_cost(
    operation: str,
    credits_charged: int | None,
    *,
    extract_url_count: int | None = None,
    settings: Settings | None = None,
) -> tuple[Decimal | None, bool]:
    """Return Tavily cost from the real charged credits for a supported operation.

    Tavily charges per credit, not per request.  The configured operation credit
    quantities are used only when the provider does not report an actual usage;
    when it does, that real usage is always the billing basis.
    """
    active_settings = settings or get_settings()
    if not active_settings.research_pricing_enabled:
        return None, True

    configured_credits = _configured_research_credits(
        operation,
        extract_url_count=extract_url_count,
        settings=active_settings,
    )
    if configured_credits is None:
        return None, True

    billed_credits = configured_credits if credits_charged is None else credits_charged
    if billed_credits < 0:
        return None, True

    return (Decimal(billed_credits) * _TAVILY_USD_PER_CREDIT).quantize(Decimal("0.000001")), False


def _configured_research_credits(
    operation: str,
    *,
    extract_url_count: int | None,
    settings: Settings,
) -> int | None:
    if operation == "search_basic":
        return settings.tavily_basic_search_credits
    if operation == "search_advanced":
        return settings.tavily_advanced_search_credits
    if operation == "extract" and extract_url_count is not None and extract_url_count > 0:
        batches = (extract_url_count + 4) // 5
        return batches * settings.tavily_extract_credits_per_five_urls
    return None
