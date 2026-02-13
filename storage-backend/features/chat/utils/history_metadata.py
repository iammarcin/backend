"""Resolve metadata required for chat history persistence requests."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from .websocket_workflow_executor import StandardWorkflowOutcome


def normalise_session_id(candidate: Any) -> Optional[str]:
    if not candidate:
        return None
    value = str(candidate).strip()
    return value or None


def build_request_metadata(
    *,
    user_input: Mapping[str, Any],
    settings: Mapping[str, Any],
    workflow: StandardWorkflowOutcome,
    customer_id: int,
) -> Dict[str, Any]:
    return {
        "customer_id": customer_id,
        "session_id": normalise_session_id(user_input.get("session_id")),
        "session_name": user_input.get("session_name"),
        "ai_character_name": _resolve_ai_character_name(user_input, settings),
        "ai_text_gen_model": (
            user_input.get("ai_text_gen_model")
            or settings.get("text", {}).get("model")
        ),
        "tags": _resolve_tags(user_input),
        "auto_trigger_tts": _resolve_auto_trigger_tts(user_input, settings),
        "claude_session_id": _resolve_claude_session_id(workflow, user_input),
        "claude_code_data": workflow.result.get("claude_code_data"),
        "user_settings": dict(settings),
        "update_last_mod_time": _resolve_update_flag(user_input),
    }


def _resolve_tags(user_input: Mapping[str, Any]) -> list[str]:
    tags = user_input.get("tags")
    if isinstance(tags, list):
        return [str(tag) for tag in tags]
    return []


def _resolve_auto_trigger_tts(
    user_input: Mapping[str, Any], settings: Mapping[str, Any]
) -> bool:
    value = (
        user_input.get("auto_trigger_tts")
        or settings.get("general", {}).get("tts_auto_execute")
    )
    return bool(value)


def _resolve_ai_character_name(
    user_input: Mapping[str, Any], settings: Mapping[str, Any]
) -> Optional[str]:
    return (
        user_input.get("new_ai_character_name")
        or user_input.get("ai_character_name")
        or settings.get("text", {}).get("ai_character")
    )


def _resolve_claude_session_id(
    workflow: StandardWorkflowOutcome, user_input: Mapping[str, Any]
) -> Optional[str]:
    return (
        workflow.result.get("claude_session_id")
        or user_input.get("claude_session_id")
    )


def _resolve_update_flag(user_input: Mapping[str, Any]) -> bool:
    value = user_input.get("update_last_mod_time")
    if value is None:
        return True
    return bool(value)


__all__ = ["build_request_metadata", "normalise_session_id"]
