"""WebSocket mode detection utilities.

Helpers for determining which chat pipeline to use based on query params,
headers, and initial payload content.
"""

from __future__ import annotations

from typing import Iterable, Mapping, Optional

from fastapi import WebSocket

from config.text.providers import MODEL_ALIASES
from config.realtime.providers.openai import REALTIME_MODELS


_TRUTHY_QUERY_VALUES = {"1", "true", "yes", "on"}
_REALTIME_MODES = {"realtime", "real-time"}


def _normalise_hint(value: str) -> str:
    """Return a standardised representation of realtime hint strings."""
    return value.strip().lower().replace("_", "-")


_REALTIME_MODEL_HINTS = {model.lower() for model in REALTIME_MODELS.keys()}
_REALTIME_MODEL_HINTS.update(
    alias.lower()
    for alias, target in MODEL_ALIASES.items()
    if target.lower() in _REALTIME_MODEL_HINTS
)


def _iter_model_hints(payload: Mapping[str, object]) -> Iterable[str]:
    """Yield potential model identifiers from an initial websocket payload."""
    top_level_model = payload.get("model")
    if isinstance(top_level_model, str) and top_level_model:
        yield top_level_model

    user_input = payload.get("user_input")
    if isinstance(user_input, Mapping):
        for key in ("ai_text_gen_model", "model"):
            candidate = user_input.get(key)
            if isinstance(candidate, str) and candidate:
                yield candidate

    settings = payload.get("user_settings")
    if isinstance(settings, Mapping):
        text_settings = settings.get("text")
        if isinstance(text_settings, Mapping):
            for key in ("model", "ai_text_gen_model"):
                candidate = text_settings.get(key)
                if isinstance(candidate, str) and candidate:
                    yield candidate


def _normalise_model_name(model_name: str) -> str:
    """Return the canonical identifier for a potential realtime model."""
    lowered = model_name.strip().lower()
    return MODEL_ALIASES.get(lowered, lowered)


def initial_message_targets_realtime(
    initial_message: Mapping[str, object] | None,
) -> bool:
    """Return ``True`` when an initial payload indicates realtime mode."""
    if not isinstance(initial_message, Mapping):
        return False

    request_type = initial_message.get("request_type")
    if isinstance(request_type, str):
        normalised = _normalise_hint(request_type)
        if normalised in {"realtime", "real-time", "text-realtime"}:
            return True

    message_type = initial_message.get("type")
    if isinstance(message_type, str):
        if _normalise_hint(message_type) in {"realtime", "real-time"}:
            return True

    for model_hint in _iter_model_hints(initial_message):
        normalised_model = _normalise_model_name(model_hint)
        if not normalised_model:
            continue
        lowered_model = normalised_model.lower()
        if lowered_model in _REALTIME_MODEL_HINTS:
            return True
        if normalised_model in REALTIME_MODELS:
            return True

    return False


def should_use_realtime(websocket: WebSocket) -> bool:
    """Return ``True`` when the websocket request targets realtime mode."""
    params = websocket.query_params

    mode_param = (
        params.get("mode")
        or params.get("chat_mode")
        or params.get("ws_mode")
        or websocket.headers.get("x-chat-mode")
    )
    if mode_param and mode_param.lower() in _REALTIME_MODES:
        return True

    realtime_flag = (
        params.get("realtime")
        or params.get("enable_realtime")
        or params.get("realtime_mode")
        or websocket.headers.get("x-enable-realtime")
    )
    if realtime_flag and realtime_flag.lower() in _TRUTHY_QUERY_VALUES:
        return True

    return False


def should_use_proactive(
    websocket: WebSocket,
) -> tuple[bool, Optional[int], Optional[str], Optional[str]]:
    """Check if websocket request targets proactive mode.

    Returns:
        Tuple of (is_proactive, user_id, session_id, client_id)
    """
    params = websocket.query_params

    mode_param = (
        params.get("mode")
        or params.get("chat_mode")
        or params.get("ws_mode")
        or websocket.headers.get("x-chat-mode")
    )

    if mode_param and mode_param.lower() == "proactive":
        user_id_str = params.get("user_id")
        session_id = params.get("session_id")
        client_id = params.get("client_id")

        user_id = int(user_id_str) if user_id_str and user_id_str.isdigit() else None

        return True, user_id, session_id, client_id

    return False, None, None, None


__all__ = [
    "initial_message_targets_realtime",
    "should_use_realtime",
    "should_use_proactive",
]
