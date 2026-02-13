"""Helpers for assembling Gemini video generation requests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Mapping, Optional

from google.genai import types  # type: ignore
from google.genai import models  # type: ignore

from core.exceptions import ValidationError
from . import assets, options

# Defensive imports for Google GenAI types that may not exist in all versions
try:
    ImagePreparer = Callable[[Any], Awaitable[Optional[types.Image]]]
    ResolveReferenceType = Callable[[Any], Optional[types.VideoGenerationReferenceType]]
except AttributeError:
    # Fallback type aliases if the specific types don't exist
    from typing import TypeVar
    T = TypeVar('T')
    ImagePreparer = Callable[[Any], Awaitable[Optional[T]]]
    ResolveReferenceType = Callable[[Any], Optional[T]]


@dataclass(frozen=True)
class GeminiGenerationRequest:
    """Resolved payload for a Gemini video generation call."""

    duration: int
    aspect_ratio: str
    config: types.GenerateVideosConfig


async def build_generation_request(
    *,
    duration_seconds: Any,
    aspect_ratio: Any,
    kwargs: Mapping[str, Any] | dict[str, Any],
    number_of_videos: int,
    available_aspect_ratios: set[str],
    available_person_generation: set[str],
    available_resolutions: set[str],
    prepare_image: ImagePreparer,
    resolve_reference_type: ResolveReferenceType,
    default_aspect_ratio: str,
    enhance_prompt_default: bool = True,
) -> GeminiGenerationRequest:
    """Resolve inputs into a Gemini ``GenerateVideosConfig``."""

    _ensure_no_unsupported_options(kwargs)

    duration = options.clamp_duration(duration_seconds)
    resolved_aspect_ratio = options.normalise_aspect_ratio(
        aspect_ratio,
        available_aspect_ratios,
        default=default_aspect_ratio,
    )
    # Note: person_generation is not supported by veo-3.1-fast
    # Only include it if explicitly requested
    person_generation_value = kwargs.get("person_generation")
    person_generation = None
    if person_generation_value and person_generation_value in available_person_generation:
        person_generation = person_generation_value

    # Note: enhance_prompt is not supported by all models (e.g., veo-3.1-fast)
    # We don't include it by default; callers must explicitly request it
    enhance_prompt = None  # Don't include by default

    resolution = options.resolve_resolution(
        kwargs.get("resolution"),
        available_resolutions,
    )
    negative_prompt = kwargs.get("negative_prompt")

    reference_images = await assets.prepare_reference_images(
        kwargs.get("reference_images"),
        prepare_image,
        resolve_reference_type,
    )
    last_frame = await prepare_image(kwargs.get("last_frame"))

    config_kwargs: dict[str, Any] = {
        "aspect_ratio": resolved_aspect_ratio,
        "number_of_videos": number_of_videos,
        "duration_seconds": duration,
    }

    # Only include person_generation if explicitly set (not supported by veo-3.1-fast)
    if person_generation is not None:
        config_kwargs["person_generation"] = person_generation

    # Only include enhance_prompt if explicitly set (not supported by all models)
    if enhance_prompt is not None:
        config_kwargs["enhance_prompt"] = enhance_prompt

    if isinstance(negative_prompt, str) and negative_prompt.strip():
        config_kwargs["negative_prompt"] = negative_prompt.strip()
    if resolution:
        config_kwargs["resolution"] = resolution
    if reference_images:
        config_kwargs["reference_images"] = reference_images
    if last_frame:
        config_kwargs["last_frame"] = last_frame

    # Note: http_options is NOT passed to GenerateVideosConfig as per official SDK docs
    # It should be passed to the client method if needed, not to the config

    config = types.GenerateVideosConfig(**config_kwargs)
    _ensure_config_supported(config)
    return GeminiGenerationRequest(
        duration=duration,
        aspect_ratio=resolved_aspect_ratio,
        config=config,
    )


def _ensure_no_unsupported_options(kwargs: Mapping[str, Any] | dict[str, Any]) -> None:
    """Fail fast when callers provide Gemini options that the API rejects."""

    unsupported_options = {
        "fps": "Frame rate (fps) configuration is not supported by the Gemini video API.",
        "generate_audio": "Audio track generation is not supported by the Gemini video API.",
        "compression_quality": "Compression quality selection is not supported by the Gemini video API.",
        "mask": "Video masks are not supported by the Gemini video API.",
        "output_gcs_uri": "Direct GCS output is not supported by the Gemini video API.",
        "seed": "Deterministic seeds are not supported by the Gemini video API.",
        "pubsub_topic": "Pub/Sub delivery is not supported by the Gemini video API.",
        # Note: enhance_prompt is conditionally supported, so we don't block it here
    }

    for option, message in unsupported_options.items():
        if option not in kwargs:
            continue
        value = kwargs.get(option)
        if _has_value(value):
            raise ValidationError(message, field=option)


def _ensure_config_supported(config: types.GenerateVideosConfig) -> None:
    """Validate the config against the installed Google SDK without calling the API."""

    try:
        models._GenerateVideosConfig_to_mldev(config, {})  # type: ignore[attr-defined]
    except ValueError as exc:  # pragma: no cover - defensive compatibility check
        raise ValidationError(str(exc)) from exc


def _has_value(value: Any) -> bool:
    """Return ``True`` when the value should be considered as provided."""

    if value is None:
        return False
    if isinstance(value, (str, bytes)):
        return bool(value.strip()) if isinstance(value, str) else bool(value)
    if isinstance(value, Mapping):
        return bool(value)
    if isinstance(value, (list, tuple, set)):
        return bool(value)
    return True


__all__ = ["GeminiGenerationRequest", "build_generation_request"]
