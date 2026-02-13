"""Garmin activity metadata and GPS stream ORM models."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import BigInteger, Date, Float, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.db.base import Base


class ActivityData(Base):
    """Represents a single Garmin activity summary row."""

    __tablename__ = "get_activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(Integer, index=True)
    calendar_date: Mapped[date] = mapped_column(Date, index=True)
    activity_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    activity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    activity_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    activity_description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    activity_start_time: Mapped[str | None] = mapped_column(String(5), nullable=True)
    activity_start_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    activity_start_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    activity_end_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    activity_end_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    activity_location_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    activity_duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    activity_elapsed_duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    activity_moving_duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    activity_distance: Mapped[float | None] = mapped_column(Float, nullable=True)
    activity_elevation_gain: Mapped[float | None] = mapped_column(Float, nullable=True)
    activity_elevation_loss: Mapped[float | None] = mapped_column(Float, nullable=True)
    activity_min_elevation: Mapped[float | None] = mapped_column(Float, nullable=True)
    activity_max_elevation: Mapped[float | None] = mapped_column(Float, nullable=True)
    activity_calories: Mapped[float | None] = mapped_column(Float, nullable=True)
    activity_bmr_calories: Mapped[float | None] = mapped_column(Float, nullable=True)
    activity_steps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    activity_avgStrideLength: Mapped[float | None] = mapped_column(Float, nullable=True)
    activity_average_speed: Mapped[float | None] = mapped_column(Float, nullable=True)
    activity_average_hr: Mapped[float | None] = mapped_column(Float, nullable=True)
    activity_max_hr: Mapped[float | None] = mapped_column(Float, nullable=True)
    activity_watch_min_temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    activity_watch_max_temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    activity_weather_temperature_on_start: Mapped[float | None] = mapped_column(Float, nullable=True)
    activity_weather_relative_humidity_on_start: Mapped[float | None] = mapped_column(Float, nullable=True)
    activity_weather_wind_direction_on_start: Mapped[str | None] = mapped_column(String(10), nullable=True)
    activity_weather_wind_speed_on_start: Mapped[float | None] = mapped_column(Float, nullable=True)
    activity_weather_wind_gust_on_start: Mapped[float | None] = mapped_column(Float, nullable=True)
    activity_weather_type_desc: Mapped[str | None] = mapped_column(String(50), nullable=True)
    activity_water_estimated: Mapped[float | None] = mapped_column(Float, nullable=True)
    activity_aerobic_training_effect: Mapped[float | None] = mapped_column(Float, nullable=True)
    activity_anaerobic_training_effect: Mapped[float | None] = mapped_column(Float, nullable=True)
    activity_activity_training_load: Mapped[float | None] = mapped_column(Float, nullable=True)
    activity_training_effect_label: Mapped[str | None] = mapped_column(String(50), nullable=True)
    activity_aerobic_training_effect_message: Mapped[str | None] = mapped_column(String(255), nullable=True)
    activity_anaerobic_training_effect_message: Mapped[str | None] = mapped_column(String(255), nullable=True)
    activity_moderate_intensity_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    activity_vigorous_intensity_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    activity_difference_body_battery: Mapped[int | None] = mapped_column(Integer, nullable=True)
    activity_secs_in_zone1: Mapped[float | None] = mapped_column(Float, nullable=True)
    activity_secs_in_zone2: Mapped[float | None] = mapped_column(Float, nullable=True)
    activity_secs_in_zone3: Mapped[float | None] = mapped_column(Float, nullable=True)
    activity_secs_in_zone4: Mapped[float | None] = mapped_column(Float, nullable=True)
    activity_secs_in_zone5: Mapped[float | None] = mapped_column(Float, nullable=True)


class ActivityGPSData(Base):
    """Stores raw GPS samples for a Garmin activity."""

    __tablename__ = "get_activity_gps_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    activity_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    customer_id: Mapped[int] = mapped_column(Integer, index=True)
    calendar_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    activity_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    gps_data: Mapped[Any | None] = mapped_column(JSON, nullable=True)


__all__ = ["ActivityData", "ActivityGPSData"]
