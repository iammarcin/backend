"""SQLAlchemy models for semantic search domain."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from infrastructure.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class SessionSummary(Base):
    """Session-level summaries for semantic search."""

    __tablename__ = "session_summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("ChatSessionsNG.session_id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    customer_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    summary: Mapped[str] = mapped_column(Text, nullable=False)
    key_topics: Mapped[list[str] | None] = mapped_column(JSON, nullable=True, default=list)
    main_entities: Mapped[list[str] | None] = mapped_column(JSON, nullable=True, default=list)

    message_count: Mapped[int] = mapped_column(Integer, nullable=False)
    first_message_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_message_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    tags: Mapped[list[str] | None] = mapped_column(JSON, nullable=True, default=list)

    summary_model: Mapped[str] = mapped_column(String(100), nullable=False)
    summary_config_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )

    session: Mapped["features.chat.db_models.ChatSession"] = relationship(
        "ChatSession",
        backref="summary",
        lazy="joined",
    )

    def __repr__(self) -> str:
        return f"<SessionSummary(session_id={self.session_id}, customer_id={self.customer_id})>"


__all__ = ["SessionSummary"]
