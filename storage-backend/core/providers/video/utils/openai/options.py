"""Option resolution helpers for the OpenAI Sora provider."""

from __future__ import annotations

from typing import Any, Mapping, Sequence


def resolve_seconds(duration: Any, allowed_seconds: Sequence[int]) -> str:
    """Clamp requested duration to the closest supported OpenAI value."""

    try:
        requested = int(duration)
    except (TypeError, ValueError):
        requested = min(allowed_seconds)

    for allowed in sorted(allowed_seconds, reverse=True):
        if requested >= allowed:
            return str(allowed)
    return str(min(allowed_seconds))


def resolve_size(
    aspect_ratio: Any,
    size_override: Any,
    aspect_ratio_to_size: Mapping[str, str],
    available_sizes: set[str],
    resolution_presets: Mapping[str, Mapping[str, str]],
) -> str:
    """Resolve render size based on aspect ratio and optional override."""

    ratio = normalise_aspect_ratio(aspect_ratio, aspect_ratio_to_size)

    if isinstance(size_override, str):
        cleaned = size_override.lower().replace(" ", "")
        if cleaned in available_sizes:
            return cleaned
        preset = resolution_presets.get(cleaned)
        if preset and ratio in preset:
            return preset[ratio]

    return aspect_ratio_to_size.get(ratio, "720x1280")


def normalise_aspect_ratio(
    aspect_ratio: Any,
    aspect_ratio_to_size: Mapping[str, str],
    *,
    default: str = "9:16",
) -> str:
    """Normalise aspect ratio values to supported keys."""

    if isinstance(aspect_ratio, str):
        candidate = aspect_ratio.strip()
        if candidate in aspect_ratio_to_size:
            return candidate
        stripped = candidate.replace(" ", "")
        if stripped in aspect_ratio_to_size:
            return stripped
    return default


__all__ = ["normalise_aspect_ratio", "resolve_seconds", "resolve_size"]
