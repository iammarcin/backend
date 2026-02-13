"""Streaming-related types and enumerations."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict

from pydantic import BaseModel, Field


class StreamEventType(str, Enum):
    """Enumeration of supported streaming event types."""

    TEXT = "text"
    REASONING = "reasoning"
    CITATIONS = "citations"
    AUDIO = "audio"
    ERROR = "error"
    COMPLETE = "complete"


class StreamEvent(BaseModel):
    """Payload delivered through streaming queues."""

    type: StreamEventType
    content: Any
    metadata: Dict[str, Any] = Field(default_factory=dict)
