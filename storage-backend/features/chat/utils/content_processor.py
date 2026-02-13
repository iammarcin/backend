"""Content processing utilities for multimodal chat messages."""

from __future__ import annotations

import base64
import logging
import mimetypes
import tempfile
from typing import Any

import requests
import pypdfium2 as pdfium

logger = logging.getLogger(__name__)


def _extract_url(value: Any) -> str:
    """Return a URL string from supported structures."""

    if isinstance(value, dict):
        return str(value.get("url") or "").strip()
    if isinstance(value, str):
        return value.strip()
    return ""


def process_message_content(
    *,
    content: list[dict[str, Any]],
    provider_name: str,
    model_name: str,
) -> list[dict[str, Any]]:
    """Process multimodal content items into provider-ready format.

    Args:
        content: List of structured content items (text, image_url, file_url, ...).
        provider_name: Provider identifier (e.g. ``openai``, ``anthropic``).
        model_name: Concrete model identifier for capability detection.

    Returns:
        List of content dictionaries ready to be sent to the provider API.
    """
    if not isinstance(content, list):
        return content

    provider_key = (provider_name or "").lower()
    model_key = (model_name or "").lower()

    processed_content: list[dict[str, Any]] = []
    image_items: list[dict[str, Any]] = []
    file_items: list[dict[str, Any]] = []
    passthrough_items: list[dict[str, Any]] = []

    for item in content:
        item_type = item.get("type")
        if item_type == "text":
            processed_content.append(item)
        elif item_type == "image_url":
            image_value = item.get("image_url")
            if isinstance(image_value, str):
                item = {**item, "image_url": {"url": image_value}}
            image_items.append(item)
        elif item_type == "file_url":
            file_value = item.get("file_url")
            if isinstance(file_value, str):
                item = {**item, "file_url": {"url": file_value}}
            file_items.append(item)
        else:
            passthrough_items.append(item)

    if file_items:
        if is_native_pdf_model(provider_key, model_key):
            logger.debug(
                "Model %s (%s) supports native PDF attachments; preserving file_url items",
                model_name,
                provider_name,
            )
            processed_content.extend(file_items)
        else:
            logger.debug(
                "Model %s (%s) requires PDF conversion; converting file attachments",
                model_name,
                provider_name,
            )
            try:
                converted_paths = process_file_attachments(file_items=file_items)
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.error("Failed to process file attachments: %s", exc)
                converted_paths = []

            for path in converted_paths:
                image_items.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": path},
                    }
                )

    if image_items:
        try:
            processed_images = process_image_attachments(
                image_items=image_items,
                provider_name=provider_key,
                model_name=model_key,
            )
            processed_content.extend(processed_images)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Failed to process image attachments: %s", exc)

    if passthrough_items:
        processed_content.extend(passthrough_items)

    return processed_content


def process_file_attachments(*, file_items: list[dict[str, Any]]) -> list[str]:
    """Convert PDF file attachments into temporary image files.

    Args:
        file_items: List of ``file_url`` content entries.

    Returns:
        List of file paths to generated image files.
    """
    image_paths: list[str] = []

    for item in file_items:
        file_value = item.get("file_url")
        url = _extract_url(file_value)
        if not url:
            logger.debug("Skipping file attachment without URL: %r", item)
            continue

        if not url.lower().endswith(".pdf"):
            logger.debug("Skipping non-PDF file attachment: %s", url)
            continue

        try:
            logger.debug("Downloading PDF attachment from %s", url)
            response = requests.get(url, timeout=30)
            response.raise_for_status()
        except Exception as exc:  # pragma: no cover - network failures are runtime concerns
            logger.error("Failed to download PDF %s: %s", url, exc)
            continue

        try:
            pdf = pdfium.PdfDocument(response.content)
        except Exception as exc:  # pragma: no cover - pdf parsing edge cases
            logger.error("Failed to open PDF %s: %s", url, exc)
            continue

        page_count = len(pdf)
        logger.info("Converting PDF %s with %d pages to images", url, page_count)

        for index, page in enumerate(pdf):
            try:
                bitmap = page.render(scale=1, rotation=0)
                pil_image = bitmap.to_pil()
            except Exception as exc:  # pragma: no cover
                logger.error("Failed to render PDF page %d from %s: %s", index, url, exc)
                continue

            with tempfile.NamedTemporaryFile(delete=False, suffix=f"_page{index}.png") as tmp_file:
                pil_image.save(tmp_file, format="PNG")
                image_paths.append(tmp_file.name)
                logger.debug("Generated image for %s page %d: %s", url, index, tmp_file.name)

    return image_paths


def process_image_attachments(
    *,
    image_items: list[dict[str, Any]],
    provider_name: str,
    model_name: str,
) -> list[dict[str, Any]]:
    """Format image attachments for the downstream provider."""

    processed: list[dict[str, Any]] = []
    provider_key = (provider_name or "").lower()

    for item in image_items:
        image_value = item.get("image_url")
        url = _extract_url(image_value)
        if not url:
            logger.debug("Skipping image item without URL: %r", item)
            continue

        if isinstance(image_value, str):
            item = {"type": item.get("type", "image_url"), "image_url": {"url": url}}

        if provider_key == "anthropic":
            try:
                mime_type, base64_data = get_base64_for_image(url)
            except Exception as exc:  # pragma: no cover - runtime I/O issues
                logger.error("Failed to convert image %s to base64: %s", url, exc)
                continue

            processed.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": mime_type,
                        "data": base64_data,
                    },
                }
            )
            logger.debug("Converted image attachment to base64 for Anthropic model %s", model_name)
        else:
            processed.append(item)
            logger.debug(
                "Preserving image URL attachment for provider %s model %s",
                provider_name,
                model_name,
            )

    return processed


def is_native_pdf_model(provider_name: str, model_name: str) -> bool:
    """Return ``True`` when the model supports native PDF/file_url attachments."""

    provider_key = (provider_name or "").lower()
    model_key = (model_name or "").lower()

    if provider_key in {"anthropic", "gemini"}:
        return True

    if model_key.startswith("gpt-5") or model_key.startswith("o3"):
        return True

    return False


def download_file(url: str) -> bytes:
    """Download file content from a URL."""

    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.content


def get_mime_type(url: str) -> str:
    """Return a MIME type guess for the provided URL."""

    mime_type, _ = mimetypes.guess_type(url)
    return mime_type or "application/octet-stream"


def get_base64_for_image(url: str) -> tuple[str, str]:
    """Return the (mime_type, base64_data) pair for an image URL or path."""

    mime_type = get_mime_type(url)

    if url.startswith("http"):
        content = download_file(url)
    else:
        with open(url, "rb") as file_obj:
            content = file_obj.read()

    base64_data = base64.b64encode(content).decode("utf-8")
    return mime_type, base64_data


__all__ = [
    "process_message_content",
    "process_file_attachments",
    "process_image_attachments",
    "is_native_pdf_model",
]
