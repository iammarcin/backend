"""Shared emitters for Gemini streaming tool events."""

from __future__ import annotations

import json
import logging
from typing import Any, List, Set

from core.streaming.manager import StreamingManager
from features.chat.services.streaming.events import emit_tool_use_event

from .grounding_emitters import emit_grounding_events

logger = logging.getLogger(__name__)


async def process_candidate(
    *,
    candidate: Any,
    manager: StreamingManager,
    seen: Set[str],
) -> List[dict[str, Any]]:
    """Convert a streaming candidate payload into custom events."""

    payloads: List[dict[str, Any]] = []
    content = getattr(candidate, "content", None) or getattr(candidate, "contents", None)
    if content:
        payloads.extend(
            await emit_content_events(content=content, manager=manager, seen=seen)
        )

    grounding = getattr(candidate, "grounding_metadata", None)
    if grounding:
        payloads.extend(
            await emit_grounding_events(grounding=grounding, manager=manager, seen=seen)
        )

    return payloads


async def emit_content_events(
    *,
    content: Any,
    manager: StreamingManager,
    seen: Set[str],
) -> List[dict[str, Any]]:
    payloads: List[dict[str, Any]] = []
    parts = getattr(content, "parts", None)
    if not parts:
        return payloads

    for part in parts:
        function_call = getattr(part, "function_call", None) or (
            part.get("function_call") if isinstance(part, dict) else None
        )
        if function_call:
            payloads.extend(
                await emit_function_call(
                    function_call=function_call,
                    manager=manager,
                    seen=seen,
                )
            )

        executable_code = getattr(part, "executable_code", None) or (
            part.get("executable_code") if isinstance(part, dict) else None
        )
        if executable_code:
            payloads.extend(
                await emit_code_execution(
                    executable_code=executable_code,
                    manager=manager,
                    seen=seen,
                )
            )

    return payloads


async def emit_function_call(
    *,
    function_call: Any,
    manager: StreamingManager,
    seen: Set[str],
) -> List[dict[str, Any]]:
    name = getattr(function_call, "name", None)
    if name is None and isinstance(function_call, dict):
        name = function_call.get("name")

    raw_args = getattr(function_call, "args", None)
    if raw_args is None and isinstance(function_call, dict):
        raw_args = function_call.get("args") or function_call.get("arguments")

    args_dict: dict[str, Any] = {}
    if raw_args is not None:
        if isinstance(raw_args, dict):
            args_dict = raw_args
        elif hasattr(raw_args, "items"):
            args_dict = {str(k): v for k, v in raw_args.items()}
        elif isinstance(raw_args, str):
            try:
                parsed = json.loads(raw_args)
                if isinstance(parsed, dict):
                    args_dict = parsed
            except ValueError:
                args_dict = {"raw": raw_args}

    dedupe_key = f"function:{name}:{json.dumps(args_dict, sort_keys=True, ensure_ascii=False)}"
    if dedupe_key in seen:
        return []
    seen.add(dedupe_key)

    logger.info("Gemini function call detected: %s", name or "unknown")

    await emit_tool_use_event(
        manager=manager,
        provider="gemini",
        tool_name=name or "function_call",
        tool_input=args_dict,
    )

    payload = {
        "name": name or "function_call",
        "toolName": name or "function_call",
        "input": args_dict,
        "toolInput": args_dict,
        "id": None,
        "callId": None,
        "provider": "gemini",
        "requires_action": False,
    }
    logger.debug(
        "Gemini function_call payload created: name=%s requires_action=%s",
        name or "function_call",
        payload["requires_action"],
    )

    return [payload]


async def emit_code_execution(
    *,
    executable_code: Any,
    manager: StreamingManager,
    seen: Set[str],
) -> List[dict[str, Any]]:
    code = getattr(executable_code, "code", None)
    if code is None and isinstance(executable_code, dict):
        code = executable_code.get("code")

    language = getattr(executable_code, "language", None)
    if language is None and isinstance(executable_code, dict):
        language = executable_code.get("language")

    snippet = (code or "")[:100]
    dedupe_key = f"code:{language}:{snippet}"
    if dedupe_key in seen:
        return []
    seen.add(dedupe_key)

    logger.info(
        "Gemini code execution detected: language=%s code_length=%d",
        language or "unknown",
        len(code) if isinstance(code, str) else 0,
    )

    await emit_tool_use_event(
        manager=manager,
        provider="gemini",
        tool_name="code_execution",
        tool_input={"code": code or "", "language": language or "PYTHON"},
    )

    payload = {
        "name": "code_execution",
        "toolName": "code_execution",
        "input": {"code": code or "", "language": language or "PYTHON"},
        "toolInput": {"code": code or "", "language": language or "PYTHON"},
        "id": None,
        "callId": None,
        "provider": "gemini",
        "requires_action": False,
    }
    logger.debug(
        "Gemini code_execution payload created: language=%s requires_action=%s",
        language or "PYTHON",
        payload["requires_action"],
    )

    return [payload]


__all__ = [
    "emit_code_execution",
    "emit_content_events",
    "emit_function_call",
    "process_candidate",
]
