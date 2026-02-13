"""Handlers for updating and removing chat history messages."""

from __future__ import annotations

from core.exceptions import ValidationError

from features.chat.schemas.requests import RemoveMessagesRequest, UpdateMessageRequest
from features.chat.schemas.responses import MessageUpdateResult, MessagesRemovedResult

from .base import HistoryRepositories
from .semantic_indexing import queue_semantic_deletion_tasks


async def update_message(
    repositories: HistoryRepositories, request: UpdateMessageRequest
) -> MessageUpdateResult:
    """Apply a JSON-style patch to a stored message."""

    if not request.patch:
        return MessageUpdateResult(message_id=request.message_id)

    payload = request.patch.to_payload()
    if not payload:
        raise ValidationError("No update fields provided", field="patch")

    message = await repositories.messages.update_message(
        message_id=request.message_id,
        customer_id=request.customer_id,
        payload=payload,
        append_image_locations=request.append_image_locations,
    )
    return MessageUpdateResult(message_id=message.message_id)


async def remove_messages(
    repositories: HistoryRepositories, request: RemoveMessagesRequest
) -> MessagesRemovedResult:
    """Delete the selected messages from a session."""

    removed = await repositories.messages.remove_messages(
        session_id=request.session_id,
        customer_id=request.customer_id,
        message_ids=request.message_ids,
    )

    if removed:
        await queue_semantic_deletion_tasks(message_ids=request.message_ids)

    return MessagesRemovedResult(
        removed_count=removed,
        message_ids=request.message_ids,
    )


__all__ = ["update_message", "remove_messages"]
