"""
Legacy API endpoints for database and file upload operations.

These endpoints use the original /api/db and /api/aws paths for historical reasons,
but accept the canonical snake_case field names like all other endpoints.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DatabaseError, OperationalError

from core.auth import AuthenticationError, authenticate_bearer_token
from core.exceptions import ValidationError
from features.chat.dependencies import get_chat_history_service
from features.chat.service import ChatHistoryService
from features.storage.dependencies import get_storage_service
from infrastructure.aws.storage import StorageService

from .aws_handlers import handle_aws_upload
from .case_converters import camel_to_snake, deep_convert_keys
from .db_handlers import (
    handle_db_all_sessions_for_user,
    handle_db_get_user_session,
    handle_db_new_message,
    handle_db_search_messages,
)
from .response_helpers import legacy_error_response

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Legacy Compatibility"])


@router.post("/api/db")
async def legacy_db_endpoint(
    request: Request,
    service: ChatHistoryService = Depends(get_chat_history_service),
) -> JSONResponse:
    """
    Legacy database endpoint that accepts old mobile app format.

    Handles actions like:
    - db_search_messages: Search/list chat sessions
    - db_get_user_session: Get specific session with messages
    - db_new_message: Create new message in a session
    """
    # Validate JWT and extract customer_id from token
    try:
        auth_context = authenticate_bearer_token(
            authorization=request.headers.get("authorization"),
        )
        customer_id = auth_context["customer_id"]
    except AuthenticationError as exc:
        logger.warning("Legacy DB request auth failed: %s", exc.reason)
        return legacy_error_response(exc.message, 401)

    # Parse request body
    try:
        body = await request.json()
    except Exception as e:
        logger.error(f"Failed to parse legacy DB request body: {e}")
        return legacy_error_response("Invalid request body", 400)

    # Convert camelCase keys to snake_case for legacy Android app compatibility
    body = deep_convert_keys(body, camel_to_snake)

    # Extract request parameters (canonical snake_case)
    action = body.get("action")
    user_input = body.get("user_input", {})
    user_settings = body.get("user_settings", {})

    logger.info(f"Legacy DB request: action={action}, customer_id={customer_id}")

    # Route to appropriate handler
    try:
        if action == "db_search_messages":
            return await handle_db_search_messages(customer_id, user_input, service)

        elif action == "db_all_sessions_for_user":
            return await handle_db_all_sessions_for_user(customer_id, user_input, service)

        elif action == "db_get_user_session":
            return await handle_db_get_user_session(customer_id, user_input, service)

        elif action == "db_new_message":
            return await handle_db_new_message(customer_id, user_input, user_settings, service)

        else:
            logger.warning(f"Unsupported legacy DB action: {action}")
            return legacy_error_response(f"Unsupported action: {action}", 400)

    except ValidationError as val_exc:
        logger.warning(
            "Legacy request validation error (action=%s, customer=%s): %s",
            action,
            customer_id,
            val_exc,
        )
        return legacy_error_response(str(val_exc), 400)

    except (OperationalError, DatabaseError) as db_exc:
        logger.error(
            "Database connection error for legacy request (action=%s, customer=%s): %s",
            action,
            customer_id,
            db_exc,
            exc_info=True,
        )
        return legacy_error_response(
            "Database temporarily unavailable. Please try again later.",
            503,
        )

    except Exception as e:
        logger.error(
            "Unexpected error processing legacy DB request: %s",
            e,
            exc_info=True,
        )
        return legacy_error_response("An error occurred processing your request", 500)


@router.post("/api/aws")
async def legacy_aws_upload_endpoint(
    request: Request,
    storage: StorageService = Depends(get_storage_service),
) -> JSONResponse:
    """
    File upload endpoint at legacy /api/aws path.

    Handles file uploads (images, audio, etc.) and stores them in S3.
    Accepts both camelCase and snake_case form field names for legacy Android compatibility.
    """
    # Validate JWT and extract customer_id from token
    try:
        auth_context = authenticate_bearer_token(
            authorization=request.headers.get("authorization"),
        )
        customer_id = auth_context["customer_id"]
    except AuthenticationError as exc:
        logger.warning("Legacy AWS request auth failed: %s", exc.reason)
        return legacy_error_response(exc.message, 401)

    form = await request.form()

    # Helper to get field by either snake_case or camelCase
    def get_field(snake: str, camel: str, default=None):
        return form.get(snake) or form.get(camel) or default

    action = get_field("action", "action", "")
    category = get_field("category", "category", "")
    user_input = get_field("user_input", "userInput", "")
    file = form.get("file")

    # Validate file presence
    if not file or not hasattr(file, "read"):
        return legacy_error_response("No file uploaded", 400)

    return await handle_aws_upload(
        action=action,
        category=category,
        user_input=user_input,
        customer_id=customer_id,
        file=file,
        storage=storage,
    )


__all__ = ["router"]
