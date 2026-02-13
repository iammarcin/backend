"""Prompt parsing helpers for semantic enhancement."""

from __future__ import annotations

from .prompt_enhancement_result import PromptInput


def extract_prompt_text(prompt: PromptInput) -> tuple[str, str | None]:
    """Return normalized prompt text and optional error message."""

    if isinstance(prompt, str):
        return prompt, None

    if isinstance(prompt, list):
        text_parts = [
            part.get("text", "")
            for part in prompt
            if isinstance(part, dict) and part.get("type") == "text"
        ]
        return " ".join(text_parts).strip(), None

    return "", "Invalid prompt format"


__all__ = ["extract_prompt_text"]
