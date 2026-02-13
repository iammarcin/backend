"""Utilities for logging OpenAI Responses API tool usage."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping, Sequence
from typing import Any

logger = logging.getLogger(__name__)


def _to_plain_data(value: Any) -> Any:
    """Convert OpenAI SDK objects into plain Python data structures."""

    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, Mapping) or hasattr(value, "items"):
        try:
            items = value.items()  # type: ignore[attr-defined]
        except Exception:  # pragma: no cover - defensive
            items = None
        if items is not None:
            return {key: _to_plain_data(val) for key, val in items}

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_to_plain_data(item) for item in value]

    for attr in ("model_dump", "dict"):
        method = getattr(value, attr, None)
        if callable(method):
            try:
                return _to_plain_data(method())
            except Exception:  # pragma: no cover - defensive
                continue

    return value


def _extract_plain_tool_items(data: Any) -> list[dict[str, Any]]:
    """Extract tool call payloads from a responses API payload."""

    items: list[dict[str, Any]] = []

    def _walk(node: Any) -> None:
        if isinstance(node, Mapping):
            node_type = node.get("type")
            name = node.get("name") if isinstance(node.get("name"), str) else None
            has_input = any(
                key in node
                for key in (
                    "input",
                    "arguments",
                    "args",
                    "payload",
                    "code",
                    "query",
                    "messages",
                )
            )

            # Special handling for web_search_call - it doesn't have typical input fields
            # but has type="web_search_call" and should be detected
            if node_type == "web_search_call":
                items.append(node)  # type: ignore[arg-type]
            elif has_input and (
                node_type in {
                    "tool_call",
                    "tool_use",
                    "function_call",
                    "custom_tool_call",
                    "web_search",
                    "code_interpreter",
                }
                or (name and name in {"web_search", "code_interpreter"})
            ):
                items.append(node)  # type: ignore[arg-type]

            for value in node.values():
                _walk(value)
        elif isinstance(node, list):
            for value in node:
                _walk(value)

    _walk(_to_plain_data(data))
    return items


def _serialize_for_seen(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return json.dumps(value, sort_keys=True, ensure_ascii=False)
    except TypeError:  # pragma: no cover - best effort
        return str(value)


def _stringify(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False)
    except TypeError:  # pragma: no cover - best effort
        return str(value)


def _truncate_text(text: str, limit: int = 200) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:limit]}…"


def _sanitize_log_text(text: str) -> str:
    return text.replace("\n", "\\n").replace("\r", "")


def _extract_web_search_query(data: Any) -> str | None:
    if isinstance(data, Mapping):
        for key in ("query", "search", "q"):
            if key in data:
                value = data[key]
                if isinstance(value, str) and value.strip():
                    return value
                nested = _extract_web_search_query(value)
                if nested:
                    return nested
        for value in data.values():
            nested = _extract_web_search_query(value)
            if nested:
                return nested
    elif isinstance(data, list):
        for value in data:
            nested = _extract_web_search_query(value)
            if nested:
                return nested
    elif isinstance(data, str) and data.strip():
        return data
    return None


def _extract_code_interpreter_code(data: Any) -> str | None:
    if isinstance(data, Mapping):
        for key in ("code", "input", "instructions"):
            if key in data:
                value = data[key]
                if isinstance(value, str) and value.strip():
                    return value
                nested = _extract_code_interpreter_code(value)
                if nested:
                    return nested
        if "messages" in data:
            nested = _extract_code_interpreter_code(data["messages"])
            if nested:
                return nested
        for value in data.values():
            nested = _extract_code_interpreter_code(value)
            if nested:
                return nested
    elif isinstance(data, list):
        for value in data:
            nested = _extract_code_interpreter_code(value)
            if nested:
                return nested
    elif isinstance(data, str) and data.strip():
        return data
    return None


def _log_single_tool_usage(
    *,
    tool_name: str | None,
    call_id: str | None,
    tool_input: Any,
    source: str,
    logger: logging.Logger,
) -> None:
    name = tool_name or "unknown"
    input_payload = _to_plain_data(tool_input)

    snippet_label = "input"
    snippet: str | None = None

    if name == "web_search":
        snippet = _extract_web_search_query(input_payload)
        snippet_label = "query"
    elif name == "code_interpreter":
        snippet = _extract_code_interpreter_code(input_payload)
        snippet_label = "code"

    if snippet is None and input_payload is not None:
        snippet = _stringify(input_payload)

    if snippet is None:
        snippet = "[unknown]"

    sanitized_snippet = _sanitize_log_text(_truncate_text(str(snippet)))
    call_id_part = f" call_id={call_id}" if call_id else ""

    logger.info(
        "Responses API tool usage (%s): %s%s %s=%s",
        source,
        name,
        call_id_part,
        snippet_label,
        sanitized_snippet,
    )


def log_responses_tool_calls(
    output: Any,
    *,
    source: str,
    logger: logging.Logger | None = None,
    seen: set[tuple[str | None, str | None, str | None]] | None = None,
) -> None:
    """Log any tool usage embedded within a Responses API payload."""

    if output is None:
        return

    active_logger = logger or logging.getLogger("core.providers.text.openai_responses")

    for item in _extract_plain_tool_items(output):
        name = item.get("name") or item.get("tool") or item.get("type")
        call_id = item.get("call_id") or item.get("id")

        # Normalize web_search_call to web_search
        if name == "web_search_call":
            name = "web_search"

        # Extract tool input - for web_search_call, use the action field
        tool_input = None
        if item.get("type") == "web_search_call":
            # Extract action which contains query, domains, etc.
            # Only process when status is completed to get full action details
            status = item.get("status")
            if status == "completed":
                action = item.get("action")
                if action:
                    tool_input = action
                else:
                    tool_input = {}
            else:
                # Skip in_progress events
                continue
        else:
            # For other tools, look for standard input fields
            for key in ("input", "arguments", "args", "payload", "web_search", "code_interpreter"):
                if key in item:
                    tool_input = item[key]
                    break
            if tool_input is None:
                tool_input = {}

        # Deduplicate based on call_id only for web_search
        if name == "web_search":
            dedupe_key = (str(name), str(call_id) if call_id else None, None)
        else:
            serialized_input = _serialize_for_seen(_to_plain_data(tool_input))
            dedupe_key = (
                str(name) if name is not None else None,
                str(call_id) if call_id is not None else None,
                serialized_input,
            )

        if seen is not None:
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)

        _log_single_tool_usage(
            tool_name=str(name) if name is not None else None,
            call_id=str(call_id) if call_id is not None else None,
            tool_input=tool_input,
            source=source,
            logger=active_logger,
        )


__all__ = ["log_responses_tool_calls"]
