"""Authentication endpoints for the legacy chat history flow."""

from __future__ import annotations

from fastapi import Depends

from core.pydantic_schemas import ApiResponse
from features.chat.dependencies import get_chat_history_service
from features.chat.schemas.requests import AuthRequest
from features.chat.schemas.responses import AuthResult
from features.chat.service import ChatHistoryService

from .shared import execute_service_call, history_router


@history_router.post(
    "/auth/login",
    response_model=ApiResponse[AuthResult],
)
async def auth_login_endpoint(
    request: AuthRequest,
    service: ChatHistoryService = Depends(get_chat_history_service),
):
    """Authenticate a customer account using the legacy credential flow."""

    return await execute_service_call(
        lambda: service.authenticate(request),
        success_message="Authentication successful",
        formatter=lambda result: result.model_dump(by_alias=True, exclude_none=True),
    )


__all__ = ["auth_login_endpoint"]

