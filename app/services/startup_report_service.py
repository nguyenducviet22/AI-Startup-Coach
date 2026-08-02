import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.startup import Startup
from app.services.document_service import DocumentService, StartupNotFoundError

REPORT_SECTION_ORDER = ("overview", "lean_canvas", "bmc", "swot", "product_plan", "marketing", "basic_finance", "pitch_outline")
REPORT_TITLES = {
    "overview": "Tổng quan ý tưởng", "lean_canvas": "Lean Canvas", "bmc": "Business Model Canvas",
    "swot": "Phân tích SWOT", "product_plan": "Kế hoạch MVP", "marketing": "Kế hoạch Marketing",
    "basic_finance": "Tài chính cơ bản", "pitch_outline": "Pitch outline",
}


class ReportSectionSelectionError(ValueError):
    pass


class StartupReportService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_report(self, startup_id: uuid.UUID | str) -> dict[str, Any]:
        startup_uuid = startup_id if isinstance(startup_id, uuid.UUID) else uuid.UUID(str(startup_id))
        startup = await self.session.scalar(select(Startup).where(Startup.id == startup_uuid))
        if startup is None:
            raise StartupNotFoundError(startup_uuid)
        service = DocumentService(self.session)
        current = {doc_type: await service.get_current_document(startup_id=startup_uuid, doc_type=doc_type) for doc_type in ("lean_canvas", "bmc", "swot", "product_plan", "marketing", "funding")}
        lean, bmc, marketing, funding = (_content(current[key]) for key in ("lean_canvas", "bmc", "marketing", "funding"))
        content_by_section: dict[str, dict[str, Any]] = {
            "overview": {key: lean.get(key) for key in ("problem", "customer_segments", "solution", "unique_value_proposition")},
            "lean_canvas": lean,
            "bmc": _content(current["bmc"]),
            "swot": _content(current["swot"]),
            "product_plan": _content(current["product_plan"]),
            "marketing": marketing,
            "basic_finance": {"revenue_streams": lean.get("revenue_streams") or bmc.get("revenue_streams"), "cost_structure": lean.get("cost_structure") or bmc.get("cost_structure"), "marketing_budget": marketing.get("budget_estimate")},
            "pitch_outline": {"pitch_outline": funding.get("pitch_outline"), "funding_stage_recommendation": funding.get("funding_stage_recommendation")},
        }
        return {
            "startup_id": str(startup.id),
            "startup_name": startup.name or "Startup chưa đặt tên",
            "sections": [{"key": key, "title": REPORT_TITLES[key], "available": _has_value(content_by_section[key]), "content": content_by_section[key]} for key in REPORT_SECTION_ORDER],
        }

    @staticmethod
    def select_sections(report: dict[str, Any], requested: list[str] | None) -> list[dict[str, Any]]:
        available = {section["key"]: section for section in report["sections"] if section["available"]}
        if requested is None:
            keys = [key for key in REPORT_SECTION_ORDER if key in available]
        else:
            unknown = [key for key in requested if key not in REPORT_SECTION_ORDER]
            if unknown:
                raise ReportSectionSelectionError(f"Unknown report section: {unknown[0]}")
            selected = set(requested)
            keys = [key for key in REPORT_SECTION_ORDER if key in selected and key in available]
        return [available[key] for key in keys]


def _content(document: dict[str, Any] | None) -> dict[str, Any]:
    return dict(document["content"]) if document is not None else {}


def _has_value(value: Any) -> bool:
    if value in (None, "", [], {}):
        return False
    if isinstance(value, dict):
        return any(_has_value(item) for item in value.values())
    if isinstance(value, list):
        return any(_has_value(item) for item in value)
    return True
