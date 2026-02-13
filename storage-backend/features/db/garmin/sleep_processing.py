"""Garmin sleep payload transformations shared across repositories.

The Garmin APIs pack several related series (levels, HR, HRV, naps) into a
single payload.  The helpers here unpack the response into deterministic lists
that can be inserted into MySQL without post-processing in the calling layers.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional

from .timestamps import convert_timestamp


def prepare_garmin_sleep_data(
    user_input: Mapping[str, Any],
    offset: timedelta,
) -> tuple[
    Optional[str],
    Optional[str],
    Optional[str],
    Optional[str],
    Optional[List[Dict[str, Any]]],
    List[Dict[str, Any]],
    List[Dict[str, Any]],
    List[Dict[str, Any]],
    List[Dict[str, Any]],
]:
    """Normalise Garmin sleep payloads into DB-friendly structures.

    ``user_input`` must contain a ``dailySleepDTO`` key with Garmin's sleep
    summary payload. The helper converts timestamps to local/GMT HH:MM strings
    and ensures nested arrays are serialisable dictionaries.
    """

    main_sleep = user_input.get("dailySleepDTO")
    if not isinstance(main_sleep, Mapping):
        raise ValueError("user_input must contain a dailySleepDTO mapping")

    sleep_start = _format_local_time(
        main_sleep.get("sleepStartTimestampLocal"),
        main_sleep.get("sleepStartTimestampGMT"),
        offset,
    )
    sleep_end = _format_local_time(
        main_sleep.get("sleepEndTimestampLocal"),
        main_sleep.get("sleepEndTimestampGMT"),
        offset,
    )

    sleep_start_gmt = convert_timestamp(main_sleep.get("sleepStartTimestampGMT"), timedelta(0))
    sleep_end_gmt = convert_timestamp(main_sleep.get("sleepEndTimestampGMT"), timedelta(0))

    nap_data: Optional[List[Dict[str, Any]]] = None
    if (main_sleep.get("napTimeSeconds") or 0) > 0:
        nap_data = []
        for nap in user_input.get("dailyNapDTOS", []):
            if not isinstance(nap, Mapping):
                continue
            nap_data.append(
                {
                    "napTimeSec": nap.get("napTimeSec"),
                    "napFeedback": nap.get("napFeedback"),
                    "napStartLocal": convert_timestamp(
                        nap.get("napStartTimestampGMT"), offset, is_iso_string=True
                    ),
                    "napEndLocal": convert_timestamp(
                        nap.get("napEndTimestampGMT"), offset, is_iso_string=True
                    ),
                    "napStartGMT": convert_timestamp(
                        nap.get("napStartTimestampGMT"), timedelta(0), is_iso_string=True
                    ),
                    "napEndGMT": convert_timestamp(
                        nap.get("napEndTimestampGMT"), timedelta(0), is_iso_string=True
                    ),
                }
            )

    sleep_levels_data = []
    for level in user_input.get("sleepLevels", []) or []:
        if not isinstance(level, Mapping):
            continue
        start_gmt = level.get("startGMT")
        end_gmt = level.get("endGMT")
        sleep_levels_data.append(
            {
                **level,
                "startLocal": convert_timestamp(start_gmt, offset, is_iso_string=True),
                "endLocal": convert_timestamp(end_gmt, offset, is_iso_string=True),
                "startGMT": convert_timestamp(start_gmt, timedelta(0), is_iso_string=True),
                "endGMT": convert_timestamp(end_gmt, timedelta(0), is_iso_string=True),
            }
        )

    sleep_heart_rate_data = _normalise_series(
        user_input.get("sleepHeartRate", []), offset
    )
    sleep_hrv_data = _normalise_series(user_input.get("hrvData", []), offset)
    sleep_stress_data = _normalise_series(user_input.get("sleepStress", []), offset)

    return (
        sleep_start,
        sleep_end,
        sleep_start_gmt,
        sleep_end_gmt,
        nap_data,
        sleep_levels_data,
        sleep_heart_rate_data,
        sleep_hrv_data,
        sleep_stress_data,
    )


def _format_local_time(
    local_ts: int | None,
    gmt_ts: int | None,
    offset: timedelta,
) -> Optional[str]:
    """Prefer the device-local timestamp when present otherwise fallback to GMT."""

    if local_ts:
        return datetime.fromtimestamp(int(local_ts) / 1000, tz=timezone.utc).strftime("%H:%M")
    return convert_timestamp(gmt_ts, offset)


def _normalise_series(series: Iterable[Mapping[str, Any]], offset: timedelta) -> List[Dict[str, Any]]:
    """Map Garmin's (value, startGMT) series into HH:MM friendly dicts."""

    normalised: List[Dict[str, Any]] = []
    for record in series or []:
        if not isinstance(record, Mapping):
            continue
        start_gmt = record.get("startGMT")
        if start_gmt is None:
            continue
        normalised.append(
            {
                "value": record.get("value"),
                "startLocal": convert_timestamp(start_gmt, offset),
                "startGMT": convert_timestamp(start_gmt, timedelta(0)),
            }
        )
    return normalised


__all__ = ["prepare_garmin_sleep_data"]

