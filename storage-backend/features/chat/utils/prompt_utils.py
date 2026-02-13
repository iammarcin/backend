"""Utilities for parsing chat prompts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

PromptInput = Union[str, List[Any]]


def prompt_preview(prompt: PromptInput) -> str:
    """Return a compact preview of a prompt for logging."""

    if isinstance(prompt, str):
        text = prompt
    else:
        text = " ".join(str(item) for item in prompt) if prompt else ""
    text = (text or "").strip().replace("\n", " ")
    return text[:1000] + ("…" if len(text) > 1000 else "")


@dataclass
class PromptContext:
    """Parsed information extracted from an incoming prompt payload."""

    text_prompt: str
    image_mode: Optional[str]
    input_image_url: Optional[str]


def parse_prompt(prompt: PromptInput) -> PromptContext:
    """Normalize prompt payload into text and optional image metadata."""

    if isinstance(prompt, str):
        text_prompt = prompt.strip()
        return PromptContext(text_prompt=text_prompt, image_mode=None, input_image_url=None)

    text_segments: List[str] = []
    image_mode: Optional[str] = None
    input_image_url: Optional[str] = None

    for item in prompt:
        item_data: Dict[str, Any]
        if hasattr(item, "model_dump"):
            item_data = item.model_dump()
        elif isinstance(item, dict):
            item_data = item
        else:
            continue

        item_type = str(item_data.get("type", "")).lower()
        if item_type == "text":
            text_value = str(item_data.get("text", "")).strip()
            if text_value:
                text_segments.append(text_value)
        elif item_type == "image_mode":
            image_mode = str(item_data.get("image_mode") or "") or None
        elif item_type == "image_url":
            image_value = item_data.get("image_url")
            if isinstance(image_value, dict):
                input_image_url = str(image_value.get("url") or "") or None
            else:
                input_image_url = str(image_value or "") or None
        elif item_type == "file_url":
            file_value = item_data.get("file_url")
            if isinstance(file_value, dict):
                input_image_url = input_image_url or str(file_value.get("url") or "") or None
            else:
                input_image_url = input_image_url or str(file_value or "") or None

    text_prompt = " ".join(segment for segment in text_segments if segment).strip()
    return PromptContext(
        text_prompt=text_prompt,
        image_mode=image_mode,
        input_image_url=input_image_url,
    )


__all__ = ["PromptContext", "PromptInput", "parse_prompt", "prompt_preview"]
