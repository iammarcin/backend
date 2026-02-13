"""Extraction utilities for OpenAI realtime event payloads.

This module provides utility functions to extract structured data from raw
OpenAI realtime event payloads, including response IDs, item IDs, text deltas,
and audio chunks.
"""

from __future__ import annotations

from typing import Mapping


def extract_response_id(event: Mapping[str, object]) -> str | None:
    """Extract response_id from an event payload."""
    response = event.get("response")
    if isinstance(response, Mapping):
        response_id = response.get("id")
        if isinstance(response_id, str):
            return response_id
    candidate = event.get("response_id") or event.get("responseId")
    if isinstance(candidate, str):
        return candidate
    return None


def extract_item_id(event: Mapping[str, object]) -> str | None:
    """Extract item_id from an event payload."""
    item = event.get("item")
    if isinstance(item, Mapping):
        item_id = item.get("id")
        if isinstance(item_id, str):
            return item_id
    return None


def extract_text_delta(event: Mapping[str, object]) -> str | None:
    """Extract text content from a delta payload."""
    delta = event.get("delta")
    if isinstance(delta, Mapping):
        text = delta.get("text") or delta.get("content") or delta.get("transcript")
        if text is None and "output_text" in delta:
            text = delta.get("output_text")
        if text is None and "content" in delta:
            content = delta["content"]
            if isinstance(content, list) and content:
                candidate = content[0]
                if isinstance(candidate, Mapping):
                    text = candidate.get("text")
        if text is not None:
            return str(text)
    if isinstance(delta, str):
        return delta
    return None


def extract_audio_delta(event: Mapping[str, object]) -> tuple[str | None, str | None]:
    """Extract audio data and format from a delta payload.

    OpenAI Realtime API sends audio deltas as:
    {
        "type": "response.output_audio.delta",
        "delta": "Base64EncodedAudioDelta",  // <-- delta is a string directly
        ...
    }
    """
    delta = event.get("delta")

    # Handle the standard OpenAI format where delta is a base64 string directly
    if isinstance(delta, str):
        return delta, None

    # Fallback: handle nested structure (for compatibility)
    if isinstance(delta, Mapping):
        audio = delta.get("audio")
        if isinstance(audio, Mapping):
            data = audio.get("data") or audio.get("chunk")
            audio_format = audio.get("format")
            if isinstance(data, str):
                return data, str(audio_format) if audio_format else None
        if isinstance(audio, str):
            return audio, None

    return None, None


__all__ = [
    "extract_response_id",
    "extract_item_id",
    "extract_text_delta",
    "extract_audio_delta",
]
