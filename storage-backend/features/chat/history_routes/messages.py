"""Endpoints that manage chat message persistence."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import Depends, HTTPException

from core.auth import AuthContext, require_auth_context
from core.pydantic_schemas import ApiResponse
from features.chat.dependencies import get_chat_history_service
from features.chat.schemas.requests import (
    CreateMessageRequest,
    EditMessageRequest,
    RemoveMessagesRequest,
    UpdateMessageRequest,
)
from features.chat.schemas.responses import MessageUpdateResult
from features.chat.service import ChatHistoryService

from .shared import execute_service_call, history_router


@history_router.post(
    "/messages",
    response_model=ApiResponse[Dict[str, Any]],
)
async def create_message_endpoint(
    request: CreateMessageRequest,
    auth_context: AuthContext = Depends(require_auth_context),
    service: ChatHistoryService = Depends(get_chat_history_service),
):
    """Persist one or more chat messages generated during a conversation."""

    if auth_context["customer_id"] != request.customer_id:
        raise HTTPException(status_code=403, detail="Access denied: customer ID mismatch")

    return await execute_service_call(
        lambda: service.create_message(request),
        success_message="Chat messages stored successfully",
        formatter=lambda result: result.model_dump(),
    )


@history_router.patch(
    "/messages",
    response_model=ApiResponse[Dict[str, Any]],
)
async def edit_message_endpoint(
    request: EditMessageRequest,
    auth_context: AuthContext = Depends(require_auth_context),
    service: ChatHistoryService = Depends(get_chat_history_service),
):
    """Modify fields on existing messages without replacing the entire record."""

    if auth_context["customer_id"] != request.customer_id:
        raise HTTPException(status_code=403, detail="Access denied: customer ID mismatch")

    return await execute_service_call(
        lambda: service.edit_message(request),
        success_message="Chat messages updated successfully",
        formatter=lambda result: result.model_dump(),
    )


@history_router.put(
    "/messages",
    response_model=ApiResponse[MessageUpdateResult],
)
async def update_message_endpoint(
    request: UpdateMessageRequest,
    auth_context: AuthContext = Depends(require_auth_context),
    service: ChatHistoryService = Depends(get_chat_history_service),
):
    """Replace a message payload while keeping its identifier stable."""

    if auth_context["customer_id"] != request.customer_id:
        raise HTTPException(status_code=403, detail="Access denied: customer ID mismatch")

    return await execute_service_call(
        lambda: service.update_message(request),
        success_message="Message updated successfully",
        formatter=lambda result: result.model_dump(by_alias=True, exclude_none=True),
    )


@history_router.delete(
    "/messages",
    response_model=ApiResponse[Dict[str, Any]],
)
async def remove_messages_endpoint(
    request: RemoveMessagesRequest,
    auth_context: AuthContext = Depends(require_auth_context),
    service: ChatHistoryService = Depends(get_chat_history_service),
):
    """Delete a batch of messages from a session and return the affected IDs."""

    if auth_context["customer_id"] != request.customer_id:
        raise HTTPException(status_code=403, detail="Access denied: customer ID mismatch")

    return await execute_service_call(
        lambda: service.remove_messages(request),
        success_message="Messages removed successfully",
        formatter=lambda result: result.model_dump(by_alias=True, exclude_none=True),
    )


__all__ = [
    "create_message_endpoint",
    "edit_message_endpoint",
    "remove_messages_endpoint",
    "update_message_endpoint",
]
