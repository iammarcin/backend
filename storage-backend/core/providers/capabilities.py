"""Provider capability declarations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ProviderCapabilities:
    """Capabilities supported by an AI provider."""

    streaming: bool = False
    reasoning: bool = False
    citations: bool = False
    audio_input: bool = False
    image_input: bool = False
    file_input: bool = False
    audio_output: bool = False
    image_to_video: bool = False
    function_calling: bool = False
    batch_api: bool = False
    batch_max_requests: int = 0
    batch_max_file_size_mb: int = 0


__all__ = ["ProviderCapabilities"]
