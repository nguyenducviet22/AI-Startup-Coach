"""Deterministic policy for grounding research evidence in chat prose."""

import re
from dataclasses import dataclass
from collections.abc import Iterable
from typing import Any

from app.research.schemas import LEGAL_NOTICE

_CITATION_PATTERN = re.compile(r"\[([^\]]+)\]")
_UNCERTAINTY_MESSAGE = (
    "I found relevant sources, but I cannot verify the proposed synthesis from the cited evidence yet. "
    "Please review the sources below and treat conclusions as uncertain."
)


@dataclass(frozen=True)
class ResearchPolicyResult:
    content: str
    research: dict[str, Any] | None


def apply_research_response_policy(
    content: str,
    tool_call_data: list[dict[str, Any]],
    *,
    prior_tool_call_data: Iterable[dict[str, Any]] = (),
) -> ResearchPolicyResult:
    """Sanitize a response using evidence from this turn and its chat session."""
    research = _latest_research_result(tool_call_data)
    current_evidence = _evidence_records(tool_call_data)
    prior_evidence = _evidence_records(prior_tool_call_data)
    evidence = [*prior_evidence, *current_evidence]
    if research is None and not evidence:
        return ResearchPolicyResult(content=content, research=None)

    if research is not None:
        research = {**research}
    source_ids = {
        source_id
        for item in evidence
        if isinstance(source_id := item.get("source_id"), str) and source_id
    }
    citations = set(_CITATION_PATTERN.findall(content))
    if content.strip() and not source_ids.intersection(citations):
        content = _UNCERTAINTY_MESSAGE

    if research is not None and any(item.get("legal_or_regulatory") is True for item in current_evidence):
        research["legal_notice"] = LEGAL_NOTICE
        if LEGAL_NOTICE not in content:
            content = f"{content}\n\n{LEGAL_NOTICE}"

    return ResearchPolicyResult(content=content, research=research)


def _latest_research_result(tool_call_data: Iterable[dict[str, Any]]) -> dict[str, Any] | None:
    results = [
        item.get("result", {}).get("research")
        for item in tool_call_data
        if item.get("tool_name") == "research_web" and item.get("result", {}).get("ok") is True
    ]
    return next((item for item in reversed(results) if isinstance(item, dict)), None)


def _evidence_records(tool_call_data: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for item in tool_call_data:
        research = item.get("result", {}).get("research")
        if not isinstance(research, dict):
            continue
        records.extend(entry for entry in research.get("evidence", []) if isinstance(entry, dict))
    return records
