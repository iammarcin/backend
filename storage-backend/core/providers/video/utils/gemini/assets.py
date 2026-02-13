"""Helpers for preparing Gemini video assets."""

from __future__ import annotations

import asyncio
import base64
import logging
from io import BytesIO
from typing import Any, Awaitable, Callable, Iterable, List, Optional, Tuple

import requests
from PIL import Image
from google.genai import types  # type: ignore

logger = logging.getLogger(__name__)

FetchImageCallable = Callable[[str], Tuple[bytes, Optional[str]]]
# Defensive imports for Google GenAI types that may not exist in all versions
try:
    ResolveReferenceType = Callable[[Any], Optional[types.VideoGenerationReferenceType]]
    ResolveMaskMode = Callable[[Any], Optional[types.VideoGenerationMaskMode]]
except AttributeError:
    # Fallback type aliases if the specific types don't exist
    from typing import TypeVar
    T = TypeVar('T')
    ResolveReferenceType = Callable[[Any], Optional[T]]
    ResolveMaskMode = Callable[[Any], Optional[T]]


def fetch_image_bytes(source: str) -> Tuple[bytes, Optional[str]]:
    """Fetch image bytes from the given URL or data URI."""

    if source.startswith("data:image"):
        header, _, data = source.partition(",")
        mime = header.split(";")[0].split(":", 1)[-1] if ":" in header else None
        return base64.b64decode(data), mime

    response = requests.get(source, timeout=60)
    response.raise_for_status()
    return response.content, response.headers.get("Content-Type")


def _detect_mime_type(image_bytes: bytes) -> str:
    """Detect MIME type from image bytes by checking file signature."""

    # Default fallback for very small or empty data
    if not image_bytes or len(image_bytes) < 2:
        return "image/png"

    # Check common image file signatures
    if image_bytes[:2] == b'\xff\xd8':
        return "image/jpeg"
    elif len(image_bytes) >= 8 and image_bytes[:8] == b'\x89PNG\r\n\x1a\n':
        return "image/png"
    elif len(image_bytes) >= 4 and image_bytes[:4] == b'GIF8':
        return "image/gif"
    elif len(image_bytes) >= 12 and image_bytes[:4] == b'RIFF' and image_bytes[8:12] == b'WEBP':
        return "image/webp"

    # Fallback: try using PIL to detect
    try:
        img = Image.open(BytesIO(image_bytes))
        format_lower = img.format.lower() if img.format else None
        if format_lower == 'jpeg':
            return "image/jpeg"
        elif format_lower == 'png':
            return "image/png"
        elif format_lower == 'gif':
            return "image/gif"
        elif format_lower == 'webp':
            return "image/webp"
    except Exception:
        pass

    return "image/png"  # Final fallback


async def prepare_reference_images(
    references: Any,
    image_preparer: Callable[[Any], Awaitable[Optional[types.Image]]],
    reference_type_resolver: ResolveReferenceType,
) -> Optional[List[types.VideoGenerationReferenceImage]]:
    """Normalise reference image entries for the Gemini API."""

    if not references:
        return None

    prepared: List[types.VideoGenerationReferenceImage] = []
    items: Iterable[Any]
    if isinstance(references, (list, tuple, set)):
        items = references
    else:
        items = [references]

    for entry in items:
        if isinstance(entry, types.VideoGenerationReferenceImage):
            prepared.append(entry)
            continue

        image = await image_preparer(entry)
        if not image:
            continue

        reference_type = reference_type_resolver(entry)
        prepared.append(
            types.VideoGenerationReferenceImage(
                image=image,
                referenceType=reference_type,
            )
        )

    return prepared or None


async def prepare_image(
    source: Any,
    fetcher: FetchImageCallable,
) -> Optional[types.Image]:
    """Prepare a single image input for Gemini video generation."""

    if source is None:
        return None
    if isinstance(source, types.Image):
        return source

    mime_type: Optional[str] = None
    image_bytes: Optional[bytes] = None
    image_url: Optional[str] = None

    if isinstance(source, dict):
        raw = source.get("image") or source
        if isinstance(raw, types.Image):
            return raw
        if isinstance(raw, dict):
            value = raw
        else:
            value = {}
        image_bytes_field = value.get("image_bytes")
        if isinstance(image_bytes_field, bytes):
            image_bytes = image_bytes_field
        elif isinstance(image_bytes_field, str):
            try:
                image_bytes = base64.b64decode(image_bytes_field)
            except (ValueError, TypeError):
                image_bytes = None
        mime_type = value.get("mime_type")
        image_url = value.get("image_url") or value.get("url")
    elif isinstance(source, bytes):
        image_bytes = source
    elif isinstance(source, str):
        image_url = source

    if image_bytes is None and image_url:
        image_bytes, resolved_mime = await asyncio.to_thread(fetcher, image_url)
        if not mime_type:
            mime_type = resolved_mime

    if image_bytes is None:
        return None

    # Ensure mime_type is set - detect from image bytes if not provided
    if not mime_type:
        mime_type = _detect_mime_type(image_bytes)

    logger.debug(
        "Creating Image object: mime_type=%s, bytes_length=%d",
        mime_type,
        len(image_bytes) if image_bytes else 0,
    )

    # Create Image object - pass raw bytes (SDK will handle base64 encoding)
    # The SDK annotation shows: image_bytes: Optional[bytes]
    try:
        # Pass raw bytes directly - SDK converts to base64 internally
        image = types.Image(image_bytes=image_bytes, mime_type=mime_type)
        logger.debug("Created Image with raw bytes (length=%d), mime_type=%s",
                     len(image_bytes), mime_type)

        return image
    except Exception as e:
        logger.error("Failed to create Image: %s", e, exc_info=True)
        raise


async def prepare_mask(
    mask_input: Any,
    image_preparer: Callable[[Any], Awaitable[Optional[types.Image]]],
    mask_mode_resolver: ResolveMaskMode,
) -> Optional[types.VideoGenerationMask]:
    """Prepare a mask payload for the Gemini API."""

    if not mask_input:
        return None
    if isinstance(mask_input, types.VideoGenerationMask):
        return mask_input
    if isinstance(mask_input, dict):
        image = await image_preparer(mask_input.get("image") or mask_input)
        if not image:
            return None
        mode_value = mask_input.get("mask_mode") or mask_input.get("mode")
        mask_mode = mask_mode_resolver(mode_value)
        return types.VideoGenerationMask(image=image, maskMode=mask_mode)
    return None


def load_image(image_bytes: bytes) -> Image.Image:
    """Load an image from raw bytes."""

    with Image.open(BytesIO(image_bytes)) as img:
        return img.copy()


__all__ = [
    "FetchImageCallable",
    "ResolveMaskMode",
    "ResolveReferenceType",
    "fetch_image_bytes",
    "load_image",
    "prepare_image",
    "prepare_mask",
    "prepare_reference_images",
]
