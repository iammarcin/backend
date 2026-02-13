"""Utility helpers for the Flux image provider."""

from __future__ import annotations

import base64
import binascii
from typing import Any, Optional

import httpx

from core.exceptions import ProviderError

_BASE64_CHARS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=")


def find_first_base64(payload: Any) -> Optional[bytes]:
    """Recursively search for the first plausible base64 payload."""

    stack: list[Any] = [payload]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            for key, value in current.items():
                if isinstance(value, str):
                    lowered = key.lower()
                    if lowered in {
                        "image",
                        "image_base64",
                        "image_b64",
                        "b64_json",
                        "base64",
                        "base64_image",
                        "sample",
                        "sample_base64",
                    }:
                        decoded = maybe_decode_base64(value, require_length=False)
                        if decoded:
                            return decoded
                    decoded = maybe_decode_base64(value)
                    if decoded:
                        return decoded
                elif isinstance(value, (dict, list)):
                    stack.append(value)
        elif isinstance(current, list):
            stack.extend(current)
        elif isinstance(current, str):
            decoded = maybe_decode_base64(current)
            if decoded:
                return decoded
    return None


def find_first_url(payload: Any) -> Optional[str]:
    """Recursively search for an image URL returned by the Flux API."""

    stack: list[Any] = [payload]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            for value in current.values():
                if isinstance(value, str) and value.startswith("http"):
                    return value
                if isinstance(value, (dict, list)):
                    stack.append(value)
        elif isinstance(current, list):
            stack.extend(current)
        elif isinstance(current, str) and current.startswith("http"):
            return current
    return None


def maybe_decode_base64(candidate: str, *, require_length: bool = True) -> Optional[bytes]:
    """Attempt to decode the provided string as base64 if it looks plausible."""

    if not candidate:
        return None

    stripped = candidate.strip()
    if not stripped:
        return None

    if stripped.startswith("data:"):
        _, _, stripped = stripped.partition(",")
        stripped = stripped.strip()
        if not stripped:
            return None

    normalized = "".join(stripped.split())
    if require_length and len(normalized) < 64:
        return None

    if any(ch not in _BASE64_CHARS for ch in normalized):
        return None

    padding = (-len(normalized)) % 4
    normalized += "=" * padding

    try:
        decoded = base64.b64decode(normalized, validate=True)
    except binascii.Error:
        return None

    return decoded or None


async def download_image(url: str, api_key: str) -> bytes:
    """Download image bytes from the supplied URL using the Flux credentials."""

    headers = {"x-key": api_key, "accept": "image/*"}
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url, headers=headers)

    if response.status_code >= 400:
        raise ProviderError("Flux image download failed", provider="flux_image")

    return response.content


__all__ = [
    "download_image",
    "find_first_base64",
    "find_first_url",
    "maybe_decode_base64",
]
