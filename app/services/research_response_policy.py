"""Deterministic policy for grounding research evidence in chat prose."""

import re
from dataclasses import dataclass
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


def apply_research_response_policy(content: str, tool_call_data: list[dict[str, Any]]) -> ResearchPolicyResult:
    results = [
        item.get("result", {}).get("research")
        for item in tool_call_data
        if item.get("tool_name") == "research_web" and item.get("result", {}).get("ok") is True
    ]
    research = next((item for item in reversed(results) if isinstance(item, dict)), None)
    if research is None:
        return ResearchPolicyResult(content=content, research=None)
    research = {**research}

    evidence = [item for item in research.get("evidence", []) if isinstance(item, dict)]
    source_ids = {item.get("source_id") for item in evidence}
    citations = set(_CITATION_PATTERN.findall(content))
    if content.strip() and not source_ids.intersection(citations):
        content = _UNCERTAINTY_MESSAGE

    if any(item.get("legal_or_regulatory") is True for item in evidence):
        research["legal_notice"] = LEGAL_NOTICE
        if LEGAL_NOTICE not in content:
            content = f"{content}\n\n{LEGAL_NOTICE}"

    return ResearchPolicyResult(content=content, research=research)
