"""Streaming operations for Gemini provider."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, AsyncIterator, Optional, Set

if TYPE_CHECKING:
    from features.chat.utils.websocket_runtime import WorkflowRuntime

from core.exceptions import ProviderError
from core.providers.text.utils import prepare_gemini_contents
from core.streaming.manager import StreamingManager

from .config import apply_tools_to_config, build_generation_config, prepare_tool_settings
from .events import handle_gemini_tool_chunk

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from google.genai import types  # type: ignore
    from .provider import GeminiTextProvider

logger = logging.getLogger(__name__)


async def stream_text(
    provider: "GeminiTextProvider",
    *,
    prompt: str,
    model: Optional[str],
    temperature: float,
    max_tokens: int,
    system_prompt: Optional[str],
    messages: Optional[list[dict[str, Any]]],
    enable_reasoning: bool,
    reasoning_value: Optional[int],
    runtime: Optional["WorkflowRuntime"] = None,
    request_kwargs: dict[str, Any],
) -> AsyncIterator[str | dict[str, Any]]:
    if model:
        model_name = model
    else:
        model_config = provider.get_model_config()
        model_name = model_config.model_name if model_config else "gemini-2.5-flash"
    config = _build_config(
        provider=provider,
        context="stream",
        model_name=model_name,
        temperature=temperature,
        max_tokens=max_tokens,
        system_prompt=system_prompt,
        enable_reasoning=enable_reasoning,
        reasoning_value=reasoning_value,
        prompt=prompt,
        request_kwargs=request_kwargs,
    )

    async_client = provider._get_async_client()
    if not async_client or not hasattr(async_client, "models"):
        raise ProviderError("Gemini client does not support streaming", provider="gemini")

    contents = _build_contents(
        provider=provider,
        prompt=prompt,
        messages=messages,
    )

    manager: StreamingManager | None = request_kwargs.pop("manager", None)
    seen_tool_events: Set[str] = set()

    logger.debug(
        "Gemini stream: model=%s, prompt_length=%d, config=%s",
        model_name,
        len(contents),
        {
            "temperature": config.temperature,
            "thinking_config": str(getattr(config, "thinking_config", None))
            if getattr(config, "thinking_config", None)
            else "none",
        },
    )

    try:
        stream = await async_client.models.generate_content_stream(
            model=model_name,
            contents=contents,
            config=config,
        )
    except Exception as exc:  # pragma: no cover
        logger.error("Gemini stream error: %s", exc)
        raise ProviderError(f"Gemini streaming error: {exc}", provider="gemini") from exc

    try:
        async for chunk in stream:
            # Check cancellation
            if runtime and runtime.is_cancelled():
                logger.info(
                    "Gemini stream cancelled by user (model=%s)",
                    model_name,
                )
                break  # Exit loop, close stream

            # Existing tool handling
            tool_payloads = await handle_gemini_tool_chunk(
                chunk=chunk,
                manager=manager,
                seen=seen_tool_events,
            )
            for payload in tool_payloads:
                yield {
                    "type": "tool_call",
                    "content": payload,
                    "requires_action": False,
                }

            # Process candidates and parts
            candidates = getattr(chunk, "candidates", None)
            if candidates:
                for candidate in candidates:
                    content = getattr(candidate, "content", None)
                    if content:
                        parts = getattr(content, "parts", None)
                        if parts:
                            for part in parts:
                                part_text = getattr(part, "text", None)
                                is_thought = getattr(part, "thought", False)

                                if part_text:
                                    if is_thought:
                                        # Thinking content
                                        logger.debug("Gemini thinking part: %s", part_text[:50])
                                        yield {"type": "reasoning", "content": part_text}
                                    else:
                                        # Regular content
                                        yield part_text

            # FALLBACK: If no parts found, use chunk.text (existing behavior)
            if not candidates or not any(
                getattr(c, "content", None) and getattr(getattr(c, "content"), "parts", None)
                for c in candidates or []
            ):
                text = getattr(chunk, "text", None)
                if text:
                    yield text

        try:
            if hasattr(stream, "response"):
                final_response = getattr(stream, "response", None)
                if final_response:
                    logger.debug("Checking final stream response for grounding metadata and thinking")

                    # Existing tool handling
                    final_payloads = await handle_gemini_tool_chunk(
                        chunk=final_response,
                        manager=manager,
                        seen=seen_tool_events,
                    )
                    for payload in final_payloads:
                        yield {
                            "type": "tool_call",
                            "content": payload,
                            "requires_action": False,
                        }

                    # Extract thinking from final response if present
                    candidates = getattr(final_response, "candidates", None)
                    if candidates:
                        for candidate in candidates:
                            content = getattr(candidate, "content", None)
                            if content:
                                parts = getattr(content, "parts", None)
                                if parts:
                                    for part in parts:
                                        if getattr(part, "thought", False):
                                            thought_text = getattr(part, "text", None)
                                            if thought_text:
                                                logger.info("Gemini thinking in final response: %s", thought_text[:100])
                                                yield {"type": "reasoning", "content": thought_text}
        except Exception as exc:  # pragma: no cover
            logger.debug("Could not access final stream response: %s", exc)

    except asyncio.CancelledError:
        # Handle explicit task cancellation
        logger.info("Gemini stream task cancelled (model=%s)", model_name)
        raise  # Re-raise for cleanup


def _build_config(
    *,
    provider: "GeminiTextProvider",
    context: str,
    model_name: str,
    temperature: float,
    max_tokens: int,
    system_prompt: Optional[str],
    enable_reasoning: bool,
    reasoning_value: Optional[int],
    prompt: Optional[str],
    request_kwargs: dict[str, Any],
) -> "types.GenerateContentConfig":
    config = build_generation_config(
        model_name=model_name,
        temperature=temperature,
        max_tokens=max_tokens,
        system_prompt=system_prompt,
        enable_reasoning=enable_reasoning,
        reasoning_value=reasoning_value,
    )

    tool_settings = prepare_tool_settings(
        request_kwargs.pop("tool_settings", None)
    )
    apply_tools_to_config(
        config=config,
        tool_settings=tool_settings,
        context=context,
    )
    return config


def _build_contents(
    *,
    provider: "GeminiTextProvider",
    prompt: str,
    messages: Optional[list[dict[str, Any]]],
) -> list[Any]:
    model_config = provider.get_model_config()
    attachment_limit = (
        model_config.file_attached_message_limit if model_config else 2
    )
    contents = prepare_gemini_contents(
        prompt=prompt,
        messages=messages or [],
        audio_parts=None,
        attachment_limit=attachment_limit,
    )
    if not contents:
        raise ProviderError("Gemini payload is empty", provider="gemini")
    return contents


__all__ = ["stream_text"]
