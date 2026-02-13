"""Text generation operations for Gemini provider."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any, Optional

from core.exceptions import ProviderError
from core.providers.text.utils import prepare_gemini_contents
from core.pydantic_schemas import ProviderResponse

from .config import apply_tools_to_config, build_generation_config, prepare_tool_settings

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from google.genai import types  # type: ignore
    from .provider import GeminiTextProvider

logger = logging.getLogger(__name__)


async def generate_text(
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
    request_kwargs: dict[str, Any],
) -> ProviderResponse:
    if not prompt and not request_kwargs.get("audio_parts") and not messages:
        raise ProviderError("Prompt or audio input required", provider="gemini")

    if model:
        model_name = model
    else:
        model_config = provider.get_model_config()
        model_name = model_config.model_name if model_config else "gemini-2.5-flash"
    config = _build_config(
        provider=provider,
        context="generate",
        model_name=model_name,
        temperature=temperature,
        max_tokens=max_tokens,
        system_prompt=system_prompt,
        enable_reasoning=enable_reasoning,
        reasoning_value=reasoning_value,
        prompt=prompt,
        request_kwargs=request_kwargs,
    )

    contents = _build_contents(
        provider=provider,
        prompt=prompt,
        messages=messages,
        audio_parts=request_kwargs.get("audio_parts"),
    )

    logger.debug(
        "Gemini API call: model=%s, contents_count=%d, config=%s",
        model_name,
        len(contents),
        {
            "temperature": config.temperature,
            "max_output_tokens": getattr(config, "max_output_tokens", None),
            "system_instruction": "present"
            if getattr(config, "system_instruction", None)
            else "none",
            "thinking_config": str(getattr(config, "thinking_config", None))
            if getattr(config, "thinking_config", None)
            else "none",
        },
    )

    try:
        response = await provider._generate_async(model_name, contents, config)
    except Exception as exc:  # pragma: no cover - defensive, wrapped below
        logger.error("Gemini generate error: %s", exc)
        raise ProviderError(f"Gemini error: {exc}", provider="gemini") from exc

    text = getattr(response, "text", "")
    reasoning: str | None = None
    metadata: dict[str, Any] | None = None

    if hasattr(response, "candidates"):
        candidates = getattr(response, "candidates") or []
        if candidates:
            candidate = candidates[0]
            grounding = getattr(candidate, "grounding_metadata", None)
            reasoning, metadata = _extract_grounding_metadata(grounding)

    usage_metadata = getattr(response, "usage_metadata", None)
    if usage_metadata:
        metadata = metadata or {}
        metadata["usage"] = usage_metadata

    return ProviderResponse(
        text=text or "",
        model=model_name,
        provider="gemini",
        reasoning=reasoning,
        metadata=metadata,
    )


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
    audio_parts: Any | None = None,
) -> list[Any]:
    model_config = provider.get_model_config()
    attachment_limit = (
        model_config.file_attached_message_limit if model_config else 2
    )
    contents = prepare_gemini_contents(
        prompt=prompt,
        messages=messages or [],
        audio_parts=audio_parts,
        attachment_limit=attachment_limit,
    )
    if not contents:
        raise ProviderError("Gemini payload is empty", provider="gemini")
    return contents


def _extract_grounding_metadata(grounding: Any) -> tuple[str | None, dict[str, Any] | None]:
    """Serialise Gemini grounding metadata into safe response fields."""

    if not grounding:
        return None, None

    metadata_payload: dict[str, Any] | None = None
    reasoning_text: str | None = None

    if isinstance(grounding, str):
        reasoning_text = grounding
    elif isinstance(grounding, dict):
        metadata_payload = grounding
    else:
        to_dict = getattr(grounding, "to_dict", None)
        if callable(to_dict):
            try:
                metadata_payload = to_dict()
            except Exception:  # pragma: no cover - defensive logging only
                logger.debug("Gemini grounding metadata to_dict() failed", exc_info=True)

    if metadata_payload is not None:
        try:
            reasoning_text = json.dumps(metadata_payload)
        except TypeError:
            reasoning_text = str(metadata_payload)

    if reasoning_text is None:
        reasoning_text = repr(grounding)

    return reasoning_text, metadata_payload


__all__ = ["generate_text"]
