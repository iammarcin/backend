"""Dataclasses describing deep research workflow results."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(slots=True)
class DeepResearchOutcome:
    """Container describing artefacts produced during deep research."""

    session_id: Optional[str]
    optimized_prompt: str
    research_response: str
    citations: List[Dict[str, Any]]
    stage_timings: Dict[str, float]
    message_ids: Optional[Dict[str, int]]
    notification_tagged: bool
    analysis_chunks: List[str]


__all__ = ["DeepResearchOutcome"]
