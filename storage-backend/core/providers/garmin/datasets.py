"""Dataset helper mixins for the Garmin Connect provider.

Each method encapsulates the URL paths, query parameters, and data shaping for a
single Garmin endpoint.  By moving these helpers into a dedicated mixin the core
client remains focused on authentication and HTTP orchestration.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Mapping

from .utils import date_range, to_date_string


class GarminDatasetMixin:
    """Expose high-level dataset fetchers for :class:`GarminConnectClient`."""

    def fetch_sleep(self, *, display_name: str, start: date, end: date | None = None) -> list[Mapping[str, Any]]:
        results: list[Mapping[str, Any]] = []
        for day in date_range(start, end):
            path = f"/wellness-service/wellness/dailySleepData/{display_name}"
            payload = self._request(path, params={"date": day, "nonSleepBufferMinutes": 60})
            if payload:
                results.append(payload)
        return results

    def fetch_user_summary(self, *, display_name: str, start: date, end: date | None = None) -> list[Mapping[str, Any]]:
        results: list[Mapping[str, Any]] = []
        for day in date_range(start, end):
            path = f"/usersummary-service/usersummary/daily/{display_name}"
            payload = self._request(path, params={"calendarDate": day})
            if payload:
                results.append(payload)
        return results

    def fetch_body_composition(self, *, start: date, end: date | None = None) -> Mapping[str, Any] | None:
        params = {"startDate": to_date_string(start), "endDate": to_date_string(end or start)}
        return self._request("/weight-service/weight/dateRange", params=params)

    def fetch_hrv(self, *, target_date: date) -> Mapping[str, Any] | None:
        path = f"/hrv-service/hrv/{to_date_string(target_date)}"
        return self._request(path)

    def fetch_training_readiness(self, *, target_date: date) -> list[Mapping[str, Any]]:
        path = f"/metrics-service/metrics/trainingreadiness/{to_date_string(target_date)}"
        payload = self._request(path) or []
        if isinstance(payload, list):
            return payload
        return [payload]

    def fetch_endurance_score(self, *, start: date, end: date | None = None) -> Mapping[str, Any] | None:
        if end and end != start:
            path = "/metrics-service/metrics/endurancescore/stats"
            params = {"startDate": to_date_string(start), "endDate": to_date_string(end)}
        else:
            path = "/metrics-service/metrics/endurancescore"
            params = {"calendarDate": to_date_string(start)}
        return self._request(path, params=params)

    def fetch_training_status(self, *, target_date: date) -> Mapping[str, Any] | None:
        path = f"/metrics-service/metrics/trainingstatus/daily/{to_date_string(target_date)}"
        return self._request(path)

    def fetch_training_load_balance(self, *, target_date: date) -> Mapping[str, Any] | None:
        """Fetch training load balance metrics (monthly aerobic/anaerobic distribution)."""

        path = f"/metrics-service/metrics/trainingloadbalance/latest/{to_date_string(target_date)}"
        return self._request(path)

    def fetch_fitness_age(self, *, target_date: date) -> Mapping[str, Any] | None:
        path = f"/fitnessage-service/fitnessage/{to_date_string(target_date)}"
        return self._request(path)

    def fetch_activities(
        self,
        *,
        start: date,
        end: date | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Mapping[str, Any]]:
        params: dict[str, Any] = {
            "startDate": to_date_string(start),
            "endDate": to_date_string(end or start),
            "start": offset,
        }
        if limit is not None:
            params["limit"] = limit
        payload = self._request("/activitylist-service/activities/search/activities", params=params)
        if isinstance(payload, list):
            return payload
        return []

    def fetch_activity_detail(self, activity_id: int) -> Mapping[str, Any] | None:
        path = f"/activity-service/activity/{activity_id}/details"
        return self._request(path)

    def fetch_activity_gps(self, activity_id: int) -> Mapping[str, Any] | None:
        path = f"/activity-service/activity/{activity_id}/gps"
        return self._request(path)

    def fetch_activity_weather(self, activity_id: int) -> Mapping[str, Any] | None:
        """Fetch weather conditions observed during a recorded activity."""

        path = f"/activity-service/activity/{activity_id}/weather"
        return self._request(path)

    def fetch_activity_hr_zones(self, activity_id: int) -> Mapping[str, Any] | None:
        """Fetch time-in-zone metrics for an activity's heart rate data."""

        path = f"/activity-service/activity/{activity_id}/hrTimeInZones"
        return self._request(path)

    def fetch_daily_health_events(self, *, target_date: date, display_name: str) -> list[Mapping[str, Any]]:
        path = f"/wellness-service/wellness/dailyHealthEvents/{display_name}"
        params = {"date": to_date_string(target_date)}
        payload = self._request(path, params=params)
        if isinstance(payload, list):
            return payload
        if payload:
            return [payload]
        return []

    def fetch_max_metrics(self, *, start: date, end: date | None = None) -> list[Mapping[str, Any]]:
        """Fetch VO2 max metrics for a date range (monthly updates).

        Returns monthly VO2 max values from Garmin.
        Typically called with a ~1 year range to get historical VO2 max progression.
        """
        path = f"/metrics-service/metrics/maxmet/monthly/{to_date_string(start)}/{to_date_string(end or start)}"
        payload = self._request(path)
        if isinstance(payload, list):
            return payload
        if isinstance(payload, Mapping):
            return [payload]
        return []


__all__ = ["GarminDatasetMixin"]
