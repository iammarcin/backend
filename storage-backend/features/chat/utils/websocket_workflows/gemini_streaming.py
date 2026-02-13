"""Gemini response streaming helpers."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict

from core.streaming.manager import StreamingManager
from features.chat.utils.websocket_workflows.tts import handle_tts_workflow

logger = logging.getLogger(__name__)


async def _call_gemini_multimodal_and_stream(
    *,
    wav_data: bytes,
    text_prompt: str,
    model_name: str,
    user_input: Dict[str, Any],
    settings: Dict[str, Any],
    customer_id: int,
    manager: StreamingManager,
    timings: Dict[str, float],
) -> Dict[str, Any]:
    """Invoke Gemini multimodal API and stream results to the frontend."""

    from core.clients.ai import get_gemini_client
    from google.genai import types as genai_types  # type: ignore

    _ = user_input  # Reserved for future use by downstream consumers

    logger.info(
        "Calling Gemini multimodal API (model=%s, audio_size=%s)",
        model_name,
        len(wav_data),
    )

    await manager.send_to_queues(
        {
            "type": "custom_event",
            "event_type": "aiTextModelInUse",
            "content": {
                "type": "aiTextModelInUse",
                "message": "aiTextModelReceived",
                "aiTextModel": model_name,
                "provider": "gemini",
            },
        }
    )

    timings.setdefault("text_request_sent_time", time.time())

    client = get_gemini_client()

    text_part: Any = text_prompt
    audio_part = genai_types.Part.from_bytes(data=wav_data, mime_type="audio/wav")
    contents = [text_part, audio_part]

    text_settings = settings.get("text") if isinstance(settings, dict) else {}

    temperature = text_settings.get("temperature", 0.7) if isinstance(text_settings, dict) else 0.7
    max_tokens_candidate = 4096
    if isinstance(text_settings, dict):
        candidate = text_settings.get("maxTokens") or text_settings.get("max_tokens")
        try:
            if candidate is not None:
                max_tokens_candidate = int(candidate)
        except (TypeError, ValueError):  # pragma: no cover - defensive guard
            logger.debug("Invalid maxTokens value provided: %s", candidate)

    def _invoke() -> Any:
        config = genai_types.GenerateContentConfig(
            temperature=float(temperature) if temperature is not None else 0.7,
            max_output_tokens=max_tokens_candidate,
        )
        return client.models.generate_content(
            model=model_name,
            contents=contents,
            config=config,
        )

    use_streaming = bool(
        isinstance(text_settings, dict) and text_settings.get("stream", True)
        or (not isinstance(text_settings, dict))
    )

    try:
        if use_streaming:
            collected_text = await _stream_gemini_response(
                client=client,
                model_name=model_name,
                contents=contents,
                temperature=temperature,
                max_output_tokens=max_tokens_candidate,
                manager=manager,
                timings=timings,
            )
        else:
            response = await asyncio.to_thread(_invoke)
            collected_text = getattr(response, "text", "") or ""
            if collected_text:
                timings.setdefault("text_first_response_time", time.time())
                await manager.send_to_queues({"type": "text_chunk", "content": collected_text})
                manager.collect_chunk(collected_text, "text")

        timings["text_response_time"] = time.time()
        logger.info(
            "Gemini response received (customer=%s, length=%s chars)",
            customer_id,
            len(collected_text),
        )

        await manager.send_to_queues({"type": "text_completed", "content": ""})

        tts_enabled = bool(
            isinstance(settings, dict)
            and isinstance(settings.get("tts"), dict)
            and settings["tts"].get("tts_auto_execute")
        )

        tts_result: Dict[str, Any] | None = None
        if tts_enabled and collected_text.strip():
            tts_result = await handle_tts_workflow(
                prompt=[{"type": "text", "text": collected_text}],
                settings=settings,
                customer_id=customer_id,
                manager=manager,
                timings=timings,
            )
        else:
            await manager.send_to_queues({"type": "tts_not_requested", "content": ""})

        result: Dict[str, Any] = {
            "text_response": collected_text,
            "ai_response": collected_text,
        }
        if tts_result:
            result.update(tts_result)

        return result
    except Exception:
        logger.error("Gemini multimodal API call failed", exc_info=True)
        raise


async def _stream_gemini_response(
    *,
    client: Any,
    model_name: str,
    contents: list[Any],
    temperature: Any,
    max_output_tokens: int,
    manager: StreamingManager,
    timings: Dict[str, float],
) -> str:
    """Stream Gemini response and forward each chunk to the frontend."""

    from google.genai import types as genai_types  # type: ignore

    collected_text = ""

    def _stream() -> Any:
        config = genai_types.GenerateContentConfig(
            temperature=float(temperature) if temperature is not None else 0.7,
            max_output_tokens=max_output_tokens,
        )
        return client.models.generate_content_stream(
            model=model_name,
            contents=contents,
            config=config,
        )

    response_stream = await asyncio.to_thread(_stream)

    first_chunk = True
    for chunk in response_stream:
        chunk_text = getattr(chunk, "text", "") if chunk is not None else ""
        if not chunk_text:
            continue

        if first_chunk:
            timings.setdefault("text_first_response_time", time.time())
            first_chunk = False

        collected_text += chunk_text
        await manager.send_to_queues({"type": "text_chunk", "content": chunk_text})
        manager.collect_chunk(chunk_text, "text")

    return collected_text


__all__ = ["_call_gemini_multimodal_and_stream", "_stream_gemini_response"]

