"""Common pydantic data models shared across the application."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict


class ProviderResponse(BaseModel):
    """Standardised response returned by provider implementations."""

    text: str
    model: str
    provider: str
    reasoning: Optional[str] = None
    citations: Optional[List[Dict[str, Any]]] = None
    metadata: Optional[Dict[str, Any]] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    requires_tool_action: bool = False

    model_config = ConfigDict(frozen=False)

    @property
    def custom_id(self) -> Optional[str]:
        """Return batch custom_id value if present."""

        if self.metadata:
            return self.metadata.get("custom_id")
        return None

    @property
    def has_error(self) -> bool:
        """True when this response captured an error."""

        if self.metadata:
            return "error" in self.metadata
        return False


__all__ = ["ProviderResponse"]
