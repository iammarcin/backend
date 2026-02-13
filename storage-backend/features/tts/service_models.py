"""Data containers shared across the text-to-speech service layer.

This module isolates the lightweight value objects that represent the
outputs of TTS operations. Keeping them separate from the orchestration
logic makes the primary service module smaller and easier to follow while
also making these types reusable from tests or helper utilities.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass(slots=True)
class TTSGenerationResult:
    """Summary returned once a synchronous TTS generation completes."""

    status: str
    result: str
    provider: str
    model: str
    voice: str | None
    format: str
    chunk_count: int
    metadata: Dict[str, Any]


@dataclass(slots=True)
class TTSBillingResult:
    """Wrapper around billing payloads returned by providers."""

    status: str
    result: Dict[str, Any]


@dataclass(slots=True)
class TTSStreamingMetadata:
    """High-level details about a streaming session once it finishes."""

    provider: str
    model: str | None
    voice: str | None
    format: str
    text_chunk_count: int
    audio_chunk_count: int
    audio_file_url: str | None = None
    storage_metadata: Dict[str, Any] | None = None


__all__ = [
    "TTSGenerationResult",
    "TTSBillingResult",
    "TTSStreamingMetadata",
]
