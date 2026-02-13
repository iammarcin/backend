"""Base Provider Interfaces - Abstract Contracts for All AI Providers
This module defines the abstract base classes that all AI provider implementations
must follow. These interfaces ensure consistent behavior across different providers
and enable polymorphic provider resolution.
Design Pattern:
    - Abstract base classes with @abstractmethod for required methods
    - Optional methods raise NotImplementedError by default
    - Capabilities system to advertise provider features
    - ModelConfig attachment for provider-specific configuration
Why This Architecture?:
    1. Polymorphism: Services work with any provider implementing the interface
    2. Type Safety: Static type checking ensures correct usage
    3. Discoverability: IDEs can show available methods
    4. Consistency: All providers have uniform error handling
    5. Extensibility: New providers just implement the interface
Provider Lifecycle:
    1. Provider class registered via register_*_provider()
    2. Factory function instantiates provider based on model
    3. set_model_config() attaches ModelConfig to provider instance
    4. Service calls generate() or stream() method
    5. Provider returns standardized response (ProviderResponse, bytes, TTSResult)
See Also:
    - core/providers/__init__.py: Provider registration
    - core/providers/factory.py: Provider resolution
    - core/providers/capabilities.py: Capability flags
    - core/providers/registry/: Model configuration registry
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, AsyncIterator, Dict, List, Optional

if TYPE_CHECKING:
    from features.chat.utils.websocket_runtime import WorkflowRuntime

from core.exceptions import ProviderError
from core.providers.capabilities import ProviderCapabilities
from core.providers.registry import ModelConfig
from core.providers.text_batch_utils import fallback_batch_generation
from core.pydantic_schemas import ProviderResponse

logger = logging.getLogger(__name__)


class BaseTextProvider(ABC):
    """Base interface for text generation providers."""

    capabilities: ProviderCapabilities
    _model_config: Optional[ModelConfig] = None

    def set_model_config(self, config: ModelConfig) -> None:
        """Attach the resolved model configuration to the provider instance."""

        self._model_config = config

    def get_model_config(self) -> Optional[ModelConfig]:
        """Return the model configuration resolved by the provider factory."""

        return self._model_config

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        model: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> ProviderResponse:
        """Generate a non-streaming response."""

    async def generate_batch(
        self,
        requests: List[Dict[str, Any]],
        **kwargs: Any,
    ) -> List[ProviderResponse]:
        """Generate multiple completions in batch mode.

        Args:
            requests: Collection of request payloads that mimic generate() inputs.
            **kwargs: Additional provider-specific overrides passed to generate().

        Returns:
            Responses in the same order as the supplied requests.
        """

        if not getattr(self.capabilities, "batch_api", False):
            logger.info(
                "%s doesn't support batch API, falling back to sequential generation",
                self.__class__.__name__,
            )
            return await fallback_batch_generation(self, requests, **kwargs)

        # Provider-specific batch implementation should override this method
        return await fallback_batch_generation(self, requests, **kwargs)

    async def stream(
        self,
        prompt: str,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        system_prompt: Optional[str] = None,
        messages: Optional[list[dict[str, Any]]] = None,
        runtime: Optional["WorkflowRuntime"] = None,
        **kwargs: Any,
    ) -> AsyncIterator[str | dict[str, str]]:
        """Stream response chunks from the provider.

        Implementations should yield either text strings or reasoning payloads
        shaped as ``{"type": "reasoning", "content": <str>}``.
        """

        raise NotImplementedError("Streaming not supported by this provider")

    async def generate_with_reasoning(
        self,
        prompt: str,
        reasoning_effort: str = "medium",
        **kwargs: Any,
    ) -> ProviderResponse:
        """Generate a response that includes a reasoning trace."""

        if not getattr(self.capabilities, "reasoning", False):
            raise NotImplementedError(f"{self.__class__.__name__} doesn't support reasoning")
        raise NotImplementedError

    async def generate_with_audio(
        self,
        audio_data: bytes,
        prompt: str | None = None,
        **kwargs: Any,
    ) -> ProviderResponse:
        """Generate a response using audio as input."""

        if not getattr(self.capabilities, "audio_input", False):
            raise NotImplementedError(f"{self.__class__.__name__} doesn't support audio input")
        raise NotImplementedError


class BaseImageProvider(ABC):
    """Base interface for image generation providers."""

    capabilities: ProviderCapabilities

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        model: str | None = None,
        width: int = 1024,
        height: int = 1024,
        runtime: Optional["WorkflowRuntime"] = None,
        **kwargs: Any,
    ) -> bytes:
        """Generate an image for the supplied prompt."""

        raise NotImplementedError


class BaseVideoProvider(ABC):
    """Base interface for video generation providers."""

    capabilities: ProviderCapabilities

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        model: str | None = None,
        duration_seconds: int = 5,
        aspect_ratio: str = "16:9",
        runtime: Optional["WorkflowRuntime"] = None,
        **kwargs: Any,
    ) -> bytes:
        """Generate a video for the supplied prompt."""

    async def generate_from_image(
        self,
        prompt: str,
        image_url: str,
        runtime: Optional["WorkflowRuntime"] = None,
        **kwargs: Any,
    ) -> bytes:
        """Generate a video from an input image."""

        if not getattr(self.capabilities, "image_to_video", False):
            raise NotImplementedError(
                f"{self.__class__.__name__} doesn't support image-to-video"
            )
        raise NotImplementedError
