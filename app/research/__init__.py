"""Stable provider-neutral interfaces for startup research."""

from app.research.errors import ResearchProviderError
from app.research.protocol import ResearchProvider
from app.research.schemas import (
    EvidenceAuthority,
    EvidenceRecord,
    ResearchCategory,
    ResearchRequest,
    ResearchResult,
    SearchDepth,
)

__all__ = [
    "EvidenceAuthority",
    "EvidenceRecord",
    "ResearchCategory",
    "ResearchProvider",
    "ResearchProviderError",
    "ResearchRequest",
    "ResearchResult",
    "SearchDepth",
]
