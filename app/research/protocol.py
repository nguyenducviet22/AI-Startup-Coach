"""The provider-neutral contract used by research services."""

from datetime import date
from typing import Protocol, runtime_checkable

from app.research.schemas import ProviderExtractResponse, ProviderSearchResponse


@runtime_checkable
class ResearchProvider(Protocol):
    async def search(
        self,
        *,
        query: str,
        topic: str,
        search_depth: str,
        max_results: int,
        include_domains: list[str],
        start_date: date | None,
        end_date: date | None,
    ) -> ProviderSearchResponse: ...

    async def extract(
        self,
        *,
        urls: list[str],
        query: str | None,
        extract_depth: str,
    ) -> ProviderExtractResponse: ...
