"""Prompt CRUD helpers for the chat history service."""

from __future__ import annotations

from core.exceptions import DatabaseError

from features.chat.schemas.requests import (
    PromptCreateRequest,
    PromptDeleteRequest,
    PromptListRequest,
    PromptUpdateRequest,
)
from features.chat.schemas.responses import (
    MessagesRemovedResult,
    PromptListResult,
    PromptRecord,
)

from .base import HistoryRepositories


async def list_prompts(
    repositories: HistoryRepositories, request: PromptListRequest
) -> PromptListResult:
    """Return all prompts for the customer."""

    prompts = await repositories.prompts.list_prompts(customer_id=request.customer_id)
    items = [PromptRecord.model_validate(prompt) for prompt in prompts]
    return PromptListResult(prompts=items)


async def add_prompt(
    repositories: HistoryRepositories, request: PromptCreateRequest
) -> PromptRecord:
    """Create a new saved prompt."""

    prompt = await repositories.prompts.add_prompt(
        customer_id=request.customer_id,
        title=request.title,
        prompt_text=request.prompt,
    )
    return PromptRecord(
        prompt_id=prompt.prompt_id,
        customer_id=prompt.customer_id,
        title=prompt.title,
        prompt=prompt.prompt,
    )


async def update_prompt(
    repositories: HistoryRepositories, request: PromptUpdateRequest
) -> PromptRecord:
    """Update the fields of an existing prompt."""

    prompt = await repositories.prompts.update_prompt(
        prompt_id=request.prompt_id,
        title=request.title,
        prompt_text=request.prompt,
    )
    return PromptRecord(
        prompt_id=prompt.prompt_id,
        customer_id=prompt.customer_id,
        title=prompt.title,
        prompt=prompt.prompt,
    )


async def delete_prompt(
    repositories: HistoryRepositories, request: PromptDeleteRequest
) -> MessagesRemovedResult:
    """Remove a stored prompt."""

    removed = await repositories.prompts.delete_prompt(prompt_id=request.prompt_id)
    if not removed:
        raise DatabaseError("Prompt not found", operation="delete_prompt")
    return MessagesRemovedResult(removed_count=1, prompt_id=request.prompt_id)
