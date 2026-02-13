"""Reference asset helpers for the OpenAI Sora provider."""

from __future__ import annotations

import asyncio
import base64
from io import BytesIO
from typing import Any, Optional, Tuple

import requests
from PIL import Image, ImageOps

from core.exceptions import ProviderError

FetchResult = Tuple[bytes, Optional[str]]

try:  # Pillow < 10 compatibility
    _RESAMPLE = Image.Resampling.LANCZOS  # type: ignore[attr-defined]
except AttributeError:  # pragma: no cover - fallback for older Pillow
    _RESAMPLE = Image.LANCZOS


def parse_render_dimensions(size: str | None) -> Tuple[int, int] | None:
    """Parse a render size string into width/height integers."""

    if not size or not isinstance(size, str):
        return None
    parts = size.lower().replace(" ", "").split("x", 1)
    if len(parts) != 2:
        return None
    try:
        width = int(parts[0])
        height = int(parts[1])
    except ValueError:
        return None
    if width <= 0 or height <= 0:
        return None
    return width, height


async def prepare_input_reference(
    source: Any,
    *,
    provider_name: str = "openai_video",
    target_size: Tuple[int, int] | None = None,
) -> Tuple[str, bytes, str]:
    """Normalise reference image input into the tuple expected by Sora."""

    if isinstance(source, (list, tuple, set)):
        for item in source:
            try:
                return await prepare_input_reference(
                    item,
                    provider_name=provider_name,
                    target_size=target_size,
                )
            except ProviderError:
                continue
        raise ProviderError("No valid reference image supplied", provider=provider_name)

    if isinstance(source, dict):
        image_bytes, mime = decode_image_bytes(source)
        if image_bytes:
            processed_bytes, processed_mime = await asyncio.to_thread(
                normalise_image_bytes,
                image_bytes,
                mime or "image/png",
                target_size,
                provider_name,
            )
            return build_reference_tuple(processed_bytes, processed_mime, provider_name)
        url = source.get("image_url") or source.get("url")
        if isinstance(url, str):
            return await prepare_input_reference(
                url,
                provider_name=provider_name,
                target_size=target_size,
            )
        raise ProviderError("Invalid reference image payload", provider=provider_name)

    if isinstance(source, bytes):
        processed_bytes, processed_mime = await asyncio.to_thread(
            normalise_image_bytes,
            source,
            "image/png",
            target_size,
            provider_name,
        )
        return build_reference_tuple(processed_bytes, processed_mime, provider_name)

    if isinstance(source, str):
        image_bytes, mime_type = await asyncio.to_thread(fetch_image_bytes, source)
        processed_bytes, processed_mime = await asyncio.to_thread(
            normalise_image_bytes,
            image_bytes,
            mime_type or "image/png",
            target_size,
            provider_name,
        )
        return build_reference_tuple(processed_bytes, processed_mime, provider_name)

    raise ProviderError("Unsupported reference image type", provider=provider_name)


def decode_image_bytes(payload: dict[str, Any]) -> Tuple[Optional[bytes], Optional[str]]:
    """Decode base64-encoded reference image bytes."""

    image_bytes = payload.get("image_bytes")
    mime_type = payload.get("mime_type")
    if isinstance(image_bytes, bytes):
        return image_bytes, mime_type
    if isinstance(image_bytes, str):
        try:
            return base64.b64decode(image_bytes), mime_type
        except (ValueError, TypeError):  # pragma: no cover - invalid base64 guard
            return None, mime_type
    return None, mime_type


def build_reference_tuple(image_bytes: bytes, mime_type: str, provider_name: str) -> Tuple[str, bytes, str]:
    """Build the tuple required by ``input_reference`` API parameter."""

    if not image_bytes:
        raise ProviderError("Reference image payload is empty", provider=provider_name)
    mime = mime_type or "image/png"
    extension = extension_from_mime(mime)
    return (f"reference.{extension}", image_bytes, mime)


