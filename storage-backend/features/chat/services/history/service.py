"""Composable chat history service exposing persistence operations."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from features.chat.schemas.requests import (
    AuthRequest,
    CreateMessageRequest,
    CreateTaskRequest,
    EditMessageRequest,
    FavoriteExportRequest,
    FileQueryRequest,
    PromptCreateRequest,
    PromptDeleteRequest,
    PromptListRequest,
    PromptUpdateRequest,
    RemoveMessagesRequest,
    RemoveSessionRequest,
    SessionDetailRequest,
    SessionListRequest,
    SessionSearchRequest,
    UpdateMessageRequest,
    UpdateSessionRequest,
)
from features.chat.schemas.responses import (
    AuthResult,
    FavoritesResult,
    FileQueryResult,
    MessageUpdateResult,
    MessageWritePayload,
    MessagesRemovedResult,
    PromptListResult,
    PromptRecord,
    SessionDetailResult,
    SessionListResult,
)

from .base import HistoryRepositories, build_repositories
from .messages import (
    create_message,
    edit_message,
    remove_messages,
    update_message,
)
from .misc import authenticate, get_favorites, query_files
from .prompts import add_prompt, delete_prompt, list_prompts, update_prompt
from .sessions import (
    create_task,
    fork_session_from_history,
    get_session,
    list_sessions,
    remove_session,
    search_sessions,
    update_session,
)


class ChatHistoryService:
    """Service layer responsible for chat persistence workflows."""

    def __init__(self, session: AsyncSession):
        self._session = session
        self._repositories = build_repositories(session)
        # Preserve legacy attributes for backwards compatibility.
        self._sessions = self._repositories.sessions
        self._messages = self._repositories.messages
        self._prompts = self._repositories.prompts
        self._users = self._repositories.users

    @property
    def repositories(self) -> HistoryRepositories:
        """Expose the repository bundle for helper functions."""

        return self._repositories

    async def create_message(
        self, request: CreateMessageRequest
    ) -> MessageWritePayload:
        return await create_message(self._repositories, request)

    async def edit_message(self, request: EditMessageRequest) -> MessageWritePayload:
        return await edit_message(self._repositories, request)

    async def update_message(self, request: UpdateMessageRequest) -> MessageUpdateResult:
        return await update_message(self._repositories, request)

    async def remove_messages(
        self, request: RemoveMessagesRequest
    ) -> MessagesRemovedResult:
        return await remove_messages(self._repositories, request)

    async def list_sessions(self, request: SessionListRequest) -> SessionListResult:
        return await list_sessions(self._repositories, request)

    async def get_session(self, request: SessionDetailRequest) -> SessionDetailResult:
        return await get_session(self._repositories, request)

    async def search_sessions(
        self, request: SessionSearchRequest
    ) -> SessionListResult:
        return await search_sessions(self._repositories, request)

    async def update_session(
        self, request: UpdateSessionRequest
    ) -> SessionDetailResult:
        return await update_session(self._repositories, request)

    async def remove_session(
        self, request: RemoveSessionRequest
    ) -> MessagesRemovedResult:
        return await remove_session(self._repositories, request)

    async def create_task(self, request: CreateTaskRequest) -> SessionDetailResult:
        return await create_task(self._repositories, request)

    async def list_prompts(self, request: PromptListRequest) -> PromptListResult:
        return await list_prompts(self._repositories, request)

    async def add_prompt(self, request: PromptCreateRequest) -> PromptRecord:
        return await add_prompt(self._repositories, request)

    async def update_prompt(self, request: PromptUpdateRequest) -> PromptRecord:
        return await update_prompt(self._repositories, request)

    async def delete_prompt(
        self, request: PromptDeleteRequest
    ) -> MessagesRemovedResult:
        return await delete_prompt(self._repositories, request)

    async def authenticate(self, request: AuthRequest) -> AuthResult:
        return await authenticate(self._repositories, request)

    async def get_favorites(
        self, request: FavoriteExportRequest
    ) -> FavoritesResult:
        return await get_favorites(self._repositories, request)

    async def query_files(self, request: FileQueryRequest) -> FileQueryResult:
        return await query_files(self._repositories, request)

    async def fork_session_from_history(
        self,
        customer_id: int,
        chat_history: list[dict],
        session_name: str = "New session from here",
        ai_character_name: str = "assistant",
        ai_text_gen_model: str | None = None,
        claude_code_data: dict | None = None,
    ) -> str:
        """Fork a session by creating a new session with historical messages."""
        return await fork_session_from_history(
            self._repositories,
            customer_id=customer_id,
            chat_history=chat_history,
            session_name=session_name,
            ai_character_name=ai_character_name,
            ai_text_gen_model=ai_text_gen_model,
            claude_code_data=claude_code_data,
        )

__all__ = [
    "ChatHistoryService",
]
