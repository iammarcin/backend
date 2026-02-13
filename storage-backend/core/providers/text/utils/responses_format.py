"""Utilities for converting between Chat Completions and Responses API formats."""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _convert_user_content_item(item: dict[str, Any]) -> dict[str, Any]:
    """Convert a single user content item to Responses API format."""

    item_type = item.get("type")
    if item_type == "text":
        return {"type": "input_text", "text": item.get("text", "")}

    if item_type == "image_url":
        image_url_obj = item.get("image_url", {})
        if isinstance(image_url_obj, dict) and "url" in image_url_obj:
            return {"type": "input_image", "image_url": image_url_obj["url"]}
        return {"type": "input_image", "image_url": str(image_url_obj)}

    if item_type == "file_url":
        file_url_obj = item.get("file_url", {})
        if isinstance(file_url_obj, dict) and "url" in file_url_obj:
            return {"type": "input_file", "file_url": file_url_obj["url"]}
        return {"type": "input_file", "file_url": str(file_url_obj)}

    if item_type == "image":
        # Anthropic compatibility
        return {"type": "input_image", "source": item.get("source", {})}

    logger.debug("Unhandled user content type: %s", item_type)
    return item


def _convert_assistant_content_item(item: dict[str, Any]) -> dict[str, Any]:
    """Convert a single assistant content item to Responses API format."""

    if item.get("type") == "text":
        return {"type": "output_text", "text": item.get("text", "")}
    return item


def _stringify_json_value(value: Any, *, default: str = "{}") -> str:
    """Convert arbitrary values to JSON strings for API payloads."""

    if isinstance(value, str):
        return value
    if value is None:
        return default
    try:
        return json.dumps(value)
    except Exception:  # pragma: no cover - defensive
        return str(value)


def convert_to_responses_format(
    chat_history: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], str | None]:
    """Convert Chat Completions messages to Responses API format.

    Returns the converted messages and any system instruction extracted from the
    chat history. The Responses API expects system prompts to be sent via the
    ``instructions`` field instead of within the message list.
    """

    system_instruction: str | None = None
    messages_to_convert = chat_history

    if chat_history and chat_history[0].get("role") == "system":
        system_content = chat_history[0].get("content")
        if isinstance(system_content, list):
            extracted_parts: list[str] = []
            for item in system_content:
                if isinstance(item, dict):
                    text_value = item.get("text")
                    if text_value:
                        extracted_parts.append(str(text_value))
                else:
                    extracted_parts.append(str(item))
            system_instruction = " ".join(part for part in extracted_parts if part)
        elif system_content is not None:
            system_instruction = str(system_content)

        messages_to_convert = chat_history[1:]

    converted: list[dict[str, Any]] = []
    for message in messages_to_convert:
        role = message.get("role")
        content = message.get("content")

        new_items: list[dict[str, Any]] = []

        if role == "system":
            logger.debug(
                "Encountered system message outside leading position; passing through"
            )
            new_items.append({"role": role, "content": content})

        elif role == "user":
            if isinstance(content, list):
                new_content = [_convert_user_content_item(item) for item in content]
            else:
                new_content = [{"type": "input_text", "text": str(content)}]
            new_items.append({"role": role, "content": new_content})

        elif role == "assistant":
            new_content: list[dict[str, Any]] | None = None
            if content is not None:
                if isinstance(content, list):
                    new_content = [_convert_assistant_content_item(item) for item in content]
                else:
                    new_content = [{"type": "output_text", "text": str(content)}]

            if new_content:
                new_items.append({"role": role, "content": new_content})

            tool_calls = message.get("tool_calls") or []
            for tool_call in tool_calls:
                function_data = tool_call.get("function", {}) if isinstance(tool_call, dict) else {}

                # For Responses API, always use call_id (call_xxx), NOT item_id
                call_id = tool_call.get("id") if isinstance(tool_call, dict) else None
                call_id = call_id or (tool_call.get("call_id") if isinstance(tool_call, dict) else None)

                logger.debug(
                    "Converting tool_call to Responses API: call_id=%s name=%s",
                    call_id,
                    function_data.get("name") if isinstance(function_data, dict) else None,
                )

                arguments = function_data.get("arguments") if isinstance(function_data, dict) else None
                new_items.append(
                    {
                        "type": "function_call",
                        "call_id": call_id,
                        "name": function_data.get("name") if isinstance(function_data, dict) else None,
                        "arguments": _stringify_json_value(arguments),
                    }
                )

        elif role == "tool":
            tool_call_id = message.get("tool_call_id") or message.get("call_id")
            logger.debug(
                "Converting tool output to Responses API: tool_call_id=%s",
                tool_call_id,
            )
            new_items.append(
                {
                    "type": "function_call_output",
                    "call_id": tool_call_id,
                    "output": _stringify_json_value(message.get("content")),
                }
            )

        else:
            logger.warning("Unknown role in chat history: %s", role)
            new_items.append(message)

        converted.extend(new_items)

    return converted, system_instruction


def is_responses_api_model(model_name: str) -> bool:
    """Return True if the supplied model requires the Responses API."""

    model_name_lower = model_name.lower()
    return model_name_lower.startswith("gpt-5") or model_name_lower.startswith("o3")


__all__ = ["convert_to_responses_format", "is_responses_api_model"]
