from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from contextlib import suppress

from websockets.asyncio.client import ClientConnection, connect

from config.api_keys import OPENAI_API_KEY
from core.exceptions import ProviderError

logger = logging.getLogger(__name__)

_WEBSOCKET_URL = "wss://api.openai.com/v1/realtime"


def build_session_config(
    *,
    model: str,
    language: str,
    prompt: str | None = None,
    enable_vad: bool = True,
    vad_threshold: float = 0.5,
    vad_prefix_padding_ms: int = 300,
    vad_silence_duration_ms: int = 500,
    session_model: str = "gpt-realtime",
    transcription_model: str | None = None,
    transcription_only: bool = False,
) -> dict[str, Any]:
    """Construct the session configuration payload for OpenAI Realtime API.

    Args:
        model: DEPRECATED - use session_model and transcription_model instead
        session_model: The realtime session model (e.g., 'gpt-realtime')
        transcription_model: Optional transcription model (e.g., 'gpt-4o-transcribe')
        transcription_only: If True, set output_modalities to ["text"] (no audio generation)
        language: Transcription language code
        prompt: Optional transcription prompt
        enable_vad: Enable voice activity detection
        vad_threshold: VAD sensitivity threshold
        vad_prefix_padding_ms: VAD prefix padding
        vad_silence_duration_ms: VAD silence duration
    """

    session_config: dict[str, Any] = {
        "type": "session.update",
        "session": {
            "type": "realtime",
            "model": session_model,  # ← FIXED: Always set session model
            "output_modalities": ["text"] if transcription_only else ["audio"],
            "audio": {
                "input": {
                    "format": {
                        "type": "audio/pcm",
                        "rate": 24000,
                    },
                    "turn_detection": None,
                }
            },
        },
    }

    # Only add transcription config if transcription model specified
    if transcription_model:
        session_config["session"]["audio"]["input"]["transcription"] = {
            "model": transcription_model,
            "language": language,
        }

    if prompt and transcription_model:
        session_config["session"]["audio"]["input"]["transcription"]["prompt"] = prompt

    if enable_vad:
        session_config["session"]["audio"]["input"]["turn_detection"] = {
            "type": "server_vad",
            "threshold": vad_threshold,
            "prefix_padding_ms": vad_prefix_padding_ms,
            "silence_duration_ms": vad_silence_duration_ms,
        }

    return session_config


async def connect_to_openai_realtime(
    *,
    model: str,
    language: str,
    prompt: str | None = None,
    enable_vad: bool = True,
    vad_threshold: float = 0.5,
    vad_prefix_padding_ms: int = 300,
    vad_silence_duration_ms: int = 500,
    timeout: float = 10.0,
    session_model: str = "gpt-realtime",
    transcription_model: str | None = None,
    transcription_only: bool = False,
) -> ClientConnection:
    """Establish and configure a WebSocket session with OpenAI Realtime API.

    Args:
        model: DEPRECATED - use session_model and transcription_model instead
        session_model: The realtime session model (default: 'gpt-realtime')
        transcription_model: Optional transcription model (e.g., 'gpt-4o-transcribe')
        transcription_only: If True, set output_modalities to ["text"] (no audio generation)
        language: Transcription language
        prompt: Optional transcription prompt
        enable_vad: Enable voice activity detection
        vad_threshold: VAD sensitivity
        vad_prefix_padding_ms: VAD prefix padding
        vad_silence_duration_ms: VAD silence duration
        timeout: Connection timeout in seconds
    """

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
    }
    # Use session model for WebSocket URL (always a realtime model)
    websocket_url = f"{_WEBSOCKET_URL}?model={session_model}"

    logger.info(
        "Connecting to OpenAI Realtime API (session_model=%s, transcription_model=%s, language=%s, vad=%s)",
        session_model,
        transcription_model,
        language,
        enable_vad,
    )

    try:
        ws_client = await asyncio.wait_for(
            connect(
                websocket_url,
                additional_headers=headers,
                ping_interval=None,
            ),
            timeout=timeout,
        )
        logger.info("WebSocket connection established")
    except asyncio.TimeoutError as exc:
        logger.error("OpenAI Realtime connection timed out after %.1fs", timeout)
        raise ProviderError(
            f"OpenAI connection timeout after {timeout:.1f}s",
            provider="openai-streaming",
        ) from exc
    except Exception as exc:  # pragma: no cover - defensive path
        logger.error("Failed to connect to OpenAI Realtime API: %s", exc)
        raise ProviderError(
            f"OpenAI connection failed: {exc}",
            provider="openai-streaming",
            original_error=exc,
        ) from exc

    session_config = build_session_config(
        model=model,  # DEPRECATED param for backwards compat
        session_model=session_model,
        transcription_model=transcription_model,
        transcription_only=transcription_only,
        language=language,
        prompt=prompt,
        enable_vad=enable_vad,
        vad_threshold=vad_threshold,
        vad_prefix_padding_ms=vad_prefix_padding_ms,
        vad_silence_duration_ms=vad_silence_duration_ms,
    )

    logger.debug("Sending session configuration: %s", session_config)

    try:
        await ws_client.send(json.dumps(session_config))
        logger.info("Session configuration sent successfully")
    except Exception as exc:  # pragma: no cover - defensive path
        logger.error("Failed to send session configuration: %s", exc)
        with suppress(Exception):
            await ws_client.close()
        raise ProviderError(
            f"Failed to configure OpenAI session: {exc}",
            provider="openai-streaming",
            original_error=exc,
        ) from exc

    return ws_client


__all__ = [
    "build_session_config",
    "connect_to_openai_realtime",
]
