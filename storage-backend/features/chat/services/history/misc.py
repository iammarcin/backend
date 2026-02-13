"""Authentication and file-query helpers for chat history workflows."""

from __future__ import annotations

from core.auth import create_auth_token
from features.chat.schemas.requests import (
    AuthRequest,
    FavoriteExportRequest,
    FileQueryRequest,
)
from features.chat.schemas.responses import (
    AuthResult,
    FavoritesResult,
    FileQueryResult,
    ChatMessagePayload,
    ChatSessionPayload,
)

from .base import HistoryRepositories


async def authenticate(
    repositories: HistoryRepositories, request: AuthRequest
) -> AuthResult:
    """Validate user credentials and return auth token."""

    user = await repositories.users.verify_credentials(
        customer_id=request.customer_id,
        username=request.username,
        password=request.password,
    )

    # Generate JWT token for authenticated user
    token = create_auth_token(
        customer_id=user.customer_id,
        email=user.email,
    )

    return AuthResult(
        customer_id=user.customer_id,
        username=user.username,
        email=user.email,
        token=token,
    )


async def get_favorites(
    repositories: HistoryRepositories, request: FavoriteExportRequest
) -> FavoritesResult:
    """Fetch the user's favourite conversation."""

    favourites = await repositories.messages.fetch_favorites(
        customer_id=request.customer_id
    )
    if not favourites:
        return FavoritesResult(session=None)
    session_payload = ChatSessionPayload.model_validate(favourites)
    return FavoritesResult(session=session_payload)


async def query_files(
    repositories: HistoryRepositories, request: FileQueryRequest
) -> FileQueryResult:
    """Return messages that have files attached."""

    messages = await repositories.messages.fetch_messages_with_files(
        customer_id=request.customer_id,
        older_then_date=request.older_then_date,
        younger_then_date=request.younger_then_date,
        exact_filename=request.exact_filename,
        ai_only=request.ai_only,
        offset=request.offset,
        limit=request.limit,
        file_extension=request.file_extension,
        check_image_locations=request.check_image_locations,
    )
    items = [ChatMessagePayload.model_validate(message) for message in messages]
    return FileQueryResult(messages=items)
