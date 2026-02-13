"""OpenAI Sora video generation provider."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from config.video.providers import openai as openai_config
from core.clients.ai import ai_clients
from core.exceptions import ProviderError
from core.providers.capabilities import ProviderCapabilities
from core.providers.base import BaseVideoProvider
from .utils.openai import operations as operations_utils
from .utils.openai import options as options_utils
from .utils.openai import references as references_utils

if TYPE_CHECKING:
    from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


def _coerce_positive_int(value: Any | None, *, default: int) -> int:
    """Convert ``value`` to a positive integer or return ``default``."""

    if value is None:
        return default

    try:
        numeric = int(value)
    except (TypeError, ValueError):
        logger.warning(
            "Invalid poll timeout value %r; falling back to %s seconds",
            value,
            default,
        )
        return default

    if numeric <= 0:
        logger.warning(
            "Non-positive poll timeout value %s received; falling back to %s seconds",
            numeric,
            default,
        )
        return default

    return numeric


def _coerce_positive_float(value: Any | None, *, default: float) -> float:
    """Convert ``value`` to a positive float or return ``default``."""

    if value is None:
        return default

    try:
        numeric = float(value)
    except (TypeError, ValueError):
        logger.warning(
            "Invalid poll interval value %r; falling back to %s seconds",
            value,
            default,
        )
        return default

    if numeric <= 0:
        logger.warning(
            "Non-positive poll interval value %s received; falling back to %s seconds",
            numeric,
            default,
        )
        return default

    return numeric


class OpenAIVideoProvider(BaseVideoProvider):
    """Video generation using OpenAI's Sora models."""

    def __init__(self) -> None:
        client = ai_clients.get("openai_async")
        if client is None or not hasattr(client, "videos"):
            raise ProviderError("OpenAI client not initialized", provider="openai_video")

        self.client: "AsyncOpenAI" = client  # type: ignore[assignment]
        self.capabilities = ProviderCapabilities(streaming=False, image_to_video=True)
        self.provider_name = "openai"

        self.default_model = openai_config.DEFAULT_MODEL
        self.allowed_seconds = openai_config.ALLOWED_DURATIONS
        self.aspect_ratio_to_size = openai_config.ASPECT_RATIO_TO_SIZE
        self.available_sizes = openai_config.AVAILABLE_SIZES
        self.resolution_presets = openai_config.RESOLUTION_PRESETS

    async def generate(
        self,
        prompt: str,
        model: str | None = None,
        duration_seconds: int = 5,
        aspect_ratio: str = "16:9",
        runtime: Optional["WorkflowRuntime"] = None,
        **kwargs: Any,
    ) -> bytes:
        """Generate a video from a text prompt using Sora."""

        if not prompt or not prompt.strip():
            raise ProviderError("Prompt cannot be empty", provider="openai_video")

        model_name = (model or self.default_model).strip() or self.default_model
        seconds = options_utils.resolve_seconds(duration_seconds, self.allowed_seconds)
        size_override = kwargs.get("size") or kwargs.get("resolution")
        size = options_utils.resolve_size(
            aspect_ratio,
            size_override,
            self.aspect_ratio_to_size,
            self.available_sizes,
            self.resolution_presets,
        )

        logger.info(
            "Generating OpenAI Sora video: model=%s seconds=%s size=%s",
            model_name,
            seconds,
            size,
        )

        poll_timeout_seconds = _coerce_positive_int(
            kwargs.pop("poll_timeout_seconds", None),
            default=openai_config.DEFAULT_POLL_TIMEOUT_SECONDS,
        )
        poll_interval_seconds = _coerce_positive_float(
            kwargs.pop("poll_interval_seconds", None),
            default=openai_config.DEFAULT_POLL_INTERVAL_SECONDS,
        )

        try:
            video = await operations_utils.create_video_job(
                self.client,
                prompt=prompt.strip(),
                model=model_name,
                seconds=seconds,
                size=size,
                provider_name="openai_video",
                poll_timeout_seconds=poll_timeout_seconds,
                poll_interval_seconds=poll_interval_seconds,
                runtime=runtime,
            )
        except ProviderError:
            raise
        except Exception as exc:  # pragma: no cover - defensive provider guard
            logger.error("OpenAI Sora generation failed: %s", exc, exc_info=True)
            raise ProviderError(
                f"OpenAI Sora generation failed: {exc}",
                provider="openai_video",
                original_error=exc,
            ) from exc

        return await operations_utils.download_video_bytes(
            self.client,
            video,
            provider_name="openai_video",
        )

    async def generate_from_image(
        self,
        prompt: str,
        image_url: str,
        runtime: Optional["WorkflowRuntime"] = None,
        **kwargs: Any,
    ) -> bytes:
        """Generate a video using an image reference."""

        if not prompt or not prompt.strip():
            raise ProviderError("Prompt cannot be empty", provider="openai_video")
        if not image_url or not isinstance(image_url, str):
            raise ProviderError("Image URL is required for image-to-video", provider="openai_video")

        model_name = (kwargs.get("model") or self.default_model).strip() or self.default_model
        seconds = options_utils.resolve_seconds(
            kwargs.get("duration_seconds", 4),
            self.allowed_seconds,
        )
        size_override = kwargs.get("size") or kwargs.get("resolution")
        aspect_ratio = kwargs.get("aspect_ratio", "9:16")
        size = options_utils.resolve_size(
            aspect_ratio,
            size_override,
            self.aspect_ratio_to_size,
            self.available_sizes,
            self.resolution_presets,
        )

        target_dimensions = references_utils.parse_render_dimensions(size)

        try:
            reference = await references_utils.prepare_input_reference(
                image_url,
                provider_name="openai_video",
                target_size=target_dimensions,
            )
        except ProviderError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Failed to prepare input reference: %s", exc, exc_info=True)
            raise ProviderError(
                f"Failed to prepare reference image: {exc}",
                provider="openai_video",
                original_error=exc,
            ) from exc

        actual_dimensions = references_utils.get_reference_dimensions(reference)
        if target_dimensions and actual_dimensions and actual_dimensions != target_dimensions:
            logger.debug(
                "Reference image resized to match target dimensions: requested=%s actual=%s",
                target_dimensions,
                actual_dimensions,
            )
        elif actual_dimensions:
            size = f"{actual_dimensions[0]}x{actual_dimensions[1]}"

        logger.info(
            "Generating OpenAI Sora image-to-video: model=%s seconds=%s size=%s",
            model_name,
            seconds,
            size,
        )

        poll_timeout_seconds = _coerce_positive_int(
            kwargs.pop("poll_timeout_seconds", None), default=240
        )
        poll_interval_seconds = _coerce_positive_float(
            kwargs.pop("poll_interval_seconds", None), default=5.0
        )

        try:
            video = await operations_utils.create_video_job(
                self.client,
                prompt=prompt.strip(),
                model=model_name,
                seconds=seconds,
                size=size,
                input_reference=reference,
                provider_name="openai_video",
                poll_timeout_seconds=poll_timeout_seconds,
                poll_interval_seconds=poll_interval_seconds,
                runtime=runtime,
            )
        except ProviderError:
            raise
        except Exception as exc:  # pragma: no cover - defensive provider guard
            logger.error("OpenAI Sora image-to-video failed: %s", exc, exc_info=True)
            raise ProviderError(
                f"OpenAI Sora image-to-video failed: {exc}",
                provider="openai_video",
                original_error=exc,
            ) from exc

        return await operations_utils.download_video_bytes(
            self.client,
            video,
            provider_name="openai_video",
        )
