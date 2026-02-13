"""Garmin training readiness and progression ORM models."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import Date, Float, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.db.base import Base


class TrainingReadiness(Base):
    """Captures Garmin daily training readiness assessment."""

    __tablename__ = "get_training_readiness"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(Integer, index=True)
    calendar_date: Mapped[date] = mapped_column(Date, index=True)
    training_readiness_level: Mapped[str | None] = mapped_column(String(50), nullable=True)
    training_readiness_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sleep_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sleep_score_factor_feedback: Mapped[str | None] = mapped_column(String(255), nullable=True)
    recovery_time_factor_feedback: Mapped[str | None] = mapped_column(String(255), nullable=True)
    recovery_time: Mapped[int | None] = mapped_column(Integer, nullable=True)
    acute_load: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hrv_weekly_average: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hrv_factor_feedback: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stress_history_factor_feedback: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sleep_history_factor_feedback: Mapped[str | None] = mapped_column(String(255), nullable=True)


class EnduranceScore(Base):
    """Tracks Garmin endurance scoring plus contributing factors."""

    __tablename__ = "get_endurance_score"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(Integer, index=True)
    calendar_date: Mapped[date] = mapped_column(Date, index=True)
    endurance_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    endurance_score_classification: Mapped[int | None] = mapped_column(Integer, nullable=True)
    endurance_score_classification_lower_limit_intermediate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    endurance_score_classification_lower_limit_trained: Mapped[int | None] = mapped_column(Integer, nullable=True)
    endurance_score_classification_lower_limit_well_trained: Mapped[int | None] = mapped_column(Integer, nullable=True)
    endurance_score_classification_lower_limit_expert: Mapped[int | None] = mapped_column(Integer, nullable=True)
    endurance_score_classification_lower_limit_superior: Mapped[int | None] = mapped_column(Integer, nullable=True)
    endurance_score_classification_lower_limit_elite: Mapped[int | None] = mapped_column(Integer, nullable=True)
    endurance_score_contributors: Mapped[Any | None] = mapped_column(JSON, nullable=True)


class TrainingStatus(Base):
    """Provides Garmin view of training load and related metrics."""

    __tablename__ = "get_training_status"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(Integer, index=True)
    calendar_date: Mapped[date] = mapped_column(Date, index=True)
    daily_training_load_acute: Mapped[int | None] = mapped_column(Integer, nullable=True)
    daily_training_load_acute_feedback: Mapped[str | None] = mapped_column(String(50), nullable=True)
    daily_training_load_chronic: Mapped[float | None] = mapped_column(Float, nullable=True)
    min_training_load_chronic: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_training_load_chronic: Mapped[float | None] = mapped_column(Float, nullable=True)
    vo2_max_precise_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    vo2_max_feedback: Mapped[str | None] = mapped_column(String(50), nullable=True)
    monthly_load_anaerobic: Mapped[float | None] = mapped_column(Float, nullable=True)
    monthly_load_aerobic_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    monthly_load_aerobic_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    monthly_load_aerobic_low_target_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    monthly_load_aerobic_low_target_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    monthly_load_aerobic_high_target_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    monthly_load_aerobic_high_target_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    monthly_load_anaerobic_target_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    monthly_load_anaerobic_target_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    training_balance_feedback_phrase: Mapped[str | None] = mapped_column(String(50), nullable=True)


class FitnessAge(Base):
    """Summarises Garmin fitness age relative to chronological age."""

    __tablename__ = "get_fitness_age"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(Integer, index=True)
    calendar_date: Mapped[date] = mapped_column(Date, index=True)
    chronological_age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fitness_age: Mapped[float | None] = mapped_column(Float, nullable=True)
    body_fat_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    vigorous_days_avg_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    rhr_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vigorous_minutes_avg_value: Mapped[float | None] = mapped_column(Float, nullable=True)


__all__ = [
    "TrainingReadiness",
    "EnduranceScore",
    "TrainingStatus",
    "FitnessAge",
]
