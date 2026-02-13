"""SQLAlchemy ORM models for group chat request correlation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import List, Optional
from uuid import UUID as PyUUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from infrastructure.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class GroupChatRequest(Base):
    """Tracks a group chat user message that requires agent responses."""

    __tablename__ = "group_chat_requests"

    id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    group_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    group_session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("ChatSessionsNG.session_id"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    user_message_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("ChatMessagesNG.message_id", ondelete="SET NULL"),
        nullable=True,
    )
    mode: Mapped[str] = mapped_column(String(50), nullable=False)
    mentioned_agents: Mapped[List[str] | None] = mapped_column(
        JSON, nullable=True, default=list
    )
    target_agents: Mapped[List[str] | None] = mapped_column(
        JSON, nullable=True, default=list
    )
    next_agent_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
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

    agent_requests: Mapped[list["GroupChatAgentRequest"]] = relationship(
        "GroupChatAgentRequest",
        back_populates="group_request",
        cascade="all, delete-orphan",
        order_by="GroupChatAgentRequest.created_at",
    )


class GroupChatAgentRequest(Base):
    """Tracks a single agent response awaiting a proactive stream end."""

    __tablename__ = "group_chat_agent_requests"

    id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    group_request_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("group_chat_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    proactive_session_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    agent_name: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    group_request: Mapped[GroupChatRequest] = relationship(
        "GroupChatRequest",
        back_populates="agent_requests",
    )


__all__ = ["GroupChatRequest", "GroupChatAgentRequest"]
