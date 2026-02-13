from datetime import datetime, timedelta, timezone

import pytest

from features.db.garmin.utils import (
    adjust_dates_for_special_modes,
    convert_timestamp,
    convert_timestamp_to_hhmm,
    get_local_offset,
    optimize_health_data,
    prepare_garmin_sleep_data,
    process_activities,
    revert_dates_for_special_modes,
    transform_date,
)


def test_optimize_health_data_merges_categories():
    data = {
        "get_sleep_data": [
            {
                "calendar_date": "2023-11-14",
                "sleep_time_seconds": 100,
                "sleep_avg_overnight_hrv": 52,
            }
        ],
        "get_user_summary": [
            {
                "calendar_date": "2023-11-14",
                "high_stress_duration": 10,
                "body_battery_lowest_value": 20,
            }
        ],
        "get_activities": [
            {
                "calendar_date": "2023-11-14",
                "activity_type": "run",
                "activity_distance": 3.4,
                "activity_duration": 20,
            }
        ],
    }

    result = optimize_health_data(data)

    assert result == [
        {
            "date": "2023-11-14",
            "sleep": {"sleep_time_seconds": 100, "sleep_avg_overnight_hrv": 52},
            "health": {
                "high_stress_duration": 10,
                "body_battery_lowest_value": 20,
            },
            "training": {
                "activity_type": ["run"],
                "activity_distance": 3.4,
                "activity_duration": 20.0,
                "activity_secs_in_zone1": 0.0,
                "activity_secs_in_zone2": 0.0,
                "activity_secs_in_zone3": 0.0,
                "activity_secs_in_zone4": 0.0,
                "activity_secs_in_zone5": 0.0,
            },
        }
    ]


def test_process_activities_rounds_values():
    activities = [
        {
            "calendar_date": "2023-11-14",
            "activity_type": "run",
            "activity_distance": 1.234,
            "activity_duration": 10.456,
        },
        {
            "calendar_date": "2023-11-14",
            "activity_type": "bike",
            "activity_distance": 2.221,
            "activity_duration": 5,
        },
    ]

    result = process_activities(activities)

    assert result["2023-11-14"]["activity_distance"] == pytest.approx(3.46, rel=1e-9)
    assert set(result["2023-11-14"]["activity_type"]) == {"run", "bike"}


def test_transform_date_rejects_future_date():
    with pytest.raises(ValueError):
        transform_date(datetime.now(timezone.utc) + timedelta(days=1))


def test_adjust_dates_for_special_modes_shifts_values():
    start, end = adjust_dates_for_special_modes(
        "correlation",
        "get_sleep_data",
        "2023-11-01",
        "2023-11-02",
        ["get_sleep_data"],
    )

    assert start == "2023-11-02"
    assert end == "2023-11-03"


def test_revert_dates_for_special_modes_reverses_shift():
    records = [{"calendar_date": "2023-11-03", "value": 1}]

    adjusted = revert_dates_for_special_modes(
        "correlation", "get_sleep_data", records, ["get_sleep_data"]
    )

    assert adjusted[0]["calendar_date"] == "2023-11-02"
    assert records[0]["calendar_date"] == "2023-11-03"  # original untouched


def test_timestamp_helpers_handle_local_offsets():
    offset = get_local_offset(1699920000000, 1699923600000)
    assert offset == timedelta(hours=1)

    local_time = convert_timestamp(1699920000000, offset)
    assert local_time == "01:00"

    iso_time = convert_timestamp("2023-11-14T01:00:00Z", offset, is_iso_string=True)
    assert iso_time == "02:00"

    hhmm = convert_timestamp_to_hhmm(1699920000000)
    assert hhmm == "00:00"


def test_prepare_garmin_sleep_data_returns_structured_payload():
    offset = timedelta(hours=1)
    user_input = {
        "dailySleepDTO": {
            "sleepStartTimestampLocal": 1699923600000,
            "sleepEndTimestampGMT": 1699943400000,
            "sleepStartTimestampGMT": 1699920000000,
            "sleepEndTimestampLocal": 1699947000000,
            "napTimeSeconds": 600,
        },
        "dailyNapDTOS": [
            {
                "napTimeSec": 600,
                "napFeedback": "restorative",
                "napStartTimestampGMT": "2023-11-14T10:00:00Z",
                "napEndTimestampGMT": "2023-11-14T10:30:00Z",
            }
        ],
        "sleepLevels": [
            {"startGMT": "2023-11-14T00:00:00Z", "endGMT": "2023-11-14T00:30:00Z", "level": "deep"}
        ],
        "sleepHeartRate": [{"value": 60, "startGMT": 1699920000000}],
        "hrvData": [{"value": 30, "startGMT": 1699920000000}],
        "sleepStress": [{"value": 10, "startGMT": 1699920000000}],
    }

    (
        sleep_start,
        sleep_end,
        sleep_start_gmt,
        sleep_end_gmt,
        nap_data,
        sleep_levels,
        heart_rate,
        hrv,
        stress,
    ) = prepare_garmin_sleep_data(user_input, offset)

    assert sleep_start == "01:00"
    assert sleep_end == "07:30"
    assert sleep_start_gmt == "00:00"
    assert sleep_end_gmt == "06:30"
    assert nap_data and nap_data[0]["napStartLocal"] == "11:00"
    assert sleep_levels[0]["startLocal"] == "01:00"
    assert heart_rate[0]["startLocal"] == "01:00"
    assert hrv[0]["startGMT"] == "00:00"
    assert stress[0]["startLocal"] == "01:00"
