"""Lifestyle event ORM models related to Garmin integrations."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.db.base import Base


class DailyHealthEvents(Base):
    """Captures lifestyle timestamps such as meals, drinks, and screen time."""

    __tablename__ = "daily_health_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(Integer, index=True)
    calendar_date: Mapped[date] = mapped_column(Date, index=True)
    last_meal_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_drink_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_screen_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (UniqueConstraint("customer_id", "calendar_date", name="unique_customer_date"),)


__all__ = ["DailyHealthEvents"]
