"""Basic validation utilities for KlingAI."""

import logging

from core.exceptions import ConfigurationError

logger = logging.getLogger(__name__)


def validate_model(provider, model: str) -> str:
    """Validate and normalize model name."""
    if model not in provider.allowed_models:
        raise ConfigurationError(
            f"Invalid model '{model}'. Allowed: {provider.allowed_models}"
        )
    return model


def validate_duration(provider, duration: int) -> int:
    """Validate and clamp duration to allowed values."""
    if duration not in provider.allowed_durations:
        # Clamp to nearest allowed value
        clamped = min(provider.allowed_durations, key=lambda x: abs(x - duration))
        logger.warning(
            f"Duration {duration}s not allowed, clamping to {clamped}s"
        )
        return clamped
    return duration


def validate_aspect_ratio(provider, aspect_ratio: str) -> str:
    """Validate aspect ratio."""
    if aspect_ratio not in provider.allowed_aspect_ratios:
        raise ConfigurationError(
            f"Invalid aspect_ratio '{aspect_ratio}'. "
            f"Allowed: {provider.allowed_aspect_ratios}"
        )
    return aspect_ratio


def validate_mode(provider, mode: str) -> str:
    """Validate generation mode."""
    if mode not in provider.allowed_modes:
        raise ConfigurationError(
            f"Invalid mode '{mode}'. Allowed: {provider.allowed_modes}"
        )
    return mode


def supports_cfg_scale(model: str) -> bool:
    """Check if model supports cfg_scale parameter."""
    # V2 models don't support cfg_scale
    return model.startswith("kling-v1")


def get_mode_for_model(model: str, requested_mode: str) -> str:
    """
    Get the effective mode for a model.

    V2.6 and O1 models only support 'pro' mode (std is invalid).
    Other models support both std and pro.

    Args:
        model: Model name
        requested_mode: Mode requested by user

    Returns:
        Effective mode to use
    """
    # V2.6 and O1 models only support 'pro' mode
    if model.startswith("kling-v2-6") or model.startswith("kling-o1"):
        if requested_mode != "pro":
            logger.info(f"Model {model} only supports 'pro' mode, overriding '{requested_mode}' -> 'pro'")
        return "pro"
    return requested_mode


def supports_audio_generation(model: str) -> bool:
    """
    Check if model supports native audio generation.

    V2.6 models generate synchronized audio with video in a single pass.
    Audio includes dialogue, sound effects, and ambient sounds.
    """
    return model.startswith("kling-v2-6") or model.startswith("kling-o1")


def is_omni_model(model: str) -> bool:
    """
    Check if model is an Omni (O1) model.

    Omni models support unified generation and editing with:
    - Text + multiple image references in one request
    - Video editing and inpainting
    - Shot continuation and keyframe control
    """
    return model.startswith("kling-o1")


def supports_camera_control(
    model: str,
    mode: str,
    duration: int
) -> bool:
    """
    Check if model/mode/duration supports camera control.

    Note: Support may vary, consult KlingAI docs for latest capabilities.
    """
    # This is a placeholder - adjust based on actual API capabilities
    # You may need to consult KlingAI documentation for exact support matrix
    return True


def validate_motion_brush_compatibility(
    model: str,
    mode: str,
    duration: int,
    has_motion_brush: bool
) -> None:
    """
    Validate motion brush compatibility with model/mode/duration.

    Args:
        model: Model name
        mode: Generation mode
        duration: Duration in seconds
        has_motion_brush: Whether motion brush is used

    Raises:
        ConfigurationError: Incompatible configuration

    Note:
        As of 2024-11-29, motion brush only works with kling-v1 model
        in std 5s and pro 5s modes.
    """
    if not has_motion_brush:
        return

    if not model.startswith("kling-v1"):
        raise ConfigurationError(
            f"Motion brush only supported with kling-v1 models, got {model}"
        )

    if duration != 5:
        logger.warning(
            f"Motion brush may not work with {duration}s duration. "
            "Recommended: 5s"
        )


def validate_image_list_consistency(
    image_urls: list[str]
) -> None:
    """
    Validate consistency across multiple images.

    Args:
        image_urls: List of image URLs/Base64

    Raises:
        ConfigurationError: Inconsistent images

    Note:
        This performs basic validation. Full validation happens server-side.
        Ideally all images should have similar aspect ratios.
    """
    if len(image_urls) < 2 or len(image_urls) > 4:
        raise ConfigurationError(
            f"Image count must be 2-4, got {len(image_urls)}"
        )

    # Additional validation could be added here:
    # - Check if all images are accessible
    # - Validate aspect ratio consistency
    # - Verify image formats match

    logger.debug(f"Validated {len(image_urls)} images for consistency")
