"""Utility helpers for Gemini video option resolution."""

from __future__ import annotations

from typing import Any, Mapping, Optional

from google.genai import types  # type: ignore


def normalise_aspect_ratio(
    aspect_ratio: Any,
    available_aspect_ratios: set[str],
    *,
    default: str = "9:16",
) -> str:
    """Normalise and validate aspect ratio input."""

    if isinstance(aspect_ratio, str) and aspect_ratio in available_aspect_ratios:
        return aspect_ratio
    return default


def resolve_person_generation(
    value: Any,
    available_values: set[str],
    *,
    default: str = "allow_adult",
) -> str:
    """Resolve person generation setting ensuring allowed values."""

    if isinstance(value, str) and value in available_values:
        return value
    return default


def resolve_resolution(value: Any, available_values: set[str]) -> Optional[str]:
    """Validate resolution value supplied by the client."""

    if isinstance(value, str):
        candidate = value.lower()
        if candidate in available_values:
            return candidate
    return None


def resolve_reference_type(
    entry: Any,
    reference_map: Mapping[str, types.VideoGenerationReferenceType],
) -> Optional[types.VideoGenerationReferenceType]:
    """Map reference type string to the Gemini enum."""

    candidate = None
    if isinstance(entry, dict):
        candidate = entry.get("reference_type") or entry.get("type")

    if isinstance(candidate, types.VideoGenerationReferenceType):
        return candidate
    if isinstance(candidate, str):
        return reference_map.get(candidate.lower())
    return None


def clamp_duration(duration: Any, *, minimum: int = 4, maximum: int = 8) -> int:
    """Clamp duration to provider allowed range (4-8 seconds for Veo 3.1)."""

    try:
        duration_int = int(duration)
    except (TypeError, ValueError):
        return minimum
    return max(minimum, min(maximum, duration_int))


def resolve_number_of_videos(value: Any, *, maximum: int = 2) -> int:
    """Validate requested number of video outputs."""

    try:
        number = int(value)
    except (TypeError, ValueError):
        return 1
    return 1 if number < 2 else min(number, maximum)


__all__ = [
    "clamp_duration",
    "normalise_aspect_ratio",
    "resolve_number_of_videos",
    "resolve_person_generation",
    "resolve_reference_type",
    "resolve_resolution",
]
