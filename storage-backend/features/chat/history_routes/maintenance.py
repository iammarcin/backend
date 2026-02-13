"""Endpoints used by maintenance tooling for favorites and file queries."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import Depends, HTTPException, Query

from core.auth import AuthContext, require_auth_context
from core.pydantic_schemas import ApiResponse
from features.chat.dependencies import get_chat_history_service
from features.chat.schemas.requests import FavoriteExportRequest, FileQueryRequest
from features.chat.schemas.responses import FileQueryResult
from features.chat.service import ChatHistoryService

from .shared import execute_service_call, history_router


@history_router.get(
    "/maintenance/favorites",
    response_model=ApiResponse[Dict[str, Any]],
)
async def favorites_endpoint(
    customer_id: int = Query(..., ge=1),
    include_session_metadata: bool = Query(True),
    auth_context: AuthContext = Depends(require_auth_context),
    service: ChatHistoryService = Depends(get_chat_history_service),
):
    """Return exported favorites for the UI maintenance workflows."""

    if auth_context["customer_id"] != customer_id:
        raise HTTPException(status_code=403, detail="Access denied: customer ID mismatch")

    request = FavoriteExportRequest(
        customer_id=customer_id,
        include_session_metadata=include_session_metadata,
    )
    return await execute_service_call(
        lambda: service.get_favorites(request),
        success_message="Favorites retrieved successfully",
        formatter=lambda result: result.model_dump(),
    )


@history_router.post(
    "/maintenance/files",
    response_model=ApiResponse[FileQueryResult],
)
async def files_endpoint(
    request: FileQueryRequest,
    auth_context: AuthContext = Depends(require_auth_context),
    service: ChatHistoryService = Depends(get_chat_history_service),
):
    """Fetch messages that reference uploaded files for housekeeping views."""

    if auth_context["customer_id"] != request.customer_id:
        raise HTTPException(status_code=403, detail="Access denied: customer ID mismatch")

    return await execute_service_call(
        lambda: service.query_files(request),
        success_message="Messages with files retrieved successfully",
        formatter=lambda result: result.model_dump(by_alias=True, exclude_none=True),
    )


__all__ = ["favorites_endpoint", "files_endpoint"]
