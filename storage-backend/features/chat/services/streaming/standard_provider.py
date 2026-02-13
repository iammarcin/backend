"""Streaming helpers for non-Claude text providers."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from features.chat.utils.websocket_runtime import WorkflowRuntime

from core.streaming.manager import StreamingManager
from features.chat.utils.chat_history_formatter import (
    extract_and_format_chat_history,
    get_provider_name_from_model,
)
from features.chat.utils.reasoning_config import get_reasoning_config
from .events import emit_reasoning_custom_event, emit_tool_use_event


@dataclass
class StandardStreamOutcome:
    """Aggregate chunks emitted while streaming from a standard provider."""

    text_chunks: List[str]
    reasoning_chunks: List[str]
    tool_calls: List[Dict[str, Any]]
    requires_tool_action: bool = False


logger = logging.getLogger(__name__)


async def stream_standard_response(
    *,
    provider,
    manager: StreamingManager,
    prompt_text: str,
    model: str,
    temperature: float,
    max_tokens: int,
    system_prompt: Optional[str],
    user_input: Optional[Dict[str, Any]] = None,
    messages: Optional[list[dict[str, Any]]] = None,
    settings: Optional[Dict[str, Any]] = None,
    runtime: Optional["WorkflowRuntime"] = None,
    session_id: Optional[str] = None,
) -> StandardStreamOutcome:
    """Stream chunks from a standard provider and forward them to queues.

    Returns a tuple of (text_chunks, reasoning_chunks).
    """

    resolved_model = model or getattr(provider, "default_model", "")
    provider_name = getattr(provider, "provider_name", None) or get_provider_name_from_model(
        resolved_model
    )

    formatted_messages = messages
    if formatted_messages is None:
        history_payload: Dict[str, Any] = {}
        if isinstance(user_input, dict):
            history_payload = dict(user_input)
        existing_prompt = history_payload.get("prompt")
        if isinstance(existing_prompt, list) or isinstance(existing_prompt, dict):
            history_payload["prompt"] = existing_prompt
        else:
            history_payload["prompt"] = prompt_text

        formatted_messages = extract_and_format_chat_history(
            user_input=history_payload,
            system_prompt=system_prompt if provider_name != "anthropic" else None,
            provider_name=provider_name,
            model_name=model,
        )
        if not formatted_messages:
            base_message = {"role": "user", "content": prompt_text}
            formatted_messages = [base_message]
            if system_prompt and provider_name != "anthropic":
                formatted_messages.insert(0, {"role": "system", "content": system_prompt})

    text_settings: Dict[str, Any] = {}
    if isinstance(settings, dict):
        text_settings = settings.get("text", {}) if isinstance(settings.get("text"), dict) else {}

    enable_reasoning, reasoning_value = get_reasoning_config(
        settings=text_settings,
        model_config=provider.get_model_config()
        if hasattr(provider, "get_model_config")
        else None,
    )

    stream_kwargs: Dict[str, Any] = {
        "prompt": prompt_text,
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "system_prompt": system_prompt,
        "messages": formatted_messages,
    }

    if isinstance(settings, dict) and settings:
        stream_kwargs["settings"] = settings

    # Ensure providers receive the streaming manager so they can emit
    # provider-specific events such as tool usage notifications.
    stream_kwargs["manager"] = manager

    # Pass runtime for cancellation support
    if runtime is not None:
        stream_kwargs["runtime"] = runtime

    logger.info(
        "Sending request to LLM | provider=%s model=%s messages=%s",
        provider_name,
        model,
        str(formatted_messages)[:200],
    )
    if enable_reasoning:
        stream_kwargs["enable_reasoning"] = True
        if reasoning_value is not None:
            stream_kwargs["reasoning_value"] = reasoning_value

    tool_settings = (
        text_settings.get("tools") if isinstance(text_settings, dict) else {}
    )
    if isinstance(tool_settings, dict) and tool_settings:
        stream_kwargs["tool_settings"] = tool_settings

    collected_chunks: List[str] = []
    reasoning_chunks: List[str] = []
    tool_calls: List[Dict[str, Any]] = []
    awaiting_tool_action = False
    async for chunk in provider.stream(**stream_kwargs):
        if isinstance(chunk, dict) and chunk.get("type") == "reasoning":
            reasoning_text = str(chunk.get("content", ""))
            if reasoning_text:
                reasoning_chunks.append(reasoning_text)
                await emit_reasoning_custom_event(
                    manager,
                    reasoning_text=reasoning_text,
                    queue_type="frontend_only",
                )
                manager.collect_chunk(reasoning_text, "reasoning")
            continue

        if isinstance(chunk, dict) and chunk.get("type") == "tool_call":
            tool_payload = chunk.get("content")
            if tool_payload is None:
                tool_payload = {k: v for k, v in chunk.items() if k != "type"}
            if not isinstance(tool_payload, dict):
                tool_payload = {"value": tool_payload}
            requires_action = chunk.get("requires_action")
            if not isinstance(requires_action, bool):
                requires_action = (
                    tool_payload.get("requires_action")
                    if isinstance(tool_payload.get("requires_action"), bool)
                    else False
                )
            tool_name = tool_payload.get("toolName") or tool_payload.get("name")
            call_id = tool_payload.get("callId") or tool_payload.get("id")
            logger.info(
                "📞 Tool call received: provider=%s name=%s call_id=%s requires_action=%s",
                provider_name,
                tool_name,
                call_id,
                requires_action,
            )
            logger.debug(
                "Tool call flags: requires_action=%s (type=%s) awaiting_action_before=%s",
                requires_action,
                type(requires_action).__name__,
                awaiting_tool_action,
            )

            # Always collect the tool call for tracking
            manager.collect_tool_call(tool_payload)

            # Ensure requires_action is explicitly set on the tool_payload
            # This is critical for downstream logic that checks if client action is needed
            if "requires_action" not in tool_payload:
                tool_payload["requires_action"] = requires_action

            tool_calls.append(tool_payload)
            logger.info(
                "✅ Tool call collected: total_count=%d",
                len(tool_calls),
            )

            # For server-side tools (requires_action=False), the provider already emitted customEvent
            # Only send toolCall message and emit customEvent if client action is required
            if requires_action is True:
                # Emit toolUse custom event for frontend
                # Handle different tool payload structures (e.g., xAI has "value" array)
                tool_name = tool_name or tool_payload.get("toolName") or tool_payload.get("name")
                tool_input = tool_payload.get("toolInput") or tool_payload.get("input")
                call_id = call_id or tool_payload.get("callId") or tool_payload.get("id")
                tool_provider = tool_payload.get("provider")

                # If tool info not found at top level, try extracting from "value" array
                if not tool_name and "value" in tool_payload:
                    value_list = tool_payload.get("value", [])
                    if isinstance(value_list, list) and value_list:
                        first_call = value_list[0]
                        if isinstance(first_call, dict):
                            function_obj = first_call.get("function", {})
                            if isinstance(function_obj, dict):
                                tool_name = function_obj.get("name")
                                tool_input = function_obj.get("arguments")
                            call_id = call_id or first_call.get("id")

                # Fall back to defaults if still not found
                tool_name = tool_name or "unknown"
                tool_input = tool_input or {}
                tool_provider = tool_provider or provider_name

                await emit_tool_use_event(
                    manager=manager,
                    provider=tool_provider,
                    tool_name=tool_name,
                    tool_input=tool_input,
                    call_id=call_id,
                    session_id=session_id,
                )

                awaiting_tool_action = True
                logger.info(
                    "Client-side tool detected, awaiting action: tool=%s call_id=%s",
                    tool_name,
                    call_id,
                )
            continue

        text_chunk = str(chunk)
        if text_chunk and not awaiting_tool_action:
            collected_chunks.append(text_chunk)
            await manager.send_to_queues({"type": "text_chunk", "content": text_chunk})
            manager.collect_chunk(text_chunk, "text")

    logger.info(
        "Standard streaming finished: provider=%s text_chunks=%d reasoning_chunks=%d tool_calls=%d",
        provider_name,
        len(collected_chunks),
        len(reasoning_chunks),
        len(tool_calls),
    )

    return StandardStreamOutcome(
        text_chunks=collected_chunks,
        reasoning_chunks=reasoning_chunks,
        tool_calls=tool_calls,
        requires_tool_action=awaiting_tool_action,
    )


__all__ = ["StandardStreamOutcome", "stream_standard_response"]
