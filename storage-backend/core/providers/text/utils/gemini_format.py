"""Helpers for translating chat history into Gemini SDK payloads."""

from __future__ import annotations

import logging
from typing import Any, Iterable, Sequence

from google.genai import types  # type: ignore

from .gemini_attachments import (
    _extract_audio_part,
    _extract_file_part,
    _extract_image_part,
)

logger = logging.getLogger(__name__)


def _normalise_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _convert_content_item(
    item: Any,
    *,
    user_message_index: int,
    attachment_limit: int,
    is_user: bool,
) -> types.Part | None:
    if isinstance(item, types.Part):
        return item

    if not isinstance(item, dict):
        text = _normalise_text(item)
        return types.Part.from_text(text=text) if text else None

    item_type = str(item.get("type") or "").lower()
    if item_type == "text":
        text = _normalise_text(item.get("text"))
        return types.Part.from_text(text=text) if text else None
    if item_type in {"image_url", "image"}:
        return _extract_image_part(
            item,
            user_message_index=user_message_index,
            attachment_limit=attachment_limit,
            is_user=is_user,
        )
    if item_type == "file_url":
        return _extract_file_part(
            item,
            user_message_index=user_message_index,
            attachment_limit=attachment_limit,
            is_user=is_user,
        )
    if item_type == "input_audio":
        return _extract_audio_part(item)

    logger.debug("Unsupported Gemini content item type: %s", item_type)
    return None


def _convert_message_to_content(
    message: dict[str, Any],
    *,
    user_message_index: int,
    attachment_limit: int,
) -> tuple[types.Content | None, int]:
    role = str(message.get("role") or "").lower()
    if role == "system" or not role:
        return None, user_message_index

    # Handle tool result messages (role="tool") - convert to Gemini function_response
    if role == "tool":
        tool_call_id = message.get("tool_call_id")
        content = message.get("content", "")

        # Parse the tool result (it's JSON string)
        import json
        try:
            result_data = json.loads(content) if isinstance(content, str) else content
        except (json.JSONDecodeError, TypeError):
            result_data = {"result": content}

        # Create Gemini function response part
        # Note: Gemini expects function responses in "user" role
        function_response_part = types.Part.from_function_response(
            name=result_data.get("tool", "unknown_tool"),
            response=result_data
        )

        return types.Content(role="user", parts=[function_response_part]), user_message_index

    # Handle assistant messages with tool_calls - convert to Gemini function_call
    tool_calls = message.get("tool_calls")
    if role == "assistant" and tool_calls:
        parts: list[types.Part] = []

        # Convert each tool call to a function_call part
        for tool_call in tool_calls:
            func = tool_call.get("function", {})
            func_name = func.get("name")
            func_args_str = func.get("arguments", "{}")

            # Parse arguments
            import json
            try:
                func_args = json.loads(func_args_str) if isinstance(func_args_str, str) else func_args_str
            except (json.JSONDecodeError, TypeError):
                func_args = {}

            # Create Gemini function call part
            function_call_part = types.FunctionCall(
                name=func_name,
                args=func_args
            )
            parts.append(types.Part(function_call=function_call_part))

        # Also include text content if present
        content_items = message.get("content")
        if content_items and content_items is not None:
            if isinstance(content_items, str):
                parts.insert(0, types.Part.from_text(text=content_items))

        if not parts:
            logger.debug("Skipping assistant message with tool_calls but no convertible parts: %s", message)
            return None, user_message_index

        return types.Content(role="model", parts=parts), user_message_index

    # Handle regular user/assistant messages
    is_user = role == "user"
    if is_user:
        user_message_index += 1

    content_items = message.get("content")
    parts: list[types.Part] = []

    if isinstance(content_items, Iterable) and not isinstance(content_items, (str, bytes, dict)):
        for item in content_items:
            part = _convert_content_item(
                item,
                user_message_index=user_message_index,
                attachment_limit=attachment_limit,
                is_user=is_user,
            )
            if part:
                parts.append(part)
    elif isinstance(content_items, dict):
        part = _convert_content_item(
            content_items,
            user_message_index=user_message_index,
            attachment_limit=attachment_limit,
            is_user=is_user,
        )
        if part:
            parts.append(part)
    else:
        text = _normalise_text(content_items)
        if text:
            parts.append(types.Part.from_text(text=text))

    if not parts:
        logger.debug("Skipping message with no convertible parts: %s", message)
        return None, user_message_index

    gemini_role = "user" if is_user else "model"
    return types.Content(role=gemini_role, parts=parts), user_message_index


def prepare_gemini_contents(
    *,
    prompt: str | None,
    messages: Sequence[dict[str, Any]] | None,
    audio_parts: Sequence[types.Part] | None = None,
    attachment_limit: int = 2,
) -> list[types.Content]:
    """Convert chat history and optional prompt into Gemini SDK payloads."""

    contents: list[types.Content] = []
    user_index = 0

    if messages:
        for message in messages:
            if not isinstance(message, dict):
                logger.debug("Ignoring non-dict chat message: %r", message)
                continue
            converted, user_index = _convert_message_to_content(
                message,
                user_message_index=user_index,
                attachment_limit=attachment_limit,
            )
            if converted:
                contents.append(converted)

    if not contents:
        text = _normalise_text(prompt)
        if text:
            contents.append(
                types.Content(role="user", parts=[types.Part.from_text(text=text)])
            )

    audio_sequence = list(audio_parts or [])
    if audio_sequence:
        if contents and (contents[-1].role or "").lower() == "user":
            existing_parts = list(contents[-1].parts or [])
            existing_parts.extend(audio_sequence)
            contents[-1] = types.Content(role="user", parts=existing_parts)
        else:
            contents.append(types.Content(role="user", parts=audio_sequence))

    return contents


__all__ = ["prepare_gemini_contents"]
