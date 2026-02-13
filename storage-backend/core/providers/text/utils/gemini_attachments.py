"""Attachment helpers for Gemini content generation."""

from __future__ import annotations

import base64
import logging
import mimetypes
import os
from typing import Any

import requests
from google.genai import types  # type: ignore

logger = logging.getLogger(__name__)


def _guess_mime_type(url: str) -> str:
    """Best-effort MIME type detection based on the file extension."""

    url_lower = url.lower()
    if "." in url_lower:
        extension = url_lower.rsplit(".", 1)[-1]
        if extension == "pdf":
            return "application/pdf"
        if extension in {"doc", "docx"}:
            return (
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                if extension == "docx"
                else "application/msword"
            )
        if extension in {"xls", "xlsx"}:
            return (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                if extension == "xlsx"
                else "application/vnd.ms-excel"
            )
        if extension in {"ppt", "pptx"}:
            return (
                "application/vnd.openxmlformats-officedocument.presentationml.presentation"
                if extension == "pptx"
                else "application/vnd.ms-powerpoint"
            )
        if extension == "txt":
            return "text/plain"
        if extension == "rtf":
            return "application/rtf"

    mime_type, _ = mimetypes.guess_type(url)
    return mime_type or "application/octet-stream"


def _decode_data_url(data_url: str) -> tuple[str, bytes] | None:
    """Decode base64 data URLs returned by the chat UI."""

    if "," not in data_url:
        return None
    header, encoded = data_url.split(",", 1)
    if not header.startswith("data:"):
        return None
    mime_type = header.split(";", 1)[0][5:] or "application/octet-stream"
    try:
        return mime_type, base64.b64decode(encoded)
    except Exception:  # pragma: no cover - defensive
        logger.debug("Failed to decode base64 data URL", exc_info=True)
        return None


def _is_gemini_file_uri(url: str) -> bool:
    """Return ``True`` when the URI already points to a Gemini file resource."""

    if not url:
        return False
    return url.startswith("files/") or "generativelanguage.googleapis.com" in url


def _load_binary_payload(url: str) -> bytes | None:
    """Download or read binary content referenced by a URL/path."""

    if not url:
        return None

    if url.startswith("http"):
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
        except Exception:  # pragma: no cover - runtime network concerns
            logger.error("Failed to download Gemini attachment from %s", url, exc_info=True)
            return None
        return response.content

    if os.path.exists(url):
        try:
            with open(url, "rb") as file_obj:
                return file_obj.read()
        except Exception:  # pragma: no cover - runtime file concerns
            logger.error("Failed to read Gemini attachment from %s", url, exc_info=True)
            return None

    logger.debug("Attachment path does not exist: %s", url)
    return None


def _extract_image_part(
    item: dict[str, Any],
    *,
    user_message_index: int,
    attachment_limit: int,
    is_user: bool,
) -> types.Part | None:
    if is_user and user_message_index > attachment_limit:
        logger.debug(
            "Skipping image attachment beyond limit (index=%s, limit=%s)",
            user_message_index,
            attachment_limit,
        )
        return None

    url_payload = item.get("image_url") or item.get("image") or {}
    if isinstance(url_payload, dict):
        url = url_payload.get("url") or url_payload.get("data")
    else:
        url = url_payload

    if not url:
        return None

    if isinstance(url, str) and url.startswith("data:"):
        decoded = _decode_data_url(url)
        if decoded:
            mime_type, data = decoded
            return types.Part.from_bytes(data=data, mime_type=mime_type)
        return None

    if isinstance(url, str):
        if _is_gemini_file_uri(url):
            return types.Part.from_uri(file_uri=url)

        mime_type = _guess_mime_type(url)
        data = _load_binary_payload(url)
        if data:
            return types.Part.from_bytes(data=data, mime_type=mime_type)

    logger.debug("Unsupported image payload: %s", url_payload)
    return None


def _extract_file_part(
    item: dict[str, Any],
    *,
    user_message_index: int,
    attachment_limit: int,
    is_user: bool,
) -> types.Part | None:
    if is_user and user_message_index > attachment_limit:
        logger.debug(
            "Skipping file attachment beyond limit (index=%s, limit=%s)",
            user_message_index,
            attachment_limit,
        )
        return None

    file_payload = item.get("file_url") or {}
    url: str | None
    if isinstance(file_payload, dict):
        url = file_payload.get("url")
    else:
        url = str(file_payload)

    if not url:
        return None

    if isinstance(file_payload, dict):
        mime_type = file_payload.get("mime_type")
    else:
        mime_type = None

    mime_type = mime_type or _guess_mime_type(url)

    if _is_gemini_file_uri(url):
        return types.Part.from_uri(file_uri=url, mime_type=mime_type)

    data = _load_binary_payload(url)
    if not data:
        logger.debug("Skipping file attachment with unreadable payload: %s", url)
        return None

    return types.Part.from_bytes(data=data, mime_type=mime_type)


def _extract_audio_part(item: dict[str, Any]) -> types.Part | None:
    audio_payload = item.get("input_audio") or {}
    if isinstance(audio_payload, dict):
        data = audio_payload.get("data")
        mime_type = audio_payload.get("mime_type") or "audio/wav"
    else:
        data = None
        mime_type = "audio/wav"

    if not data:
        return None

    try:
        audio_bytes = base64.b64decode(data)
    except Exception:  # pragma: no cover - defensive
        logger.debug("Failed to decode audio payload", exc_info=True)
        return None

    return types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)


__all__ = [
    "_decode_data_url",
    "_extract_audio_part",
    "_extract_file_part",
    "_extract_image_part",
    "_guess_mime_type",
    "_is_gemini_file_uri",
    "_load_binary_payload",
]
