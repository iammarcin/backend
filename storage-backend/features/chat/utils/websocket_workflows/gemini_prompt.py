"""Prompt parsing utilities for Gemini workflows."""

from __future__ import annotations

from typing import Any


def _extract_text_from_prompt(prompt: Any) -> str:
    """Extract a human-readable text prompt from structured payloads."""

    if not prompt:
        return ""

    if isinstance(prompt, str):
        return prompt

    if isinstance(prompt, list):
        for item in prompt:
            if isinstance(item, dict) and item.get("type") == "text":
                return str(item.get("text", ""))

    return ""


__all__ = ["_extract_text_from_prompt"]

