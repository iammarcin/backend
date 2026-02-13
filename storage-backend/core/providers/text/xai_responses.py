"""Helper utilities for processing xAI responses and events."""

from __future__ import annotations

import json
import logging
from typing import Any, Sequence

import grpc
from google.protobuf.json_format import MessageToDict
from xai_sdk.proto import chat_pb2

from core.exceptions import ProviderError

logger = logging.getLogger(__name__)


SERVER_SIDE_TOOL_TYPES = {
    chat_pb2.ToolCallType.TOOL_CALL_TYPE_WEB_SEARCH_TOOL,
    chat_pb2.ToolCallType.TOOL_CALL_TYPE_X_SEARCH_TOOL,
}

SERVER_SIDE_TOOL_NAMES = {"web_search", "x_search"}


def normalise_tool_calls(tool_calls: Sequence[Any]) -> list[dict[str, Any]]:
    """Convert SDK tool call protos into serialisable dictionaries."""

    serialised: list[dict[str, Any]] = []
    for item in tool_calls or []:
        if item is None:  # pragma: no cover - defensive guard
            continue
        call_id = getattr(item, "id", None)
        function = getattr(item, "function", None)
        name = getattr(function, "name", None) if function else None
        arguments_raw = getattr(function, "arguments", None) if function else None
        parsed_arguments: Any
        if isinstance(arguments_raw, str) and arguments_raw.strip():
            try:
                parsed_arguments = json.loads(arguments_raw)
            except json.JSONDecodeError:
                parsed_arguments = arguments_raw
        else:
            parsed_arguments = arguments_raw

        payload: dict[str, Any] = {
            "id": call_id or "",
            "type": "function",
            "function": {
                "name": name or "",
                "arguments": parsed_arguments,
            },
        }

        try:
            call_type_value = getattr(item, "type", None)
            if isinstance(call_type_value, int) and call_type_value in chat_pb2.ToolCallType.values():
                payload["call_type"] = chat_pb2.ToolCallType.Name(call_type_value)
        except Exception:  # pragma: no cover - defensive
            pass

        serialised.append(payload)
    return serialised


def format_usage(response: Any) -> dict[str, Any] | None:
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    try:
        return MessageToDict(usage)
    except Exception:  # pragma: no cover - defensive
        return None


def handle_grpc_exception(exc: BaseException) -> ProviderError:
    if isinstance(exc, grpc.RpcError):
        code = exc.code()
        details = exc.details() if callable(getattr(exc, "details", None)) else None
        if code == grpc.StatusCode.DEADLINE_EXCEEDED:
            message = "xAI request timed out"
        elif code in {grpc.StatusCode.UNAUTHENTICATED, grpc.StatusCode.PERMISSION_DENIED}:
            message = "xAI authentication failed"
        else:
            message = f"xAI gRPC error ({code.name})"
        if details:
            message = f"{message}: {details}"
        return ProviderError(message, provider="xai")
    return ProviderError(f"xAI request failed: {exc}", provider="xai")


def safe_json_loads(value: str | None) -> Any:
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _truncate(text: str, limit: int = 200) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:limit]}…"


def _sanitize_for_log(text: str) -> str:
    return text.replace("\n", "\\n").replace("\r", "")


def serialize_for_log(value: Any) -> str:
    if value is None:
        return "<none>"
    if isinstance(value, str):
        return _truncate(_sanitize_for_log(value))
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        preview = ", ".join(map(str, value))
        return f"[{_truncate(preview)}]"
    return _truncate(str(value))


def log_server_side_tool_usage(
    *,
    tool_calls: Sequence[Any] | None,
    citations: Sequence[str] | None,
    context: str,
) -> None:
    if not tool_calls and not citations:
        return

    citation_entries = [c for c in (citations or []) if isinstance(c, str) and c.strip()]
    citation_text = serialize_for_log(citation_entries) if citation_entries else None

    for call in tool_calls or []:
        call_type_value = getattr(call, "type", None)
        if not isinstance(call_type_value, int):
            continue
        if call_type_value not in SERVER_SIDE_TOOL_TYPES:
            continue

        try:
            call_type = chat_pb2.ToolCallType.Name(call_type_value)
        except ValueError:  # pragma: no cover - defensive guard
            call_type = f"UNKNOWN({call_type_value})"

        function_payload = getattr(call, "function", None)
        name = getattr(function_payload, "name", None)
        arguments_raw = getattr(function_payload, "arguments", None)
        parsed_arguments = safe_json_loads(arguments_raw if isinstance(arguments_raw, str) else None)

        log_message = (
            "xAI server tool usage (%s): type=%s name=%s arguments=%s"
            % (
                context,
                call_type,
                name or "<unspecified>",
                serialize_for_log(parsed_arguments),
            )
        )

        if citation_text:
            log_message = f"{log_message} citations={citation_text}"

        logger.info(log_message)


def is_server_side_tool_call(call: Any) -> bool:
    """Return True when the SDK tool call represents an auto-handled server tool."""

    call_type_value = getattr(call, "type", None)
    if isinstance(call_type_value, int) and call_type_value in SERVER_SIDE_TOOL_TYPES:
        return True

    function_payload = getattr(call, "function", None)
    function_name = getattr(function_payload, "name", None)
    if isinstance(function_name, str) and function_name in SERVER_SIDE_TOOL_NAMES:
        return True

    return False


def tool_calls_require_client_action(tool_calls: Sequence[Any] | None) -> bool:
    """Determine whether the emitted tool calls require the client to act."""

    relevant_calls = [call for call in tool_calls or [] if call is not None]
    if not relevant_calls:
        return False

    return any(not is_server_side_tool_call(call) for call in relevant_calls)


__all__ = [
    "SERVER_SIDE_TOOL_NAMES",
    "SERVER_SIDE_TOOL_TYPES",
    "format_usage",
    "handle_grpc_exception",
    "is_server_side_tool_call",
    "log_server_side_tool_usage",
    "normalise_tool_calls",
    "safe_json_loads",
    "serialize_for_log",
    "tool_calls_require_client_action",
]
