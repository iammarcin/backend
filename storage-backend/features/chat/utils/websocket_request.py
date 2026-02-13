"""Utilities for parsing inbound chat WebSocket payloads.

All payloads must use canonical snake_case format. These helpers extract
fields and normalise the shape so the dispatcher can focus on workflow logic.
"""

import logging
from typing import Any, Dict, Optional

from features.chat.utils.prompt_utils import PromptInput

logger = logging.getLogger(__name__)


def normalise_request_type(data: Dict[str, Any]) -> str:
    """Return the request type using either legacy or modern field names.

    If the payload represents an audio request and ``send_full_audio_to_llm`` is
    enabled, the request type is coerced to ``audio_direct`` so downstream
    workflow routing can bypass the STT flow and send audio directly to the LLM.
    """

    raw_request_type = data.get("request_type")
    if raw_request_type:
        request_type = str(raw_request_type).lower()
    else:
        message_type = data.get("type")
        if message_type:
            request_type = str(message_type).lower()
        else:
            request_type = "text"

    if request_type == "audio":
        settings = extract_settings(data)
        speech_settings = settings.get("speech", {}) if isinstance(settings, dict) else {}
        send_full_audio = speech_settings.get("send_full_audio_to_llm", False)

        if send_full_audio:
            logger.info(
                "Detected send_full_audio_to_llm=true, switching to audio_direct mode",
            )
            return "audio_direct"

    return request_type


def extract_settings(data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract user-provided settings from payload using canonical field name."""

    settings = data.get("user_settings")
    if isinstance(settings, dict):
        return settings

    return {}


def extract_agent_settings(data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract AI agent settings from WebSocket payload.

    Note: Agentic workflow has been removed. This function returns disabled
    for backward compatibility with clients that may still send these settings.
    """
    # Agentic workflow removed - always return disabled
    return {"enabled": False, "profile": "general"}


def extract_prompt(data: Dict[str, Any]) -> Optional[PromptInput]:
    """Return a prompt payload from payload structure."""

    prompt: Optional[PromptInput] = data.get("prompt")
    if prompt:
        return prompt

    user_input = data.get("user_input")
    if isinstance(user_input, dict):
        prompt = user_input.get("prompt")
        if prompt:
            return prompt

        # Kotlin "Speak" feature sends the message text as ``user_input.text``
        # when requesting TTS for an existing chat message. Treat this the same
        # way as a standard prompt payload so the dispatcher does not reject
        # the request for lacking a prompt field.
        raw_text = user_input.get("text")
        if isinstance(raw_text, str) and raw_text.strip():
            return [
                {"type": "text", "text": raw_text.strip()},
            ]

        user_message = user_input.get("user_message")
        if isinstance(user_message, dict):
            message_text = user_message.get("message")
            if message_text:
                return [
                    {"type": "text", "text": str(message_text)},
                ]

    message = data.get("message")
    if isinstance(message, dict):
        message_text = message.get("message")
        if message_text:
            return [
                {"type": "text", "text": str(message_text)},
            ]

    if isinstance(message, str) and message.strip():
        return [{"type": "text", "text": message.strip()}]

    return None
