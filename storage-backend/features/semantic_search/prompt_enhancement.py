"""Main logic for enhancing user prompts with semantic search context."""

from __future__ import annotations

import logging
from typing import Any

from core.streaming.manager import StreamingManager

from features.semantic_search.service import get_semantic_search_service
from features.semantic_search.utils.settings_parser import parse_semantic_settings
from features.semantic_search.services.multi_tier_search_service import MultiTierSearchConfig

from .prompt_enhancement_events import send_context_added_event
from .prompt_enhancement_prompt import extract_prompt_text
from .prompt_enhancement_result import PromptInput, SemanticEnhancementResult


logger = logging.getLogger(__name__)

SESSION_SEARCH_MODES = {"session_semantic", "session_hybrid", "multi_tier"}


def _estimate_result_count(context: str, search_mode: str) -> int:
    """Heuristically estimate how many results were injected based on search mode."""

    if not context:
        return 0

    normalized_mode = (search_mode or "").lower()
    if normalized_mode in SESSION_SEARCH_MODES:
        return context.count("### ")
    return context.count("**User:**") + context.count("**Assistant:**")


async def enhance_prompt_with_semantic_context(
    *,
    prompt: PromptInput,
    customer_id: int,
    user_settings: dict[str, Any],
    manager: StreamingManager | None = None,
    current_session_id: str | None = None,
) -> SemanticEnhancementResult:
    """Enhance a user prompt with semantic search context."""

    settings = parse_semantic_settings(user_settings, current_session_id)
    if not settings:
        logger.debug("Semantic search disabled, returning original prompt")
        return SemanticEnhancementResult(
            enhanced_prompt=prompt,
            original_prompt=prompt,
            context_added=False,
        )

    try:
        semantic_service = get_semantic_search_service()
    except Exception as exc:
        logger.error("Failed to get semantic service: %s", exc, exc_info=True)
        return SemanticEnhancementResult(
            enhanced_prompt=prompt,
            original_prompt=prompt,
            error=str(exc),
        )

    if not semantic_service:
        logger.warning("Semantic search service unavailable")
        return SemanticEnhancementResult(
            enhanced_prompt=prompt,
            original_prompt=prompt,
            error="Service unavailable",
        )

    from features.semantic_search.rate_limiter import get_rate_limiter

    rate_limiter = get_rate_limiter()
    if not rate_limiter.is_allowed(customer_id):
        logger.warning("Semantic search rate limited for customer %s", customer_id)
        return SemanticEnhancementResult(
            enhanced_prompt=prompt,
            original_prompt=prompt,
            rate_limited=True,
        )

    prompt_text, prompt_error = extract_prompt_text(prompt)
    if prompt_error:
        logger.warning("Invalid prompt format: %s", type(prompt).__name__)
        return SemanticEnhancementResult(
            enhanced_prompt=prompt,
            original_prompt=prompt,
            error=prompt_error,
        )

    if not prompt_text:
        logger.debug("Empty prompt text, skipping semantic search")
        return SemanticEnhancementResult(
            enhanced_prompt=prompt,
            original_prompt=prompt,
        )

    if settings.filter_fields_provided:
        logger.info(
            "Semantic search with filters: customer=%s, mode=%s, messageType=%s, tags=%s, dateRange=%s, sessionIds=%s, limit=%s, threshold=%s",
            customer_id,
            settings.search_mode,
            settings.message_type,
            settings.tags,
            settings.date_range,
            settings.session_ids,
            settings.limit,
            settings.threshold,
        )
    else:
        logger.info(
            "Semantic search for customer %s (mode=%s, limit=%s, threshold=%s)",
            customer_id,
            settings.search_mode,
            settings.limit,
            settings.threshold,
        )

    try:
        context = await semantic_service.search_and_format_context(
            query=prompt_text,
            customer_id=customer_id,
            limit=settings.limit,
            score_threshold=settings.threshold,
            search_mode=settings.search_mode,
            tags=settings.tags,
            date_range=settings.date_range,
            message_type=settings.message_type,
            session_ids=settings.session_ids,
            manager=manager,
            top_sessions=settings.top_sessions,
            messages_per_session=settings.messages_per_session,
        )
    except Exception as exc:
        logger.error("Semantic search failed: %s", exc, exc_info=True)
        return SemanticEnhancementResult(
            enhanced_prompt=prompt,
            original_prompt=prompt,
            error=str(exc),
        )

    if not context:
        logger.info("No relevant context found in semantic search")
        return SemanticEnhancementResult(
            enhanced_prompt=prompt,
            original_prompt=prompt,
            filters_applied=settings.has_filters,
        )

    result_count = _estimate_result_count(context, settings.search_mode)
    token_count = semantic_service.context_formatter.token_counter.count_tokens(context)

    logger.info(
        "Semantic search found %s relevant messages (%s tokens)",
        result_count,
        token_count,
    )

    if isinstance(prompt, str):
        augmented_prompt: PromptInput = f"{context}\n\n{prompt}"
    else:
        augmented_prompt = [
            {"type": "text", "text": f"{context}\n\n"},
            *prompt,
        ]

    session_results_payload = None
    if settings.search_mode == "multi_tier":
        config = MultiTierSearchConfig(
            top_sessions=settings.top_sessions,
            messages_per_session=settings.messages_per_session,
        )
        try:
            multi_results = await semantic_service.multi_tier_service.search(
                query=prompt_text,
                customer_id=customer_id,
                config=config,
            )
            session_results_payload = [result.to_dict() for result in multi_results]
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Failed to build multi-tier session payload: %s", exc)

    if manager:
        await send_context_added_event(
            manager=manager,
            result_count=result_count,
            token_count=token_count,
            settings=settings,
            search_mode=settings.search_mode,
            session_results=session_results_payload,
        )

    return SemanticEnhancementResult(
        enhanced_prompt=augmented_prompt,
        original_prompt=prompt,
        context_added=True,
        result_count=result_count,
        tokens_used=token_count,
        filters_applied=settings.has_filters,
    )


__all__ = ["enhance_prompt_with_semantic_context", "SemanticEnhancementResult"]
