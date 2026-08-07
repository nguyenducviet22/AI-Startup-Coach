"""Startup-scoped cache for normalized research results."""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.research import ResearchCacheEntry
from app.research.schemas import ResearchCategory, ResearchResult
from app.services.research_errors import cache_conflict

NORMALIZER_SCHEMA_VERSION = "1"


class ResearchCacheService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    @staticmethod
    def build_key(
        *,
        startup_id: UUID,
        provider: str,
        operation: str,
        query_or_url: str,
        locale: str | None,
        topic: str,
        start_date: str | None,
        end_date: str | None,
        domains: list[str],
        max_results: int,
        depth: str,
        authority_mode: str,
        legal_mode: bool,
    ) -> str:
        payload = {
            "normalizer_schema_version": NORMALIZER_SCHEMA_VERSION,
            "startup_id": str(startup_id),
            "provider": provider.strip().lower(),
            "operation": operation,
            "query_or_url": " ".join(query_or_url.lower().split()),
            "locale": (locale or "").lower(),
            "topic": topic.lower(),
            "start_date": start_date,
            "end_date": end_date,
            "domains": sorted(domain.lower() for domain in domains),
            "max_results": max_results,
            "depth": depth.lower(),
            "authority_mode": authority_mode.lower(),
            "legal_mode": legal_mode,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    async def get(self, *, startup_id: UUID, cache_key: str, served_at: datetime | None = None) -> ResearchResult | None:
        current = served_at or datetime.now(UTC)
        row = await self.session.scalar(
            select(ResearchCacheEntry).where(
                ResearchCacheEntry.startup_id == startup_id,
                ResearchCacheEntry.cache_key == cache_key,
                ResearchCacheEntry.expires_at > current,
            )
        )
        if row is None:
            return None
        payload = dict(row.payload)
        payload["cache_hit"] = True
        payload["cache_key"] = cache_key
        payload["retrieved_at"] = row.retrieved_at.isoformat()
        payload["served_at"] = current.isoformat()
        return ResearchResult.model_validate(payload)

    async def put(
        self,
        *,
        startup_id: UUID,
        cache_key: str,
        operation: str,
        category: ResearchCategory,
        result: ResearchResult,
        now: datetime | None = None,
    ) -> None:
        current = now or datetime.now(UTC)
        payload = result.model_dump(mode="json")
        ttl = self._ttl(category)
        statement = insert(ResearchCacheEntry).values(
            startup_id=startup_id,
            cache_key=cache_key,
            operation=operation,
            category=category.value,
            payload=payload,
            retrieved_at=result.retrieved_at,
            expires_at=current + ttl,
        )
        statement = statement.on_conflict_do_update(
            constraint="uq_research_cache_entries_startup_id_cache_key",
            set_={
                "operation": statement.excluded.operation,
                "category": statement.excluded.category,
                "payload": statement.excluded.payload,
                "retrieved_at": statement.excluded.retrieved_at,
                "expires_at": statement.excluded.expires_at,
                "updated_at": current,
            },
        )
        try:
            await self.session.execute(statement)
            await self.session.commit()
        except SQLAlchemyError as exc:
            await self.session.rollback()
            raise cache_conflict() from exc

    def _ttl(self, category: ResearchCategory) -> timedelta:
        seconds = {
            ResearchCategory.GENERAL: self.settings.research_cache_ttl_general_seconds,
            ResearchCategory.NEWS: self.settings.research_cache_ttl_news_seconds,
            ResearchCategory.PRICING: self.settings.research_cache_ttl_pricing_seconds,
            ResearchCategory.LEGAL: self.settings.research_cache_ttl_legal_seconds,
        }[category]
        return timedelta(seconds=seconds)
