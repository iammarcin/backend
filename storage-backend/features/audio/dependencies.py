"""Dependency helpers for the audio feature."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, List

from fastapi import Form
from pydantic import ValidationError as PydanticValidationError

from features.audio.schemas import StaticTranscriptionRequest
from features.audio.service import STTService


@dataclass(slots=True)
class ParsedStaticTranscription:
    """Wrapper returning either a parsed request or validation errors."""

    request: StaticTranscriptionRequest | None
    errors: List[Dict[str, Any]] | None


async def parse_static_transcription_form(
    action: str = Form(..., description="Requested static transcription action"),
    category: str = Form(..., description="Feature category, must be 'speech'"),
    customer_id: int = Form(..., ge=1),
    user_input: str = Form("{}"),
    user_settings: str = Form("{}"),
) -> ParsedStaticTranscription:
    """Parse multipart form data into a structured request model."""

    errors: List[Dict[str, Any]] = []

    def _parse_json(raw_value: str, field: str) -> Dict[str, Any]:
        try:
            value = raw_value.strip()
            if not value:
                return {}
            return json.loads(value)
        except json.JSONDecodeError:
            errors.append({"loc": [field], "msg": "Invalid JSON", "type": "value_error.jsondecode"})
            return {}

    parsed_user_input = _parse_json(user_input, "user_input")
    parsed_user_settings = _parse_json(user_settings, "user_settings")

    if errors:
        return ParsedStaticTranscription(request=None, errors=errors)

    raw_payload = {
        "action": action,
        "category": category,
        "user_input": parsed_user_input,
        "user_settings": parsed_user_settings,
        "customer_id": customer_id,
    }
    try:
        request = StaticTranscriptionRequest.model_validate(raw_payload)
    except PydanticValidationError as exc:
        return ParsedStaticTranscription(request=None, errors=exc.errors())
    return ParsedStaticTranscription(request=request, errors=None)


@lru_cache(maxsize=1)
def _stt_service_singleton() -> STTService:
    return STTService()


def get_stt_service() -> STTService:
    """Return a cached instance of :class:`STTService`."""

    return _stt_service_singleton()


__all__ = [
    "ParsedStaticTranscription",
    "get_stt_service",
    "parse_static_transcription_form",
]
