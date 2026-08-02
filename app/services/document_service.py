import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.documents import (
    Bmc,
    FundingGuide,
    LeanCanvas,
    MarketingStrategy,
    ProductPlan,
    Swot,
)
from app.models.startup import Startup


class DocumentServiceError(Exception):
    """Base error for document persistence failures."""


class StartupNotFoundError(DocumentServiceError):
    def __init__(self, startup_id: uuid.UUID) -> None:
        super().__init__(f"Startup '{startup_id}' was not found.")
        self.startup_id = startup_id


class UnknownDocumentTypeError(DocumentServiceError):
    def __init__(self, doc_type: str) -> None:
        super().__init__(f"Unknown document type '{doc_type}'.")
        self.doc_type = doc_type


class DocumentVersionNotFoundError(DocumentServiceError):
    def __init__(self, doc_type: str, version: int) -> None:
        super().__init__(f"Version {version} of document '{doc_type}' was not found.")
        self.doc_type = doc_type
        self.version = version


@dataclass(frozen=True)
class DocumentSpec:
    model: type
    fields: tuple[str, ...]


DOCUMENT_SPECS: dict[str, DocumentSpec] = {
    "lean_canvas": DocumentSpec(
        LeanCanvas,
        (
            "problem",
            "solution",
            "unique_value_proposition",
            "unfair_advantage",
            "customer_segments",
            "key_metrics",
            "channels",
            "cost_structure",
            "revenue_streams",
        ),
    ),
    "bmc": DocumentSpec(
        Bmc,
        (
            "key_partners",
            "key_activities",
            "key_resources",
            "value_propositions",
            "customer_relationships",
            "channels",
            "customer_segments",
            "cost_structure",
            "revenue_streams",
        ),
    ),
    "swot": DocumentSpec(Swot, ("strengths", "weaknesses", "opportunities", "threats")),
    "product_plan": DocumentSpec(ProductPlan, ("mvp_scope", "features", "timeline")),
    "marketing_strategy": DocumentSpec(
        MarketingStrategy,
        ("target_audience", "channels", "key_messages", "budget_estimate"),
    ),
    "funding_guide": DocumentSpec(
        FundingGuide,
        ("pitch_outline", "valuation_notes", "funding_stage_recommendation"),
    ),
}

DOCUMENT_ALIASES: dict[str, str] = {
    "marketing": "marketing_strategy",
    "funding": "funding_guide",
}

TOOL_DOCUMENT_TYPES: dict[str, str] = {
    "generate_lean_canvas": "lean_canvas",
    "generate_bmc": "bmc",
    "generate_swot": "swot",
    "generate_product_plan": "product_plan",
    "generate_marketing_strategy": "marketing_strategy",
    "generate_funding_guide": "funding_guide",
}


class DocumentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save_tool_document(
        self,
        *,
        startup_id: uuid.UUID | str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        doc_type = TOOL_DOCUMENT_TYPES.get(tool_name)
        if doc_type is None:
            raise UnknownDocumentTypeError(tool_name)

        return await self.save_document(
            startup_id=startup_id,
            doc_type=doc_type,
            data=arguments,
        )

    async def save_document(
        self,
        *,
        startup_id: uuid.UUID | str,
        doc_type: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        startup_uuid = _coerce_uuid(startup_id)
        canonical_doc_type = normalize_doc_type(doc_type)
        spec = _get_spec(canonical_doc_type)

        try:
            document = await self._insert_version_locked(
                startup_id=startup_uuid,
                doc_type=canonical_doc_type,
                spec=spec,
                data=data,
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

        return document

    async def get_current_document(
        self,
        *,
        startup_id: uuid.UUID | str,
        doc_type: str,
    ) -> dict[str, Any] | None:
        startup_uuid = _coerce_uuid(startup_id)
        canonical_doc_type = normalize_doc_type(doc_type)
        spec = _get_spec(canonical_doc_type)

        result = await self.session.execute(
            select(spec.model)
            .where(spec.model.startup_id == startup_uuid, spec.model.is_current.is_(True))
            .order_by(desc(spec.model.version))
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return _document_to_dict(row, canonical_doc_type, spec)

    async def get_document_history(
        self,
        *,
        startup_id: uuid.UUID | str,
        doc_type: str,
    ) -> list[dict[str, Any]]:
        startup_uuid = _coerce_uuid(startup_id)
        canonical_doc_type = normalize_doc_type(doc_type)
        spec = _get_spec(canonical_doc_type)

        result = await self.session.execute(
            select(spec.model)
            .where(spec.model.startup_id == startup_uuid)
            .order_by(desc(spec.model.version))
        )
        return [_document_to_dict(row, canonical_doc_type, spec) for row in result.scalars().all()]

    async def get_document_version(
        self,
        *,
        startup_id: uuid.UUID | str,
        doc_type: str,
        version: int,
    ) -> dict[str, Any] | None:
        startup_uuid = _coerce_uuid(startup_id)
        canonical_doc_type = normalize_doc_type(doc_type)
        spec = _get_spec(canonical_doc_type)
        result = await self.session.execute(
            select(spec.model).where(
                spec.model.startup_id == startup_uuid,
                spec.model.version == version,
            )
        )
        row = result.scalar_one_or_none()
        return None if row is None else _document_to_dict(row, canonical_doc_type, spec)

    async def restore_document_version(
        self,
        *,
        startup_id: uuid.UUID | str,
        doc_type: str,
        version: int,
    ) -> dict[str, Any]:
        startup_uuid = _coerce_uuid(startup_id)
        canonical_doc_type = normalize_doc_type(doc_type)
        spec = _get_spec(canonical_doc_type)
        source = await self.get_document_version(
            startup_id=startup_uuid,
            doc_type=canonical_doc_type,
            version=version,
        )
        if source is None:
            raise DocumentVersionNotFoundError(canonical_doc_type, version)

        try:
            restored = await self._insert_version_locked(
                startup_id=startup_uuid,
                doc_type=canonical_doc_type,
                spec=spec,
                data=source["content"],
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        return restored

    async def _insert_version_locked(
        self,
        *,
        startup_id: uuid.UUID,
        doc_type: str,
        spec: DocumentSpec,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        startup_result = await self.session.execute(
            select(Startup.id).where(Startup.id == startup_id).with_for_update()
        )
        if startup_result.scalar_one_or_none() is None:
            raise StartupNotFoundError(startup_id)

        current_result = await self.session.execute(
            select(spec.model)
            .where(spec.model.startup_id == startup_id, spec.model.is_current.is_(True))
            .order_by(desc(spec.model.version))
            .limit(1)
            .with_for_update()
        )
        current = current_result.scalar_one_or_none()

        version = 1
        if current is not None:
            current.is_current = False
            version = current.version + 1

        payload = {field: data.get(field) for field in spec.fields}
        row = spec.model(
            startup_id=startup_id,
            version=version,
            is_current=True,
            **payload,
        )
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return _document_to_dict(row, doc_type, spec)


def normalize_doc_type(doc_type: str) -> str:
    canonical = DOCUMENT_ALIASES.get(doc_type, doc_type)
    if canonical not in DOCUMENT_SPECS:
        raise UnknownDocumentTypeError(doc_type)
    return canonical


def _get_spec(doc_type: str) -> DocumentSpec:
    try:
        return DOCUMENT_SPECS[doc_type]
    except KeyError as exc:
        raise UnknownDocumentTypeError(doc_type) from exc


def _document_to_dict(row: Any, doc_type: str, spec: DocumentSpec) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "startup_id": str(row.startup_id),
        "doc_type": doc_type,
        "version": row.version,
        "is_current": row.is_current,
        "created_at": row.created_at.isoformat() if row.created_at is not None else None,
        "content": {field: getattr(row, field) for field in spec.fields},
    }


def _coerce_uuid(value: uuid.UUID | str) -> uuid.UUID:
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