def fetch_image_bytes(source: str) -> FetchResult:
    """Download image data from a remote source or data URI."""

    if source.startswith("data:image"):
        header, _, data = source.partition(",")
        mime = header.split(";")[0].split(":", 1)[-1] if ":" in header else None
        return base64.b64decode(data), mime

    try:
        response = requests.get(source, timeout=60)
        response.raise_for_status()
    except Exception as exc:  # pragma: no cover - network guard
        raise ProviderError(
            f"Failed to download reference image: {exc}",
            provider="openai_video",
        ) from exc

    return response.content, response.headers.get("Content-Type")


def extension_from_mime(mime_type: str) -> str:
    """Infer a safe file extension from a MIME type string."""

    if not mime_type or "/" not in mime_type:
        return "png"
    return mime_type.split("/", 1)[-1]


def normalise_image_bytes(
    image_bytes: bytes,
    mime_type: str,
    target_size: Tuple[int, int] | None,
    provider_name: str,
) -> Tuple[bytes, str]:
    """Ensure the reference image matches the requested render size."""

    if not image_bytes:
        raise ProviderError("Reference image payload is empty", provider=provider_name)

    mime = mime_type or "image/png"
    if not target_size:
        return image_bytes, mime

    try:
        resized_bytes, resolved_mime = resize_image_bytes(image_bytes, target_size, mime)
    except ProviderError:
        raise
    except Exception as exc:  # pragma: no cover - defensive conversion guard
        raise ProviderError(
            f"Failed to prepare reference image: {exc}",
            provider=provider_name,
            original_error=exc,
        ) from exc

    return resized_bytes, resolved_mime


def resize_image_bytes(
    image_bytes: bytes,
    target_size: Tuple[int, int],
    mime_type: str,
) -> Tuple[bytes, str]:
    """Resize image bytes to match the requested width and height."""

    width, height = target_size
    if width <= 0 or height <= 0:
        raise ProviderError("Target size must be positive", provider="openai_video")

    with Image.open(BytesIO(image_bytes)) as img:
        if img.size == target_size:
            return image_bytes, mime_type or mime_from_format(img.format)

        fitted = ImageOps.fit(img, target_size, method=_RESAMPLE, centering=(0.5, 0.5))
        buffer = BytesIO()
        save_format = normalise_pillow_format(img.format)
        if save_format == "JPEG" and "A" in fitted.getbands():
            fitted = fitted.convert("RGB")
        fitted.save(buffer, format=save_format)
        return buffer.getvalue(), mime_from_format(save_format)


def normalise_pillow_format(format_name: str | None) -> str:
    """Normalise Pillow format names to a supported set for saving."""

    if not format_name:
        return "PNG"
    upper = format_name.upper()
    if upper in {"PNG", "JPEG", "JPG", "WEBP"}:
        return "JPEG" if upper == "JPG" else upper
    return "PNG"


def mime_from_format(format_name: str | None) -> str:
    """Resolve a MIME type from a Pillow format name."""

    if not format_name:
        return "image/png"
    upper = format_name.upper()
    if upper == "JPG":
        upper = "JPEG"
    return f"image/{upper.lower()}"


def get_reference_dimensions(reference: Tuple[str, bytes, str]) -> Tuple[int, int] | None:
    """Extract width and height from a prepared reference tuple."""

    try:
        with Image.open(BytesIO(reference[1])) as img:
            return img.size
    except Exception:  # pragma: no cover - diagnostics helper
        return None


__all__ = [
    "build_reference_tuple",
    "decode_image_bytes",
    "extension_from_mime",
    "fetch_image_bytes",
    "get_reference_dimensions",
    "mime_from_format",
    "normalise_image_bytes",
    "normalise_pillow_format",
    "parse_render_dimensions",
    "prepare_input_reference",
    "resize_image_bytes",
]
