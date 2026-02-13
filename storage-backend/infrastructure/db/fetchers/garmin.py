"""Garmin health data fetcher."""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy import text

from core.pydantic_schemas import ChartData, Dataset, DataQuery
from infrastructure.db import require_garmin_session_factory, session_scope

from .base import BaseDataFetcher

logger = logging.getLogger(__name__)


class GarminDataFetcher(BaseDataFetcher):
    """Fetch garmin metrics from the health database."""

    AVAILABLE_METRICS = [
        "resting_heart_rate",
        "steps",
        "calories",
        "stress_level",
        "body_battery",
        "distance_km",
        "active_minutes",
        "vigorous_intensity_minutes",
        "moderate_intensity_minutes",
        "sleep_hours",
        "deep_sleep_hours",
        "light_sleep_hours",
        "rem_sleep_hours",
        "sleep_score",
        "weight",
        "bmi",
        "body_fat_percentage",
        "hrv_weekly_avg",
        "training_readiness_score",
        "endurance_score",
        "vo2_max",
        "training_load_acute",
    ]

    METRIC_QUERIES = {
        "resting_heart_rate": {
            "table": "get_user_summary",
            "value_column": "resting_heart_rate",
            "date_column": "calendar_date",
        },
        "steps": {
            "table": "get_user_summary",
            "value_column": "total_steps",
            "date_column": "calendar_date",
        },
        "calories": {
            "table": "get_user_summary",
            "value_column": "total_kilocalories",
            "date_column": "calendar_date",
        },
        "stress_level": {
            "table": "get_user_summary",
            "value_column": "average_stress_level",
            "date_column": "calendar_date",
        },
        "body_battery": {
            "table": "get_user_summary",
            "value_column": "body_battery_most_recent_value",
            "date_column": "calendar_date",
        },
        "distance_km": {
            "table": "get_user_summary",
            "value_column": "total_distance_meters / 1000.0",
            "date_column": "calendar_date",
        },
        "active_minutes": {
            "table": "get_user_summary",
            "value_column": "vigorous_intensity_minutes + moderate_intensity_minutes",
            "date_column": "calendar_date",
        },
        "vigorous_intensity_minutes": {
            "table": "get_user_summary",
            "value_column": "vigorous_intensity_minutes",
            "date_column": "calendar_date",
        },
        "moderate_intensity_minutes": {
            "table": "get_user_summary",
            "value_column": "moderate_intensity_minutes",
            "date_column": "calendar_date",
        },
        "sleep_hours": {
            "table": "get_sleep_data",
            "value_column": "sleep_time_seconds / 3600.0",
            "date_column": "calendar_date",
        },
        "deep_sleep_hours": {
            "table": "get_sleep_data",
            "value_column": "deep_sleep_seconds / 3600.0",
            "date_column": "calendar_date",
        },
        "light_sleep_hours": {
            "table": "get_sleep_data",
            "value_column": "light_sleep_seconds / 3600.0",
            "date_column": "calendar_date",
        },
        "rem_sleep_hours": {
            "table": "get_sleep_data",
            "value_column": "rem_sleep_seconds / 3600.0",
            "date_column": "calendar_date",
        },
        "sleep_score": {
            "table": "get_sleep_data",
            "value_column": "sleep_overall_score_value",
            "date_column": "calendar_date",
        },
        "weight": {
            "table": "get_body_composition",
            "value_column": "weight",
            "date_column": "calendar_date",
        },
        "bmi": {
            "table": "get_body_composition",
            "value_column": "bmi",
            "date_column": "calendar_date",
        },
        "body_fat_percentage": {
            "table": "get_body_composition",
            "value_column": "body_fat_percentage",
            "date_column": "calendar_date",
        },
        "hrv_weekly_avg": {
            "table": "get_hrv_data",
            "value_column": "hrv_weekly_avg",
            "date_column": "calendar_date",
        },
        "training_readiness_score": {
            "table": "get_training_readiness",
            "value_column": "training_readiness_score",
            "date_column": "calendar_date",
        },
        "endurance_score": {
            "table": "get_endurance_score",
            "value_column": "endurance_score",
            "date_column": "calendar_date",
        },
        "vo2_max": {
            "table": "get_training_status",
            "value_column": "vo2_max_precise_value",
            "date_column": "calendar_date",
        },
        "training_load_acute": {
            "table": "get_training_status",
            "value_column": "daily_training_load_acute",
            "date_column": "calendar_date",
        },
    }

    def get_available_metrics(self) -> List[str]:
        return self.AVAILABLE_METRICS

    async def fetch(self, query: DataQuery) -> ChartData:
        """Fetch metric data and convert to chart-ready format."""
        if query.metric not in self.METRIC_QUERIES:
            raise ValueError(
                f"Unknown Garmin metric '{query.metric}'. "
                f"Available metrics: {', '.join(self.AVAILABLE_METRICS)}"
            )

        metric_config = self.METRIC_QUERIES[query.metric]
        start_date, end_date = self.resolve_time_range(query.time_range)

        sql = text(
            f"""
            SELECT
                {metric_config['date_column']} as date_value,
                {metric_config['value_column']} as metric_value
            FROM {metric_config['table']}
            WHERE {metric_config['date_column']} BETWEEN :start_date AND :end_date
            ORDER BY {metric_config['date_column']}
            LIMIT :limit
        """
        )

        session_factory = require_garmin_session_factory()
        async with session_scope(session_factory) as session:
            result = await session.execute(
                sql,
                {
                    "start_date": start_date.date(),
                    "end_date": end_date.date(),
                    "limit": query.limit,
                },
            )
            rows = result.fetchall()

        labels: List[str] = []
        values: List[float] = []

        for row in rows:
            date_value = row.date_value
            if isinstance(date_value, datetime):
                labels.append(date_value.strftime("%Y-%m-%d"))
            else:
                labels.append(str(date_value))

            value = row.metric_value
            values.append(float(value) if value is not None else 0.0)

        labels, values = self._maybe_aggregate(labels, values, query.aggregation)

        return ChartData(
            labels=labels,
            datasets=[
                Dataset(
                    label=self._format_metric_label(query.metric),
                    data=values,
                )
            ],
        )

    def _format_metric_label(self, metric: str) -> str:
        return metric.replace("_", " ").title()

    def _maybe_aggregate(
        self, labels: List[str], values: List[float], aggregation: Optional[str]
    ) -> Tuple[List[str], List[float]]:
        if not aggregation or aggregation == "none":
            return labels, values
        if aggregation == "daily":
            return labels, values

        buckets: defaultdict[str, List[float]] = defaultdict(list)
        for label, value in zip(labels, values):
            bucket = self._bucket_label(label, aggregation)
            buckets[bucket].append(value)

        ordered_labels = sorted(buckets.keys())
        aggregated_values = [
            sum(buckets[label]) / max(len(buckets[label]), 1) for label in ordered_labels
        ]
        return ordered_labels, aggregated_values

    def _bucket_label(self, label: str, aggregation: str) -> str:
        dt = self._parse_label_to_datetime(label)
        if not dt:
            return label

        if aggregation == "weekly":
            return f"{dt.year}-W{dt.isocalendar().week:02d}"
        if aggregation == "monthly":
            return dt.strftime("%Y-%m")
        return dt.strftime("%Y-%m-%d")

    def _parse_label_to_datetime(self, label: str) -> Optional[datetime]:
        try:
            return datetime.fromisoformat(label)
        except ValueError:
            for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
                try:
                    return datetime.strptime(label, fmt)
                except ValueError:
                    continue
        return None


__all__ = ["GarminDataFetcher"]
