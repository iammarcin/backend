"""Helpers for consistent WebSocket lifecycle logging."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import WebSocket

from core.observability.request_logging import render_payload_preview


logger = logging.getLogger(__name__)


def _format_client(websocket: WebSocket) -> str:
    client = websocket.client
    if not client:
        return "unknown"

    host = getattr(client, "host", None)
    port = getattr(client, "port", None)

    if host and port is not None:
        return f"{host}:{port}"
    if host:
        return host
    return "unknown"


def log_websocket_upgrade_attempt(
    websocket: WebSocket,
    *,
    endpoint: str | None = None,
) -> None:
    """Log when a WebSocket upgrade is attempted on an endpoint."""

    path = endpoint or websocket.url.path
    client_addr = _format_client(websocket)

    upgrade_header = websocket.headers.get("upgrade", "")
    connection_header = websocket.headers.get("connection", "")

    is_upgrade = upgrade_header.lower() == "websocket" and "upgrade" in connection_header.lower()

    if not is_upgrade:
        logger.warning(
            "Possible WebSocket endpoint accessed without upgrade headers: %s from %s "
            "(upgrade=%s, connection=%s)",
            path,
            client_addr,
            upgrade_header or "<missing>",
            connection_header or "<missing>",
        )


def log_websocket_accepted(
    websocket: WebSocket,
    *,
    session_id: str | None = None,
    customer_id: int | None = None,
) -> None:
    """Log that a WebSocket connection has been accepted."""

    client_addr = _format_client(websocket)

    context_parts: list[str] = []
    if session_id:
        context_parts.append(f"session={session_id}")
    if customer_id:
        context_parts.append(f"customer={customer_id}")

    context = f" ({', '.join(context_parts)})" if context_parts else ""

    logger.info(
        "✅ WebSocket connection established: %s from %s%s",
        websocket.url.path,
        client_addr,
        context,
    )


def log_websocket_rejected(
    websocket: WebSocket,
    *,
    reason: str,
    code: int = 1008,
) -> None:
    """Log that a WebSocket connection was rejected before completion."""

    client_addr = _format_client(websocket)
    logger.warning(
        "❌ WebSocket connection rejected: %s from %s (code=%s, reason=%s)",
        websocket.url.path,
        client_addr,
        code,
        reason,
    )


def log_websocket_error(
    websocket: WebSocket,
    *,
    error: BaseException,
    context: str | None = None,
) -> None:
    """Log an error that occurred while handling a WebSocket connection."""

    client_addr = _format_client(websocket)
    message = (
        f"WebSocket error for {websocket.url.path} from {client_addr}"
        if not context
        else f"WebSocket error ({context}) for {websocket.url.path} from {client_addr}"
    )
    logger.error("%s: %s", message, error, exc_info=error)


def _extract_user_settings(data: dict) -> dict | None:
    """Extract user_settings from WebSocket payload using canonical field name."""
    settings = data.get("user_settings")
    return settings if isinstance(settings, dict) else None


def _format_settings_summary(settings: dict) -> str:
    """Format key settings into a compact summary string."""
    parts: list[str] = []

    # General settings (check canonical snake_case first, then legacy camelCase)
    general = settings.get("general", {})
    if isinstance(general, dict):
        ai_agent = general.get("ai_agent_enabled")
        if ai_agent is not None:
            parts.append(f"agent={ai_agent}")
        profile = general.get("ai_agent_profile")
        if profile:
            parts.append(f"profile={profile}")

    # Text settings
    text = settings.get("text", {})
    if isinstance(text, dict):
        model = text.get("model")
        if model:
            parts.append(f"model={model}")
        temp = text.get("temperature")
        if temp is not None:
            parts.append(f"temp={temp}")
        max_tokens = text.get("max_tokens")
        if max_tokens:
            parts.append(f"max_tokens={max_tokens}")

    # TTS settings
    tts = settings.get("tts", {})
    if isinstance(tts, dict):
        tts_enabled = tts.get("enabled")
        if tts_enabled is not None:
            parts.append(f"tts={tts_enabled}")
        tts_voice = tts.get("voice")
        if tts_voice:
            parts.append(f"voice={tts_voice}")

    # Audio settings
    audio = settings.get("audio", {})
    if isinstance(audio, dict):
        audio_enabled = audio.get("enabled")
        if audio_enabled is not None:
            parts.append(f"audio={audio_enabled}")

    # Speech settings
    speech = settings.get("speech", {})
    if isinstance(speech, dict):
        send_full = speech.get("send_full_audio_to_llm")
        if send_full is not None:
            parts.append(f"audio_direct={send_full}")

    return ", ".join(parts) if parts else "<empty>"


def log_websocket_message_received(
    data: Any,
    *,
    session_id: str | None = None,
    redact_fields: set[str] | None = None,
) -> None:
    """Log incoming WebSocket payload with optional field redaction."""

    preview = render_payload_preview(data)
    session_context = f" (session={session_id})" if session_id else ""

    if isinstance(data, dict):
        request_type = data.get("request_type") or data.get("type") or "unknown"
        key_fields: list[str] = []

        if "prompt" in data:
            prompt_value = str(data["prompt"])
            prompt_preview = prompt_value[:50]
            if len(prompt_value) > 50:
                prompt_preview += "..."
            key_fields.append(f"prompt='{prompt_preview}'")

        settings = data.get("settings")
        if isinstance(settings, dict):
            text_settings = settings.get("text")
            if isinstance(text_settings, dict):
                model = text_settings.get("model")
                if model:
                    key_fields.append(f"model={model}")
                temperature = text_settings.get("temperature")
                if temperature is not None:
                    key_fields.append(f"temp={temperature}")

            tts_settings = settings.get("tts")
            if isinstance(tts_settings, dict):
                tts_enabled = tts_settings.get("enabled", False)
                key_fields.append(f"tts={tts_enabled}")

            audio_settings = settings.get("audio")
            if isinstance(audio_settings, dict):
                audio_enabled = audio_settings.get("enabled", False)
                key_fields.append(f"audio={audio_enabled}")

        key_info = f" [{', '.join(key_fields)}]" if key_fields else ""

        logger.info(
            "WebSocket message received%s: type=%s%s",
            session_context,
            request_type,
            key_info,
        )

        # Log user_settings separately to ensure visibility even when payload is truncated
        user_settings = _extract_user_settings(data)
        if user_settings:
            settings_summary = _format_settings_summary(user_settings)
            logger.info(
                "WebSocket user_settings%s: %s",
                session_context,
                settings_summary,
            )

        logger.info("WebSocket message payload%s: %s", session_context, preview)
    else:
        logger.info("WebSocket message received%s: %s", session_context, preview)

    if redact_fields:
        logger.debug("Requested redaction for fields: %s", ", ".join(sorted(redact_fields)))


__all__ = [
    "log_websocket_upgrade_attempt",
    "log_websocket_accepted",
    "log_websocket_rejected",
    "log_websocket_error",
    "log_websocket_message_received",
]
