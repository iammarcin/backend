"""Daily Garmin summary and composition ORM models."""

from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.db.base import Base


class UserSummary(Base):
    """Aggregated daily Garmin metrics mirrored from ``get_user_summary``."""

    __tablename__ = "get_user_summary"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(Integer, index=True)
    calendar_date: Mapped[date] = mapped_column(Date, index=True)
    total_kilocalories: Mapped[float | None] = mapped_column(Float, nullable=True)
    active_kilocalories: Mapped[float | None] = mapped_column(Float, nullable=True)
    bmr_kilocalories: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_steps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_distance_meters: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_heart_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_heart_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resting_heart_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_seven_days_avg_resting_heart_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vigorous_intensity_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    moderate_intensity_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    average_stress_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_stress_duration: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stress_duration: Mapped[int | None] = mapped_column(Integer, nullable=True)
    uncategorized_stress_duration: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rest_stress_duration: Mapped[int | None] = mapped_column(Integer, nullable=True)
    low_stress_duration: Mapped[int | None] = mapped_column(Integer, nullable=True)
    activity_stress_duration: Mapped[int | None] = mapped_column(Integer, nullable=True)
    medium_stress_duration: Mapped[int | None] = mapped_column(Integer, nullable=True)
    high_stress_duration: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stress_qualifier: Mapped[str | None] = mapped_column(String(50), nullable=True)
    body_battery_charged_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    body_battery_drained_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    body_battery_highest_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    body_battery_lowest_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    body_battery_most_recent_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_waking_respiration_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    highest_respiration_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    lowest_respiration_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    latest_respiration_value: Mapped[float | None] = mapped_column(Float, nullable=True)


class BodyComposition(Base):
    """Daily body composition measurements from ``get_body_composition``."""

    __tablename__ = "get_body_composition"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(Integer, index=True)
    calendar_date: Mapped[date] = mapped_column(Date, index=True)
    weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    bmi: Mapped[float | None] = mapped_column(Float, nullable=True)
    body_fat_mass: Mapped[float | None] = mapped_column(Float, nullable=True)
    body_fat_percentage: Mapped[float | None] = mapped_column(Float, nullable=True)
    body_water_mass: Mapped[float | None] = mapped_column(Float, nullable=True)
    body_water_percentage: Mapped[float | None] = mapped_column(Float, nullable=True)
    bone_mass: Mapped[float | None] = mapped_column(Float, nullable=True)
    bone_mass_percentage: Mapped[float | None] = mapped_column(Float, nullable=True)
    muscle_mass: Mapped[float | None] = mapped_column(Float, nullable=True)
    muscle_mass_percentage: Mapped[float | None] = mapped_column(Float, nullable=True)
    visceral_fat: Mapped[float | None] = mapped_column(Float, nullable=True)
    basal_metabolic_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)


class HRVData(Base):
    """Heart-rate variability metrics sourced from ``get_hrv_data``."""

    __tablename__ = "get_hrv_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(Integer, index=True)
    calendar_date: Mapped[date] = mapped_column(Date, index=True)
    hrv_weekly_avg: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hrv_last_night_avg: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hrv_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    hrv_baseline_balanced_low: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hrv_baseline_balanced_upper: Mapped[int | None] = mapped_column(Integer, nullable=True)


__all__ = ["UserSummary", "BodyComposition", "HRVData"]
