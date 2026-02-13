"""SQLAlchemy ORM models for the chat domain."""

from __future__ import annotations
from infrastructure.db.base import Base

from datetime import UTC, datetime
from typing import Any, Dict, List, Optional
from uuid import UUID as PyUUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    """Return a timezone-aware UTC timestamp for ORM defaults."""

    return datetime.now(UTC)


class ChatGroup(Base):
    """Represents a multi-agent group chat configuration."""

    __tablename__ = "chat_groups"

    id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("Users.customer_id"),
        nullable=False,
        index=True,
    )
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mode: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    leader_agent: Mapped[str] = mapped_column(String(50), default="sherlock")
    context_window_size: Mapped[int] = mapped_column(Integer, default=6)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
        onupdate=_utcnow,
    )

    # Relationships
    members: Mapped[list["ChatGroupMember"]] = relationship(
        "ChatGroupMember",
        back_populates="group",
        cascade="all, delete-orphan",
        order_by="ChatGroupMember.position",
    )
    sessions: Mapped[list["ChatSession"]] = relationship(
        "ChatSession",
        back_populates="group",
    )
    user: Mapped["User"] = relationship("User", back_populates="groups")

    __table_args__ = (
        CheckConstraint("mode IN ('sequential', 'leader_listeners', 'explicit')", name="check_mode_valid"),
        CheckConstraint("context_window_size >= 3 AND context_window_size <= 10", name="check_context_window"),
    )


class ChatGroupMember(Base):
    """Represents a member (agent) in a chat group."""

    __tablename__ = "chat_group_members"

    group_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_groups.id", ondelete="CASCADE"),
        primary_key=True,
    )
    agent_name: Mapped[str] = mapped_column(String(50), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    last_response_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )

    # Relationship
    group: Mapped["ChatGroup"] = relationship("ChatGroup", back_populates="members")


class ChatSession(Base):
    """Represents a conversational session for a specific customer."""

    __tablename__ = "ChatSessionsNG"

    session_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        index=True,
    )
    customer_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("Users.customer_id"),
        index=True,
        nullable=False,
    )
    session_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ai_character_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ai_text_gen_model: Mapped[str | None] = mapped_column(String(50), nullable=True)
    auto_trigger_tts: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    claude_session_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(JSON, nullable=True, default=list)
    group_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_groups.id"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )
    last_update: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )
    task_status: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        default=None,
        index=True,
    )
    task_priority: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        default=None,
    )
    task_description: Mapped[str | None] = mapped_column(
        String(500), nullable=True, default=None
    )

    customer: Mapped["User"] = relationship("User", back_populates="sessions")
    group: Mapped["ChatGroup | None"] = relationship("ChatGroup", back_populates="sessions")
    messages: Mapped[list["ChatMessage"]] = relationship(
        "ChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by=lambda: (ChatMessage.created_at, ChatMessage.message_id),
    )

    __table_args__ = (
        Index("idx_agent_task", "ai_character_name", "task_status"),
    )


class ChatMessage(Base):
    """Stores every message exchanged in a chat session."""

    __tablename__ = "ChatMessagesNG"

    message_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("ChatSessionsNG.session_id"),
        index=True,
        nullable=False,
    )
    customer_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("Users.customer_id"),
        index=True,
        nullable=False,
    )
    sender: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_locations: Mapped[list[str] | None] = mapped_column(JSON, nullable=True, default=list)
    image_description: Mapped[str | None] = mapped_column("image_description", Text, nullable=True)
    file_locations: Mapped[list[str] | None] = mapped_column(JSON, nullable=True, default=list)
    chart_data: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True)
    ai_character_name: Mapped[str | None] = mapped_column("ai_character_name", Text, nullable=True)
    is_tts: Mapped[bool] = mapped_column("is_tts", Boolean, nullable=False, default=False)
    api_text_gen_model_name: Mapped[str | None] = mapped_column("api_text_gen_model_name", Text, nullable=True)
    api_text_gen_settings: Mapped[dict[str, Any] | None] = mapped_column("api_text_gen_settings", JSON, nullable=True, default=dict)
    api_tts_gen_model_name: Mapped[str | None] = mapped_column("api_tts_gen_model_name", Text, nullable=True)
    api_image_gen_settings: Mapped[dict[str, Any] | None] = mapped_column("api_image_gen_settings", JSON, nullable=True, default=dict)
    image_generation_request: Mapped[dict[str, Any] | None] = mapped_column("image_generation_request", JSON, nullable=True, default=dict)
    claude_code_data: Mapped[dict[str, Any] | None] = mapped_column("claude_code_data", JSON, nullable=True, default=dict)
    is_gps_location_message: Mapped[bool] = mapped_column("is_gps_location_message", Boolean, nullable=False, default=False)
    show_transcribe_button: Mapped[bool] = mapped_column("show_transcribe_button", Boolean, nullable=False, default=False)
    favorite: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    test_mode: Mapped[bool] = mapped_column("test_mode", Boolean, nullable=False, default=False)
    responding_agent: Mapped[str | None] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )

    session: Mapped[ChatSession] = relationship("ChatSession", back_populates="messages")
    customer: Mapped["User"] = relationship("User", back_populates="messages")


# Ensure group chat request models are registered with SQLAlchemy metadata.
from features.chat.group_request_models import GroupChatRequest, GroupChatAgentRequest  # noqa: E402,F401


class Prompt(Base):
    """Represents a saved reusable prompt for a customer."""

    __tablename__ = "Prompts"

    prompt_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    customer_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("Users.customer_id"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)

    customer: Mapped["User"] = relationship("User", back_populates="prompts")


class User(Base):
    """Represents an authenticated customer account."""

    __tablename__ = "Users"

    customer_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False)
    password: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )

    sessions: Mapped[list[ChatSession]] = relationship("ChatSession", back_populates="customer")
    messages: Mapped[list[ChatMessage]] = relationship("ChatMessage", back_populates="customer")
    prompts: Mapped[list[Prompt]] = relationship("Prompt", back_populates="customer")
    groups: Mapped[list[ChatGroup]] = relationship("ChatGroup", back_populates="user")


__all__ = ["ChatGroup", "ChatGroupMember", "ChatMessage", "ChatSession", "Prompt", "User"]
