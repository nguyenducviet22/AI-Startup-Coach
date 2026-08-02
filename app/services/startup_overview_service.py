import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.stages import ALL_STAGES, validate_stage
from app.models.startup import Startup
from app.services.document_service import DOCUMENT_SPECS, StartupNotFoundError


DOCUMENT_API_TYPES = {
    "lean_canvas": "lean_canvas",
    "bmc": "bmc",
    "swot": "swot",
    "product_plan": "product_plan",
    "marketing_strategy": "marketing",
    "funding_guide": "funding",
}


class StartupOverviewService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_overview(self, startup_id: uuid.UUID | str) -> dict[str, Any]:
        startup_uuid = startup_id if isinstance(startup_id, uuid.UUID) else uuid.UUID(str(startup_id))
        startup = await self.session.scalar(select(Startup).where(Startup.id == startup_uuid))
        if startup is None:
            raise StartupNotFoundError(startup_uuid)

        document_progress: list[dict[str, Any]] = []
        recent_updates: list[dict[str, Any]] = []
        total_versions = 0
        for canonical_type, spec in DOCUMENT_SPECS.items():
            version_count = int(await self.session.scalar(
                select(func.count()).select_from(spec.model).where(spec.model.startup_id == startup_uuid)
            ) or 0)
            total_versions += version_count
            current = await self.session.scalar(
                select(spec.model).where(
                    spec.model.startup_id == startup_uuid,
                    spec.model.is_current.is_(True),
                ).order_by(spec.model.version.desc()).limit(1)
            )
            api_type = DOCUMENT_API_TYPES[canonical_type]
            document_progress.append({
                "doc_type": api_type,
                "exists": current is not None,
                "version": current.version if current is not None else None,
                "updated_at": current.created_at.isoformat() if current is not None and current.created_at else None,
            })
            rows = (await self.session.execute(
                select(spec.model).where(spec.model.startup_id == startup_uuid)
                .order_by(spec.model.created_at.desc(), spec.model.version.desc()).limit(5)
            )).scalars().all()
            recent_updates.extend({
                "doc_type": api_type,
                "version": row.version,
                "updated_at": row.created_at.isoformat() if row.created_at else None,
            } for row in rows)

        recent_updates.sort(key=lambda item: item["updated_at"] or "", reverse=True)
        stage = validate_stage(startup.current_stage)
        return {
            "current_stage": stage,
            "journey_completed_steps": ALL_STAGES.index(stage) + 1,
            "journey_total_steps": len(ALL_STAGES),
            "completed_documents": sum(1 for item in document_progress if item["exists"]),
            "total_documents": len(document_progress),
            "total_versions": total_versions,
            "documents": document_progress,
            "recent_updates": recent_updates[:5],
        }
