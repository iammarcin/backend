"""Utilities for formatting BetterAI messages into xAI SDK payloads."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Sequence

from xai_sdk import AsyncClient as XaiAsyncClient
from xai_sdk import chat

from .xai_format_helpers import (
    DownloadFn,
    build_tool_result,
    convert_content_item,
    download_file,
    normalise_text,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class XaiMessageFormattingResult:
    """Container for formatted xAI messages and associated resources."""

    messages: list[Any]
    uploaded_file_ids: list[str] = field(default_factory=list)
    temporary_files: list[Path] = field(default_factory=list)


async def format_messages_for_xai(
    messages: Sequence[dict[str, Any]] | None,
    *,
    client: XaiAsyncClient,
    download_fn: Optional[DownloadFn] = None,
) -> XaiMessageFormattingResult:
    """Convert BetterAI message dictionaries into xAI SDK chat messages."""

    if not messages:
        return XaiMessageFormattingResult(messages=[])

    role_builders: dict[str, Any] = {
        "system": chat.system,
        "user": chat.user,
        "assistant": chat.assistant,
        "tool": chat.tool_result,
    }

    converter = download_fn or download_file
    formatted_messages: list[Any] = []
    temporary_files: list[Path] = []
    uploaded_file_ids: list[str] = []
    upload_cache: dict[str, str] = {}

    for message in messages:
        if not isinstance(message, dict):
            logger.debug("Skipping non-dict message entry: %r", message)
            continue

        role = str(message.get("role") or "user").lower()

        if role == "tool":
            formatted_messages.append(build_tool_result(message.get("content")))
            continue

        builder = role_builders.get(role, chat.user)
        content = message.get("content")

        if isinstance(content, list):
            parts: list[Any] = []
            for item in content:
                converted = await convert_content_item(
                    item,
                    client=client,
                    upload_cache=upload_cache,
                    uploaded_file_ids=uploaded_file_ids,
                    temporary_files=temporary_files,
                    download_fn=converter,
                )
                if converted is not None:
                    parts.append(converted)

            if not parts:
                parts.append(chat.text(""))

            formatted_messages.append(builder(*parts))
            continue

        formatted_messages.append(builder(chat.text(normalise_text(content))))

    return XaiMessageFormattingResult(
        messages=formatted_messages,
        uploaded_file_ids=uploaded_file_ids,
        temporary_files=temporary_files,
    )


__all__ = ["XaiMessageFormattingResult", "format_messages_for_xai"]
