"""Building utilities for KlingAI."""

import logging
from typing import Dict, Any, List

from core.exceptions import ConfigurationError

logger = logging.getLogger(__name__)


def build_camera_control(camera_control: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build and validate camera control configuration.

    Args:
        camera_control: Camera control dict with 'type' and optional 'config'

    Returns:
        Validated camera control dict

    Raises:
        ConfigurationError: Invalid camera control configuration
    """
    from .models import CameraControlType

    try:
        # Parse and validate using Pydantic models
        control = CameraControl(**camera_control)

        # Build API payload
        result = {"type": control.type.value}

        if control.config:
            result["config"] = {
                "horizontal": control.config.horizontal,
                "vertical": control.config.vertical,
                "pan": control.config.pan,
                "tilt": control.config.tilt,
                "roll": control.config.roll,
                "zoom": control.config.zoom,
            }

        return result

    except ValueError as e:
        raise ConfigurationError(f"Invalid camera control: {str(e)}") from e


def build_dynamic_masks(
    dynamic_masks: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Build and validate dynamic masks configuration.

    Args:
        dynamic_masks: List of dynamic mask configs (max 6)

    Returns:
        Validated dynamic masks list

    Raises:
        ConfigurationError: Invalid mask configuration
    """
    from .models import DynamicMask
    from .validators_image import process_image_input

    if len(dynamic_masks) > 6:
        raise ConfigurationError(
            f"Maximum 6 dynamic masks allowed, got {len(dynamic_masks)}"
        )

    validated_masks = []

    for idx, mask_config in enumerate(dynamic_masks):
        try:
            # Validate using Pydantic model
            mask = DynamicMask(**mask_config)

            # Process mask image
            processed_mask = process_image_input(mask.mask)

            # Build API payload
            validated_masks.append({
                "mask": processed_mask,
                "trajectories": [
                    {"x": t.x, "y": t.y}
                    for t in mask.trajectories
                ]
            })

        except ValueError as e:
            raise ConfigurationError(
                f"Invalid dynamic mask #{idx}: {str(e)}"
            ) from e

    logger.debug(f"Built {len(validated_masks)} dynamic masks")
    return validated_masks


def get_video_metadata(
    task_result: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Extract video metadata from task result.

    Args:
        task_result: Task result dictionary

    Returns:
        Video metadata including parent info (if extension)

    Note:
        For extensions, includes parent_video information
    """
    metadata = {
        "videos": task_result.get("videos", [])
    }

    # Check for parent video (extension task)
    task_info = task_result.get("task_info", {})
    if "parent_video" in task_info:
        metadata["parent_video"] = task_info["parent_video"]
        logger.debug(
            f"Extension task - parent: {task_info['parent_video'].get('id')}"
        )

    return metadata


def validate_extension_duration(
    current_duration: int,
    extension_length: int = 5
) -> None:
    """
    Validate that extension won't exceed maximum duration.

    Args:
        current_duration: Current video duration in seconds
        extension_length: Extension length (typically 4-5s)

    Raises:
        ConfigurationError: If total would exceed 3 minutes

    Note:
        Maximum total video duration is 180 seconds (3 minutes)
    """
    max_duration = 180  # 3 minutes
    total_duration = current_duration + extension_length

    if total_duration > max_duration:
        raise ConfigurationError(
            f"Extension would exceed maximum duration of {max_duration}s. "
            f"Current: {current_duration}s, extension: {extension_length}s, "
            f"total would be: {total_duration}s"
        )

    logger.debug(
        f"Extension validation passed: {current_duration}s + {extension_length}s "
        f"= {total_duration}s (max: {max_duration}s)"
    )


def get_model_info(model: str) -> Dict[str, Any]:
    """Get model metadata."""
    from .validators_basic import supports_cfg_scale
    return {
        "model": model,
        "supports_cfg_scale": supports_cfg_scale(model),
        "family": "v1" if model.startswith("kling-v1") else "v2",
    }
