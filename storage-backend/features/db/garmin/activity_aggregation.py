"""Utilities for condensing Garmin activity payloads into daily summaries.

The helpers in this module reshape the verbose records returned by Garmin's
database procedures into day-focused objects.  These outputs are convenient for
serialisation and form the basis for the insights displayed in the product UI.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, DefaultDict, Dict, List, Mapping, Sequence

CATEGORY_MAPPINGS: Dict[str, Dict[str, Any]] = {
    "sleep": {
        "tables": ["get_sleep_data"],
        "columns": [
            "calendar_date",
            "sleep_time_seconds",
            "sleep_start",
            "sleep_end",
            "nap_time_seconds",
            "deep_sleep_seconds",
            "light_sleep_seconds",
            "rem_sleep_seconds",
            "awake_sleep_seconds",
            "sleep_average_respiration_value",
            "sleep_awake_count",
            "avg_sleep_stress",
            "sleep_score_feedback",
            "sleep_overall_score_value",
            "sleep_overall_score_qualifier",
            "sleep_stress_qualifier",
            "sleep_rem_percentage_value",
            "sleep_light_percentage_value",
            "sleep_deep_percentage_value",
            "sleep_avg_overnight_hrv",
            "sleep_resting_heart_rate",
            "sleep_body_battery_change",
            "sleep_restless_moments_count",
        ],
    },
    "health": {
        "tables": ["get_user_summary", "get_body_composition", "get_hrv_data"],
        "columns": {
            "get_user_summary": [
                "calendar_date",
                "high_stress_duration",
                "medium_stress_duration",
                "low_stress_duration",
                "rest_stress_duration",
                "activity_stress_duration",
                "uncategorized_stress_duration",
                "average_stress_level",
                "body_battery_highest_value",
                "body_battery_lowest_value",
                "body_battery_drained_value",
            ],
            "get_body_composition": [
                "calendar_date",
                "weight",
                "bmi",
                "body_fat_percentage",
                "body_water_percentage",
                "muscle_mass_percentage",
                "visceral_fat",
                "basal_metabolic_rate",
            ],
            "get_hrv_data": [
                "calendar_date",
                "hrv_weekly_avg",
                "hrv_last_night_avg",
                "hrv_baseline_balanced_low",
                "hrv_baseline_balanced_upper",
            ],
        },
    },
    "training": {
        "tables": [
            "get_training_readiness",
            "get_endurance_score",
            "get_training_status",
            "get_fitness_age",
            "get_activities",
            "get_activity_gps_data",
        ],
        "columns": {
            "get_training_readiness": ["calendar_date", "training_readiness_score"],
            "get_endurance_score": ["calendar_date", "endurance_score"],
            "get_training_status": [
                "calendar_date",
                "daily_training_load_acute",
                "monthly_load_anaerobic",
                "monthly_load_aerobic_high",
                "monthly_load_aerobic_low",
                "vo2_max_precise_value",
            ],
            "get_fitness_age": ["calendar_date"],
            "get_activities": [
                "calendar_date",
                "activity_type",
                "activity_distance",
                "activity_duration",
                "activity_secs_in_zone5",
                "activity_secs_in_zone4",
                "activity_secs_in_zone3",
                "activity_secs_in_zone2",
                "activity_secs_in_zone1",
            ],
            "get_activity_gps_data": ["calendar_date"],
        },
    },
}


def optimize_health_data(
    data: Mapping[str, Sequence[Mapping[str, Any]]]
) -> List[Dict[str, Any]]:
    """Normalise Garmin health data into day-indexed structures.

    Parameters
    ----------
    data:
        Mapping where keys are table names (for example ``"get_sleep_data"``)
        and values are sequences of row dictionaries sourced from the legacy
        database helpers.

    Returns
    -------
    list of dict
        A list sorted by calendar date containing merged category payloads,
        suitable for serialising to JSON or passing to analytics routines.
    """

    categorized_data: DefaultDict[str, DefaultDict[str, Dict[str, Any]]] = defaultdict(
        lambda: defaultdict(dict)
    )

    for category, config in CATEGORY_MAPPINGS.items():
        for table_name in config["tables"]:
            if table_name not in data:
                continue

            records = data.get(table_name) or []
            if table_name == "get_activities":
                activities_by_date = process_activities(records)
                for calendar_date, activity_data in activities_by_date.items():
                    categorized_data[calendar_date][category].update(activity_data)
                continue

            columns_to_keep = (
                config["columns"].get(table_name, [])
                if isinstance(config["columns"], dict)
                else config["columns"]
            )

            for record in records:
                calendar_date = record.get("calendar_date")
                if not calendar_date:
                    continue
                for column in columns_to_keep:
                    if column == "calendar_date":
                        continue
                    if column not in record:
                        continue
                    value = record.get(column)
                    if value is None:
                        continue
                    categorized_data[calendar_date][category][column] = value

    merged: List[Dict[str, Any]] = []
    for calendar_date in sorted(categorized_data.keys()):
        merged.append({"date": calendar_date, **categorized_data[calendar_date]})

    return merged


def process_activities(activities: Sequence[Mapping[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Aggregate per-activity rows into per-day summaries.

    Each activity row is expected to contain a ``calendar_date`` key. Numeric
    fields are summed and rounded while ``activity_type`` values are collected
    into a list preserving duplicates.
    """

    daily_totals: DefaultDict[str, Dict[str, Any]] = defaultdict(
        lambda: {
            "activity_type": [],
            "activity_distance": 0.0,
            "activity_duration": 0.0,
            "activity_secs_in_zone1": 0.0,
            "activity_secs_in_zone2": 0.0,
            "activity_secs_in_zone3": 0.0,
            "activity_secs_in_zone4": 0.0,
            "activity_secs_in_zone5": 0.0,
        }
    )

    for record in activities:
        calendar_date = record.get("calendar_date")
        if not calendar_date:
            continue
        entry = daily_totals[calendar_date]
        activity_type = record.get("activity_type")
        if activity_type:
            entry["activity_type"].append(activity_type)
        for key in [
            "activity_distance",
            "activity_duration",
            "activity_secs_in_zone1",
            "activity_secs_in_zone2",
            "activity_secs_in_zone3",
            "activity_secs_in_zone4",
            "activity_secs_in_zone5",
        ]:
            value = record.get(key)
            if value is None:
                continue
            entry[key] += float(value)

    for entry in daily_totals.values():
        for key in [
            "activity_distance",
            "activity_duration",
            "activity_secs_in_zone1",
            "activity_secs_in_zone2",
            "activity_secs_in_zone3",
            "activity_secs_in_zone4",
            "activity_secs_in_zone5",
        ]:
            entry[key] = round(entry[key], 2)

    return {date_key: dict(values) for date_key, values in daily_totals.items()}


__all__ = ["CATEGORY_MAPPINGS", "optimize_health_data", "process_activities"]

