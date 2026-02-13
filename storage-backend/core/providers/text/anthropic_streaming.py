"""Streaming operations for Anthropic provider."""

from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, AsyncIterator, Optional

if TYPE_CHECKING:
    from features.chat.utils.websocket_runtime import WorkflowRuntime

from core.clients.ai import ai_clients
from core.exceptions import ProviderError
from core.providers.text.utils import log_tool_usage
from core.streaming.manager import StreamingManager
from .anthropic_events import emit_anthropic_tool_events, iter_tool_call_payloads
from .anthropic_params import build_api_params, prepare_messages

logger = logging.getLogger(__name__)


async def stream_anthropic(
    client,
    *,
    prompt: str,
    model: Optional[str] = "claude-sonnet-4-5",
    temperature: float = 0.1,
    max_tokens: int = 4096,
    system_prompt: Optional[str] = None,
    messages: Optional[list[dict[str, Any]]] = None,
    enable_reasoning: bool = False,
    reasoning_value: Optional[int] = None,
    runtime: Optional["WorkflowRuntime"] = None,
    **kwargs: Any,
) -> AsyncIterator[str | dict[str, Any]]:
    """Stream response chunks using Anthropic's streaming API."""

    if not prompt:
        raise ProviderError("Prompt cannot be empty", provider="anthropic")

    final_messages = prepare_messages(prompt, messages)

    manager: StreamingManager | None = kwargs.pop("manager", None)
    provider_instance = kwargs.pop("provider", None)
    provider_for_tools = provider_instance or SimpleNamespace(provider_name="anthropic")
    seen_tools: set[str] = set()

    # Pop settings to avoid passing to API
    kwargs.pop("settings", None)

    provided_tools = kwargs.pop("tools", None)
    disable_native_tools = kwargs.pop("disable_native_tools", False)

    # Build base_tools - use provided tools or default native tools
    if provided_tools is not None:
        base_tools = provided_tools
    else:
        if disable_native_tools:
            base_tools = []
        else:
            if hasattr(provider_for_tools, "get_native_tools"):
                base_tools = provider_for_tools.get_native_tools()
            else:
                base_tools = [
                    {
                        "type": "web_search_20250305",
                        "name": "web_search",
                        "max_uses": 5,
                    }
                ]

    api_params = build_api_params(
        model=model,
        messages=final_messages,
        max_tokens=max_tokens,
        temperature=temperature,
        system_prompt=system_prompt,
        enable_reasoning=enable_reasoning,
        reasoning_value=reasoning_value,
        tools=base_tools,
        extra_kwargs=kwargs,
    )

    logger.info(
        "Calling Anthropic API: model=%s messages=%d tools=%d",
        api_params.get("model") or "claude-sonnet-4-5",
        len(final_messages),
        len(api_params.get("tools", [])),
    )
    logger.debug(
        "Anthropic params: system_prompt=%s temperature=%.2f max_tokens=%d thinking=%s",
        "present" if system_prompt else "none",
        api_params.get("temperature", 0.0),
        api_params.get("max_tokens", 0),
        api_params.get("thinking", "disabled"),
    )

    try:
        stream = client.messages.stream(**api_params)
    except Exception as exc:  # pragma: no cover
        logger.error("Anthropic stream error: %s", exc)
        raise ProviderError(f"Anthropic streaming error: {exc}", provider="anthropic") from exc

    content_blocks: list[Any] | None = None
    try:
        async with stream as event_stream:
            # Always process raw events to handle both reasoning and regular text streaming
            thinking_block_id = None
            text_block_id = None

            try:
                async for event in event_stream:
                    if runtime and runtime.is_cancelled():
                        logger.info(
                            "Anthropic stream cancelled by user (model=%s)",
                            model,
                        )
                        break  # Exit loop, close stream

                    event_type = event.type

                    # Track content block types
                    if event_type == "content_block_start":
                        block = event.content_block
                        if block.type == "thinking":
                            thinking_block_id = event.index
                            logger.debug("Anthropic thinking block started: index=%s", thinking_block_id)
                        elif block.type == "text":
                            text_block_id = event.index

                    # Yield thinking or text deltas
                    elif event_type == "content_block_delta":
                        if event.delta.type == "text_delta":
                            chunk_text = event.delta.text
                            if chunk_text:
                                if enable_reasoning and event.index == thinking_block_id:
                                    logger.info("✅ Anthropic thinking delta: %s", chunk_text[:80])
                                    yield {"type": "reasoning", "content": chunk_text}
                                elif event.index == text_block_id:
                                    yield chunk_text
                        elif event.delta.type == "signature_delta":
                            logger.debug("Anthropic signature_delta event: index=%s", event.index)
            except asyncio.CancelledError:
                # Handle explicit task cancellation
                logger.info("Anthropic stream task cancelled (model=%s)", model)
                raise  # Re-raise for cleanup
            finally:
                try:
                    final_message = await event_stream.get_final_message()
                except Exception as exc:  # pragma: no cover - defensive
                    logger.debug("Anthropic stream final message unavailable: %s", exc)
                else:
                    if final_message:
                        content_blocks = getattr(final_message, "content", None)
    except asyncio.CancelledError:
        # Propagate cancellation after cleanup
        raise

    if not content_blocks:
        return

    for block in content_blocks:
        if enable_reasoning and hasattr(block, "type") and block.type == "thinking":
            thinking_text = (
                getattr(block, "thinking", None)
                or getattr(block, "text", None)
                or getattr(block, "signature", None)
            )
            if thinking_text:
                if isinstance(thinking_text, (bytes, bytearray)):
                    logger.debug(
                        "Anthropic thinking signature (encrypted): %d bytes",
                        len(thinking_text),
                    )
                else:
                    logger.info(
                        "✅ Anthropic thinking from final message: %s",
                        str(thinking_text)[:100],
                    )
                    yield {"type": "reasoning", "content": str(thinking_text)}

    log_tool_usage(
        "Anthropic",
        content_blocks,
        logger=logger,
    )
    await emit_anthropic_tool_events(
        content_blocks=content_blocks,
        manager=manager,
        seen=seen_tools,
    )

    for payload in iter_tool_call_payloads(content_blocks):
        yield {
            "type": "tool_call",
            "content": payload,
            "requires_action": False,
        }


__all__ = ["stream_anthropic"]
