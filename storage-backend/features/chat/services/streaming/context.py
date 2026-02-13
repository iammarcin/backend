"""Utilities for resolving prompt and provider context for chat streaming.

This module centralises the logic that adapts raw chat prompts into the
provider-specific configuration required by the various streaming entry points.
Each helper returns both the parsed prompt context and the provider metadata so
that the callers can focus on business logic instead of repetitive plumbing.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from features.chat.utils.generation_context import (
    resolve_generation_context as _resolve_generation_context,
)
from features.chat.utils.prompt_utils import (
    PromptInput,
    parse_prompt as _parse_prompt,
)

from .helpers import get_helper


def resolve_prompt_and_provider(
    *,
    prompt: PromptInput,
    settings: Dict[str, Any],
    customer_id: int,
    model: Optional[str] = None,
):
    """Return the parsed prompt context and provider configuration.

    The implementation honours helper overrides registered via ``get_helper`` so
    that tests and feature flags can inject custom prompt parsing or provider
    selection logic.  The function returns a tuple containing the parsed prompt
    context followed by the provider handle and sampling parameters.
    """

    parse_prompt_fn = get_helper("parse_prompt", _parse_prompt)
    resolve_context_fn = get_helper(
        "resolve_generation_context", _resolve_generation_context
    )

    context = parse_prompt_fn(prompt)
    provider, resolved_model, temperature, max_tokens = resolve_context_fn(
        prompt_text=context.text_prompt,
        settings=settings,
        customer_id=customer_id,
        model=model,
    )
    return context, provider, resolved_model, temperature, max_tokens


__all__ = ["resolve_prompt_and_provider"]
