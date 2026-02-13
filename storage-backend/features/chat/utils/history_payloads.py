"""Helpers for assembling chat history persistence payloads."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Mapping, MutableMapping, Optional

from pydantic import ValidationError as PydanticValidationError

from features.chat.schemas.message_content import MessageContent
from features.chat.utils.prompt_utils import PromptInput, parse_prompt

from .websocket_workflow_executor import StandardWorkflowOutcome

logger = logging.getLogger(__name__)


def coerce_dict(payload: Any) -> Dict[str, Any]:
    if isinstance(payload, Mapping):
        return dict(payload)
    return {}


def resolve_prompt_text(prompt: Optional[PromptInput]) -> Optional[str]:
    if prompt is None:
        return None
    try:
        context = parse_prompt(prompt)
    except Exception:  # pragma: no cover - defensive guard
        return None
    return context.text_prompt or None


def calculate_timing_metrics(timings: Mapping[str, float]) -> Dict[str, float]:
    """Timer fields removed per canonical field naming contract."""
    # Timer fields (time_to_*, elapsed_time, etc.) are no longer persisted.
    # This function is kept for API compatibility but always returns empty dict.
    return {}


def _augment_files(payload: MutableMapping[str, Any], audio_file: Optional[str]) -> None:
    if not audio_file:
        return
    files = list(payload.get("file_locations") or [])
    if audio_file not in files:
        payload["file_locations"] = [audio_file, *files]


def _extract_chart_data_from_tool_results(tool_results: Any) -> Optional[list[Dict[str, Any]]]:
    """Extract chart payloads from tool results for persistence."""
    if not tool_results or not isinstance(tool_results, list):
        return None

    chart_data = []
    for tool_result in tool_results:
        if isinstance(tool_result, dict):
            result = tool_result.get("result")
            if isinstance(result, dict) and result.get("chart_payload"):
                chart_data.append(result["chart_payload"])

    return chart_data if chart_data else None


def build_user_message_payload(
    *,
    user_input: Dict[str, Any],
    prompt_text: Optional[str],
    timings: Mapping[str, float],
    transcription: Optional[str],
) -> MessageContent:
    raw_user_message = coerce_dict(user_input.get("user_message"))
    payload: Dict[str, Any] = dict(raw_user_message)

    if not payload.get("message"):
        payload["message"] = transcription or prompt_text

    payload.setdefault("sender", payload.get("sender") or "User")

    _augment_files(payload, user_input.get("audio_file_name"))

    timing_metrics = calculate_timing_metrics(timings)
    if timing_metrics:
        payload.update(timing_metrics)

    return MessageContent.model_validate(payload)


def build_ai_message_payload(
    *,
    user_input: Dict[str, Any],
    settings: Mapping[str, Any],
    workflow: StandardWorkflowOutcome,
    timings: Mapping[str, float],
) -> Optional[MessageContent]:
    text_response = workflow.result.get("text_response")
    reasoning = workflow.result.get("reasoning")
    image_data = workflow.result.get("image_data") or {}
    tts_metadata = workflow.result.get("tts") or {}

    raw_ai_message = coerce_dict(user_input.get("ai_response"))
    payload: Dict[str, Any] = dict(raw_ai_message)

    payload.setdefault("sender", payload.get("sender") or "AI")

    if text_response:
        payload["message"] = text_response

    if reasoning and not payload.get("ai_reasoning"):
        payload["ai_reasoning"] = reasoning

    # Extract ai_reasoning from tool results (e.g., judge verdict from browser automation)
    if not payload.get("ai_reasoning"):
        tool_results = workflow.result.get("tool_results")
        if tool_results and isinstance(tool_results, list):
            for tool_result in tool_results:
                if isinstance(tool_result, dict) and tool_result.get("ai_reasoning"):
                    payload["ai_reasoning"] = tool_result["ai_reasoning"]
                    logger.info(
                        "📝 Extracted ai_reasoning from tool result: %s",
                        tool_result.get("tool", "unknown")
                    )
                    break

    text_settings = settings.get("text") if isinstance(settings, Mapping) else {}
    if text_settings and not payload.get("api_text_gen_settings"):
        payload["api_text_gen_settings"] = text_settings

    model_name = (
        user_input.get("ai_text_gen_model")
        or text_settings.get("model")
    )
    if model_name:
        payload.setdefault("api_text_gen_model_name", model_name)

    if tts_metadata:
        payload["is_tts"] = True
        if tts_metadata.get("model"):
            payload.setdefault("api_tts_gen_model_name", tts_metadata.get("model"))
        audio_file = tts_metadata.get("audio_file_url")
        if not audio_file:
            storage_meta = tts_metadata.get("storage_metadata")
            if storage_meta:
                audio_file = storage_meta.get("s3_url")
        _augment_files(payload, audio_file)

    if isinstance(image_data, Mapping):
        image_url = image_data.get("image_url")
        if image_url:
            payload["image_locations"] = [image_url]
        settings_payload = image_data.get("settings")
        if settings_payload and not payload.get("api_image_gen_settings"):
            payload["api_image_gen_settings"] = settings_payload
        if text_response:
            payload.setdefault(
                "image_generation_request",
                {
                    "prompt": text_response,
                    "input_image_url": image_data.get("input_image_url"),
                    "image_mode": user_input.get("mode"),
                },
            )

    claude_code_data = workflow.result.get("claude_code_data")
    if claude_code_data and not payload.get("claude_code_data"):
        payload["claude_code_data"] = claude_code_data

    chart_payloads: List[Dict[str, Any]] = []
    if getattr(workflow, "chart_payloads", None):
        chart_payloads = [dict(payload) for payload in workflow.chart_payloads if isinstance(payload, dict)]
    elif isinstance(workflow.result.get("chart_payloads"), list):
        chart_payloads = [
            dict(payload) for payload in workflow.result.get("chart_payloads", []) if isinstance(payload, dict)
        ]

    if not chart_payloads:
        chart_payloads = _extract_chart_data_from_tool_results(workflow.result.get("tool_results")) or []

    if chart_payloads:
        payload["chart_data"] = chart_payloads

    timing_metrics = calculate_timing_metrics(timings)
    if timing_metrics:
        payload.update(timing_metrics)

    try:
        ai_message = MessageContent.model_validate(payload)
    except PydanticValidationError as exc:
        logger.warning("Failed to validate AI message payload: %s", exc)
        return None

    return ai_message if ai_message.has_content() else None


__all__ = [
    "build_ai_message_payload",
    "build_user_message_payload",
    "calculate_timing_metrics",
    "coerce_dict",
    "resolve_prompt_text",
]
