"""Image validation utilities for KlingAI."""

import logging

from core.exceptions import ConfigurationError

logger = logging.getLogger(__name__)


def process_image_input(image_input: str) -> str:
    """
    Process image input (URL or Base64).

    Args:
        image_input: Image URL or Base64 string

    Returns:
        Processed image string (URL or cleaned Base64)

    Raises:
        ConfigurationError: Invalid image input

    Note:
        - If Base64, removes any data URI prefix
        - If URL, validates format
    """
    if not image_input:
        raise ConfigurationError("Image input cannot be empty")

    # Check if it's a data URL (Base64)
    if image_input.startswith("data:"):
        # Extract Base64 part (remove "data:image/png;base64," prefix)
        if ";base64," in image_input:
            base64_data = image_input.split(";base64,", 1)[1]
            logger.debug("Extracted Base64 data from data URL")
            return base64_data
        else:
            raise ConfigurationError(
                "Invalid data URL format (missing ';base64,')"
            )

    # Check if it's a URL
    elif image_input.startswith("http://") or image_input.startswith("https://"):
        logger.debug(f"Using image URL: {image_input[:50]}...")
        return image_input

    # Assume it's raw Base64
    else:
        logger.debug("Using raw Base64 image data")
        return image_input


def validate_image_format(image_data: bytes) -> None:
    """
    Validate image format and size.

    Args:
        image_data: Image bytes

    Raises:
        ConfigurationError: Invalid image format or size

    Note:
        This is a basic validation. Full validation happens on KlingAI side.
    """
    # Check file size
    size_mb = len(image_data) / (1024 * 1024)
    if size_mb > 10:
        raise ConfigurationError(
            f"Image size ({size_mb:.2f}MB) exceeds 10MB limit"
        )

    # Check image format (basic magic number check)
    if image_data.startswith(b'\xff\xd8\xff'):
        format_type = "JPEG"
    elif image_data.startswith(b'\x89PNG'):
        format_type = "PNG"
    else:
        raise ConfigurationError(
            "Unsupported image format (must be JPG or PNG)"
        )

    logger.debug(f"Image validated: {format_type}, {size_mb:.2f}MB")
