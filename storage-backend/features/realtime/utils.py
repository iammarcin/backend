"""General utility helpers that support realtime chat session orchestration."""

from __future__ import annotations

import json
import logging
from typing import Iterable, Mapping
from uuid import uuid4

from fastapi import WebSocket

from core.observability import render_payload_preview
from features.realtime.schemas import (
    RealtimeHandshakeMessage,
    RealtimeSessionSettings,
    RealtimeSessionSnapshot,
)

logger = logging.getLogger(__name__)


def build_handshake(
    *, session_id: str, customer_id: int, settings: RealtimeSessionSettings
) -> RealtimeHandshakeMessage:
    """Return the handshake message sent to clients when a session starts."""

    snapshot = RealtimeSessionSnapshot(
        session_id=session_id,
        customer_id=customer_id,
        turn_id=None,
    )
    return RealtimeHandshakeMessage(session=snapshot, settings=settings)


def extract_customer_id(websocket: WebSocket) -> int:
    """Extract a numeric ``customer_id`` from query params, defaulting to ``1``."""

    query_params = dict(websocket.query_params)
    raw_customer = query_params.get("customer_id")
    if raw_customer is None:
        return 1
    try:
        return max(1, int(raw_customer))
    except (TypeError, ValueError):
        logger.warning(
            "Invalid customer_id supplied to realtime websocket", exc_info=False
        )
        return 1


def generate_session_id() -> str:
    """Return a random hexadecimal identifier for the realtime session."""

    return uuid4().hex


def parse_client_payload(raw_message: str) -> Mapping[str, object] | None:
    """Safely parse a client-sent JSON payload, returning ``None`` on failure."""

    try:
        payload = json.loads(raw_message)
    except json.JSONDecodeError:
        logger.warning(
            "Ignoring invalid realtime client payload: %s",
            render_payload_preview(raw_message),
        )
        return None
    if not isinstance(payload, Mapping):
        logger.warning(
            "Ignoring realtime payload that is not an object: %s",
            render_payload_preview(payload),
        )
        return None
    return payload


def required_modalities(settings: RealtimeSessionSettings) -> Iterable[str]:
    """Return the modalities that must complete for a given session."""

    modalities: list[str] = []
    if settings.requires_text_output():
        modalities.append("text")
    if settings.enable_audio_output and settings.tts_auto_execute:
        modalities.append("audio_output")
    return modalities


def is_google_model(model: str) -> bool:
    """Return ``True`` when ``model`` should be treated as a Google Gemini model."""

    model_normalised = (model or "").lower()
    return model_normalised.startswith("gemini") or "gemini" in model_normalised


__all__ = [
    "build_handshake",
    "extract_customer_id",
    "generate_session_id",
    "parse_client_payload",
    "required_modalities",
    "is_google_model",
]
