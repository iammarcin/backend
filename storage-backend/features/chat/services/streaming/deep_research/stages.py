"""Individual stages for the deep research workflow."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Tuple

from core.streaming.manager import StreamingManager

from ..events import (
    emit_deep_research_analyzing,
    emit_deep_research_optimizing,
    emit_deep_research_searching,
)
from ..deep_research_config import DEEP_RESEARCH_DEFAULTS, get_deep_research_config
from ..deep_research_helpers import (
    build_analysis_prompt_text,
    build_optimization_prompt_text,
    resolve_primary_provider,
)
from features.chat.utils.model_swap import get_provider_for_model


logger = logging.getLogger("features.chat.services.streaming.deep_research")


async def optimize_research_prompt(
    *,
    user_query: str,
    chat_history: str,
    settings: Dict[str, Any],
    customer_id: int,
    manager: StreamingManager,
) -> str:
    """Stage 1: Optimize user query into research prompt."""

    logger.info("Stage 1: Optimizing research prompt (customer=%s)", customer_id)
    await emit_deep_research_optimizing(manager)

    today = datetime.now().strftime("%Y-%m-%d")
    optimization_prompt_text = build_optimization_prompt_text(
        user_query=user_query,
        chat_history=chat_history,
        today=today,
    )

    provider, _ = resolve_primary_provider(settings, customer_id, logger=logger)

    optimisation_temperature = get_deep_research_config(
        "optimization_temperature", settings
    )
    optimisation_max_tokens = get_deep_research_config(
        "optimization_max_tokens", settings
    )

    response = await provider.generate(
        prompt=optimization_prompt_text,
        temperature=float(optimisation_temperature or 0.2),
        max_tokens=int(optimisation_max_tokens or 800),
    )

    optimized_text = getattr(response, "text", "").strip()
    if not optimized_text:
        logger.warning("Optimization returned empty text (customer=%s)", customer_id)
        optimized_text = user_query

    optimized_with_date = f"Today is {today}\n{optimized_text}"
    logger.info(
        "Prompt optimized (customer=%s, chars=%s)",
        customer_id,
        len(optimized_with_date),
    )
    return optimized_with_date


REASONING_EFFORT_MAP = {
    0: "low",
    1: "medium",
    2: "high",
    "low": "low",
    "medium": "medium",
    "high": "high",
}


def _resolve_reasoning_effort(settings: Dict[str, Any]) -> str:
    """Translate user provided reasoning effort to Perplexity API format."""

    raw_value = get_deep_research_config("deep_research_reasoning_effort", settings)

    if isinstance(raw_value, str):
        normalised = raw_value.strip().lower()
        if normalised.isdigit():
            raw_value = int(normalised)
        elif normalised in REASONING_EFFORT_MAP:
            return REASONING_EFFORT_MAP[normalised]

    if isinstance(raw_value, (int, float)):
        int_value = int(raw_value)
        return REASONING_EFFORT_MAP.get(int_value, "medium")

    return "medium"


async def execute_deep_research(
    *,
    optimized_prompt: str,
    settings: Dict[str, Any],
    customer_id: int,
    manager: StreamingManager,
) -> Tuple[str, List[Dict[str, Any]]]:
    """Stage 2: Execute Perplexity deep research."""

    logger.info("Stage 2: Executing deep research (customer=%s)", customer_id)
    await emit_deep_research_searching(manager, optimized_prompt=optimized_prompt)

    research_model = str(
        get_deep_research_config("deep_research_model", settings)
        or DEEP_RESEARCH_DEFAULTS["deep_research_model"]
    ).lower()

    if research_model != "perplexity":
        logger.warning(
            "Unsupported deep research model '%s', defaulting to Perplexity (customer=%s)",
            research_model,
            customer_id,
        )
        research_model = "perplexity"

    target_model_name = "sonar-deep-research"
    provider = get_provider_for_model(
        model_name=target_model_name,
        base_settings=settings,
        enable_reasoning=True,
    )

    research_temperature = get_deep_research_config("research_temperature", settings)
    research_max_tokens = get_deep_research_config("research_max_tokens", settings)

    reasoning_effort = _resolve_reasoning_effort(settings)

    logger.info(
        "Using reasoning effort '%s' for deep research (customer=%s)",
        reasoning_effort,
        customer_id,
    )

    response = await provider.generate(
        prompt=optimized_prompt,
        temperature=float(research_temperature or 0.2),
        max_tokens=int(research_max_tokens or 2048),
        model=target_model_name,
        reasoning_effort=reasoning_effort,
    )

    research_text = getattr(response, "text", "").strip()
    citations = getattr(response, "citations", None) or []

    logger.info(
        "Deep research completed (customer=%s, chars=%s, citations=%s)",
        customer_id,
        len(research_text),
        len(citations),
    )
    return research_text, citations


async def analyze_research_findings(
    *,
    research_response: str,
    original_query: str,
    chat_history: str,
    optimized_prompt: str,
    settings: Dict[str, Any],
    customer_id: int,
    manager: StreamingManager,
) -> AsyncGenerator[str, None]:
    """Stage 3: Stream conversational analysis."""

    logger.info("Stage 3: Analyzing research findings (customer=%s)", customer_id)
    await emit_deep_research_analyzing(manager)

    analysis_prompt_text = build_analysis_prompt_text(
        original_query=original_query,
        chat_history=chat_history,
        research_response=research_response,
        optimized_prompt=optimized_prompt,
    )

    provider, text_settings = resolve_primary_provider(
        settings, customer_id, logger=logger
    )

    temperature = text_settings.get("temperature", 0.7)
    max_tokens = text_settings.get("max_tokens", 4096)

    async for chunk in provider.stream(
        prompt=analysis_prompt_text,
        temperature=temperature,
        max_tokens=max_tokens,
    ):
        yield str(chunk)

    logger.info("Analysis streaming completed (customer=%s)", customer_id)


__all__ = [
    "optimize_research_prompt",
    "execute_deep_research",
    "analyze_research_findings",
]
