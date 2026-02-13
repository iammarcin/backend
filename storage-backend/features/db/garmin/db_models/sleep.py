"""Sleep-specific Garmin ORM models."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import Date, Float, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.db.base import Base


class SleepData(Base):
    """Represents one night of Garmin sleep analytics for a customer."""

    __tablename__ = "get_sleep_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(Integer, index=True)
    calendar_date: Mapped[date] = mapped_column(Date, index=True)
    time_offset: Mapped[str | None] = mapped_column(Text, nullable=True)
    sleep_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sleep_start: Mapped[str | None] = mapped_column(String(5), nullable=True)
    sleep_end: Mapped[str | None] = mapped_column(String(5), nullable=True)
    sleep_start_gmt: Mapped[str | None] = mapped_column(String(5), nullable=True)
    sleep_end_gmt: Mapped[str | None] = mapped_column(String(5), nullable=True)
    nap_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    nap_data: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    deep_sleep_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    light_sleep_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rem_sleep_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    awake_sleep_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sleep_average_respiration_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    sleep_lowest_respiration_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    sleep_highest_respiration_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    sleep_awake_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_sleep_stress: Mapped[float | None] = mapped_column(Float, nullable=True)
    sleep_score_feedback: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sleep_score_insight: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sleep_score_personalized_insight: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sleep_overall_score_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sleep_overall_score_qualifier: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sleep_total_duration_qualifier: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sleep_stress_qualifier: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sleep_awake_count_qualifier: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sleep_rem_percentage_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sleep_rem_percentage_qualifier: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sleep_rem_optimal_start: Mapped[float | None] = mapped_column(Float, nullable=True)
    sleep_rem_optimal_end: Mapped[float | None] = mapped_column(Float, nullable=True)
    sleep_restlessness_qualifier: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sleep_restlessness_optimal_start: Mapped[float | None] = mapped_column(Float, nullable=True)
    sleep_restlessness_optimal_end: Mapped[float | None] = mapped_column(Float, nullable=True)
    sleep_light_percentage_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sleep_light_percentage_qualifier: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sleep_light_optimal_start: Mapped[float | None] = mapped_column(Float, nullable=True)
    sleep_light_optimal_end: Mapped[float | None] = mapped_column(Float, nullable=True)
    sleep_deep_percentage_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sleep_deep_percentage_qualifier: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sleep_deep_optimal_start: Mapped[float | None] = mapped_column(Float, nullable=True)
    sleep_deep_optimal_end: Mapped[float | None] = mapped_column(Float, nullable=True)
    sleep_avg_overnight_hrv: Mapped[float | None] = mapped_column(Float, nullable=True)
    sleep_resting_heart_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sleep_body_battery_change: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sleep_restless_moments_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sleep_levels_data: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    sleep_heart_rate_data: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    sleep_hrv_data: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    sleep_stress_data: Mapped[Any | None] = mapped_column(JSON, nullable=True)


__all__ = ["SleepData"]
