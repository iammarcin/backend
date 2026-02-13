"""Message preparation helpers for xAI provider."""

from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence

from xai_sdk import chat

from typing import TYPE_CHECKING

from .xai_format import XaiMessageFormattingResult

if TYPE_CHECKING:  # pragma: no cover - import for type checking only
    from . import xai as xai_pkg


async def prepare_messages(
    *,
    client: Any,
    prompt: str,
    system_prompt: Optional[str],
    messages: Optional[Sequence[Mapping[str, Any]]],
) -> XaiMessageFormattingResult:
    """Build and format the message list for the SDK."""

    base_messages: list[Mapping[str, Any]] = []
    if messages:
        base_messages.extend(messages)
    else:
        if system_prompt:
            base_messages.append({"role": "system", "content": system_prompt})
        base_messages.append({"role": "user", "content": prompt})

    from . import xai as xai_pkg

    formatted = await xai_pkg.format_messages_for_xai(base_messages, client=client)
    if formatted.messages:
        return formatted

    fallback_messages = []
    if system_prompt:
        fallback_messages.append(chat.system(system_prompt))
    fallback_messages.append(chat.user(prompt))
    return XaiMessageFormattingResult(messages=fallback_messages)


__all__ = ["prepare_messages"]
