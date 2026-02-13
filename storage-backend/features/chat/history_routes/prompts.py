"""Endpoints that manage saved prompt definitions."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import Depends, HTTPException, Query

from core.auth import AuthContext, require_auth_context
from core.pydantic_schemas import ApiResponse
from features.chat.dependencies import get_chat_history_service
from features.chat.schemas.requests import (
    PromptCreateRequest,
    PromptDeleteRequest,
    PromptListRequest,
    PromptUpdateRequest,
)
from features.chat.schemas.responses import PromptListResult, PromptRecord
from features.chat.service import ChatHistoryService

from .shared import execute_service_call, history_router


@history_router.get(
    "/prompts",
    response_model=ApiResponse[PromptListResult],
)
async def list_prompts_endpoint(
    customer_id: int = Query(..., ge=1),
    auth_context: AuthContext = Depends(require_auth_context),
    service: ChatHistoryService = Depends(get_chat_history_service),
):
    """Return saved prompts for the provided customer identifier."""

    if auth_context["customer_id"] != customer_id:
        raise HTTPException(status_code=403, detail="Access denied: customer ID mismatch")

    request = PromptListRequest(customer_id=customer_id)
    return await execute_service_call(
        lambda: service.list_prompts(request),
        success_message="Prompts retrieved successfully",
        formatter=lambda result: result.model_dump(by_alias=True, exclude_none=True),
    )


@history_router.post(
    "/prompts",
    response_model=ApiResponse[PromptRecord],
)
async def create_prompt_endpoint(
    request: PromptCreateRequest,
    auth_context: AuthContext = Depends(require_auth_context),
    service: ChatHistoryService = Depends(get_chat_history_service),
):
    """Create a reusable prompt template for the active customer."""

    if auth_context["customer_id"] != request.customer_id:
        raise HTTPException(status_code=403, detail="Access denied: customer ID mismatch")

    return await execute_service_call(
        lambda: service.add_prompt(request),
        success_message="Prompt created successfully",
        formatter=lambda result: result.model_dump(by_alias=True, exclude_none=True),
    )


@history_router.put(
    "/prompts",
    response_model=ApiResponse[PromptRecord],
)
async def update_prompt_endpoint(
    request: PromptUpdateRequest,
    auth_context: AuthContext = Depends(require_auth_context),
    service: ChatHistoryService = Depends(get_chat_history_service),
):
    """Update an existing saved prompt with the supplied payload."""

    if auth_context["customer_id"] != request.customer_id:
        raise HTTPException(status_code=403, detail="Access denied: customer ID mismatch")

    return await execute_service_call(
        lambda: service.update_prompt(request),
        success_message="Prompt updated successfully",
        formatter=lambda result: result.model_dump(by_alias=True, exclude_none=True),
    )


@history_router.delete(
    "/prompts",
    response_model=ApiResponse[Dict[str, Any]],
)
async def delete_prompt_endpoint(
    request: PromptDeleteRequest,
    auth_context: AuthContext = Depends(require_auth_context),
    service: ChatHistoryService = Depends(get_chat_history_service),
):
    """Remove a prompt definition from the customer's library."""

    if auth_context["customer_id"] != request.customer_id:
        raise HTTPException(status_code=403, detail="Access denied: customer ID mismatch")

    return await execute_service_call(
        lambda: service.delete_prompt(request),
        success_message="Prompt removed successfully",
        formatter=lambda result: result.model_dump(by_alias=True, exclude_none=True),
    )


__all__ = [
    "create_prompt_endpoint",
    "delete_prompt_endpoint",
    "list_prompts_endpoint",
    "update_prompt_endpoint",
]
