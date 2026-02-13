"""Endpoints that interact with chat session records."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import Depends, HTTPException

from core.auth import AuthContext, require_auth_context
from core.pydantic_schemas import ApiResponse
from features.chat.dependencies import get_chat_history_service
from features.chat.schemas.requests import (
    CreateTaskRequest,
    RemoveSessionRequest,
    SessionDetailRequest,
    SessionListRequest,
    SessionSearchRequest,
    UpdateSessionRequest,
)
from features.chat.schemas.responses import SessionListResult
from features.chat.service import ChatHistoryService

from .shared import execute_service_call, history_router, logger


@history_router.post(
    "/sessions/list",
    response_model=ApiResponse[SessionListResult],
)
async def list_sessions_endpoint(
    request: SessionListRequest,
    auth_context: AuthContext = Depends(require_auth_context),
    service: ChatHistoryService = Depends(get_chat_history_service),
):
    """List sessions for a customer, optionally including message previews."""

    if auth_context["customer_id"] != request.customer_id:
        raise HTTPException(status_code=403, detail="Access denied: customer ID mismatch")

    logger.info(
        "Listing chat sessions for customer_id=%s offset=%s limit=%s include_messages=%s filters=%s",
        request.customer_id,
        request.offset,
        request.limit,
        request.include_messages,
        {
            "start_date": request.start_date.isoformat() if request.start_date else None,
            "end_date": request.end_date.isoformat() if request.end_date else None,
            "tags": request.tags,
            "ai_character_name": request.ai_character_name,
            "task_status": request.task_status,
        },
    )

    response = await execute_service_call(
        lambda: service.list_sessions(request),
        success_message="Sessions retrieved successfully",
        formatter=lambda result: result.model_dump(by_alias=True, exclude_none=True),
    )

    if isinstance(response, dict):
        data = response.get("data") or {}
        logger.info(
            "List sessions completed for customer_id=%s count=%s",
            request.customer_id,
            data.get("count"),
        )
    return response


@history_router.post(
    "/sessions/detail",
    response_model=ApiResponse[Dict[str, Any]],
)
async def session_detail_endpoint(
    request: SessionDetailRequest,
    auth_context: AuthContext = Depends(require_auth_context),
    service: ChatHistoryService = Depends(get_chat_history_service),
):
    """Retrieve a detailed payload for a specific chat session."""

    if auth_context["customer_id"] != request.customer_id:
        raise HTTPException(status_code=403, detail="Access denied: customer ID mismatch")

    return await execute_service_call(
        lambda: service.get_session(request),
        success_message="Session retrieved successfully",
        formatter=lambda result: result.model_dump(),
    )


@history_router.post(
    "/sessions/search",
    response_model=ApiResponse[SessionListResult],
)
async def search_sessions_endpoint(
    request: SessionSearchRequest,
    auth_context: AuthContext = Depends(require_auth_context),
    service: ChatHistoryService = Depends(get_chat_history_service),
):
    """Search sessions using text filters and return paginated results."""

    if auth_context["customer_id"] != request.customer_id:
        raise HTTPException(status_code=403, detail="Access denied: customer ID mismatch")

    logger.info(
        "Searching chat sessions for customer_id=%s limit=%s query=%r",
        request.customer_id,
        request.limit,
        request.search_text,
    )

    response = await execute_service_call(
        lambda: service.search_sessions(request),
        success_message="Sessions matched successfully",
        formatter=lambda result: result.model_dump(by_alias=True, exclude_none=True),
    )

    if isinstance(response, dict):
        data = response.get("data") or {}
        logger.info(
            "Search sessions completed for customer_id=%s count=%s",
            request.customer_id,
            data.get("count"),
        )
    return response


@history_router.patch(
    "/sessions",
    response_model=ApiResponse[Dict[str, Any]],
)
async def update_session_endpoint(
    request: UpdateSessionRequest,
    auth_context: AuthContext = Depends(require_auth_context),
    service: ChatHistoryService = Depends(get_chat_history_service),
):
    """Update metadata for a stored session such as title or tags."""

    if auth_context["customer_id"] != request.customer_id:
        raise HTTPException(status_code=403, detail="Access denied: customer ID mismatch")

    return await execute_service_call(
        lambda: service.update_session(request),
        success_message="Session updated successfully",
        formatter=lambda result: result.model_dump(),
    )


@history_router.delete(
    "/sessions",
    response_model=ApiResponse[Dict[str, Any]],
)
async def remove_session_endpoint(
    request: RemoveSessionRequest,
    auth_context: AuthContext = Depends(require_auth_context),
    service: ChatHistoryService = Depends(get_chat_history_service),
):
    """Delete a chat session and return identifiers for the removed data."""

    if auth_context["customer_id"] != request.customer_id:
        raise HTTPException(status_code=403, detail="Access denied: customer ID mismatch")

    return await execute_service_call(
        lambda: service.remove_session(request),
        success_message="Session removed successfully",
        formatter=lambda result: result.model_dump(by_alias=True, exclude_none=True),
    )


@history_router.post(
    "/sessions/create-task",
    response_model=ApiResponse[Dict[str, Any]],
)
async def create_task_endpoint(
    request: CreateTaskRequest,
    auth_context: AuthContext = Depends(require_auth_context),
    service: ChatHistoryService = Depends(get_chat_history_service),
):
    """Create a new session promoted to a task with metadata."""

    if auth_context["customer_id"] != request.customer_id:
        raise HTTPException(status_code=403, detail="Access denied: customer ID mismatch")

    logger.info(
        "Creating task for customer_id=%s agent=%s priority=%s",
        request.customer_id,
        request.ai_character_name,
        request.task_priority,
    )

    return await execute_service_call(
        lambda: service.create_task(request),
        success_message="Task created successfully",
        formatter=lambda result: result.model_dump(),
    )


__all__ = [
    "create_task_endpoint",
    "list_sessions_endpoint",
    "remove_session_endpoint",
    "search_sessions_endpoint",
    "session_detail_endpoint",
    "update_session_endpoint",
]
