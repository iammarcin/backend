"""Dataclasses describing AI model configurations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class ModelConfig:
    """Configuration for a specific AI model."""

    # Core identification
    model_name: str
    provider_name: str

    # API configuration
    api_type: str = "chat_completion"

    # Capability flags
    is_reasoning_model: bool = False
    support_image_input: bool = False
    support_audio_input: bool = False
    supports_streaming: bool = True
    supports_temperature: bool = True
    supports_reasoning_effort: bool = False
    supports_code_interpreter: bool = True

    # Constraints
    file_attached_message_limit: int = 3
    temperature_max: float = 2.0
    temperature_min: float = 0.0
    max_tokens_default: int = 4096
    context_window: Optional[int] = None

    # Reasoning settings
    reasoning_effort_values: Optional[list[str | int]] = None
    reasoning_model_counterpart: Optional[str] = None

    # Additional metadata
    supports_citations: bool = False
    category: Optional[str] = None
    input_cost_per_1m: Optional[float] = None
    output_cost_per_1m: Optional[float] = None
    audio_input_cost_per_min: Optional[float] = None
    audio_output_cost_per_min: Optional[float] = None
    supports_audio_output: bool = False
    supports_vad: bool = False
    supports_function_calling: bool = False
    voices: Optional[tuple[str, ...]] = None
    description: Optional[str] = None

    # Deprecation metadata
    is_deprecated: bool = False
    replacement_model: Optional[str] = None

    # Batch processing support
    supports_batch_api: bool = False
    batch_max_requests: int = 0
    batch_max_file_size_mb: int = 0

    def __post_init__(self) -> None:
        """Validate configuration invariants."""

        if self.supports_reasoning_effort and not self.reasoning_effort_values:
            raise ValueError(
                f"Model {self.model_name} supports reasoning effort but has no values configured",
            )

        valid_api_types = ("chat_completion", "responses_api", "realtime", "audio_transcription")
        if self.api_type not in valid_api_types:
            raise ValueError(
                f"Model {self.model_name} has invalid api_type '{self.api_type}'. "
                f"Must be one of {valid_api_types}",
            )


__all__ = ["ModelConfig"]
