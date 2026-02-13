"""Dataclasses and types for semantic prompt enhancement."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Mapping


PromptInput = str | List[Mapping[str, Any]]


@dataclass(slots=True)
class SemanticEnhancementResult:
    """Result of semantic prompt enhancement."""

    enhanced_prompt: PromptInput
    original_prompt: PromptInput
    context_added: bool = False
    result_count: int = 0
    tokens_used: int = 0
    filters_applied: bool = False
    rate_limited: bool = False
    error: str | None = None
    _metadata_cache: dict[str, Any] = field(default_factory=dict, init=False, repr=False)

    @property
    def metadata(self) -> dict[str, Any]:
        """Return metadata dictionary for logging/events."""

        if not self._metadata_cache:
            meta = {
                "context_added": self.context_added,
                "result_count": self.result_count,
                "tokens_used": self.tokens_used,
                "filters_applied": self.filters_applied,
                "rate_limited": self.rate_limited,
            }
            if self.error:
                meta["error"] = self.error
            self._metadata_cache = meta
        return dict(self._metadata_cache)

    def to_tuple(self) -> tuple[PromptInput, dict[str, Any]]:
        """Convert to (enhanced_prompt, metadata) tuple for backward compatibility."""

        return (self.enhanced_prompt, self.metadata)


__all__ = ["SemanticEnhancementResult", "PromptInput"]
