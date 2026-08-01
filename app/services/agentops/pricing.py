from decimal import Decimal

from app.core.config import Settings, get_settings


_PRICE_PER_MILLION_TOKENS: dict[str, tuple[Decimal, Decimal]] = {
    "anthropic/claude-3.5-haiku": (Decimal("0.80"), Decimal("4.00")),
    "openai/gpt-4o-mini": (Decimal("0.15"), Decimal("0.60")),
}
_TOKENS_PER_MILLION = Decimal("1000000")


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
