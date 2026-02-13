"""Tests for Garmin sleep schema normalisation."""

from __future__ import annotations

from features.garmin.schemas.requests import SleepIngestRequest


def test_sleep_field_mapping_completeness():
    payload = {
        "calendarDate": "2025-10-25",
        "dailySleepDTO": {
            "calendarDate": "2025-10-25",
            "sleepTimeSeconds": 29940,
            "sleepStartTimestampGMT": 1729884240000,
            "sleepStartTimestampLocal": 1729891440000,
            "sleepEndTimestampGMT": 1729914180000,
            "sleepEndTimestampLocal": 1729921380000,
            "averageRespirationValue": 15.0,
            "lowestRespirationValue": 8.0,
            "highestRespirationValue": 18.0,
            "awakeCount": 1,
            "sleepScores": {
                "overall": {"value": 79, "qualifierKey": "FAIR"},
                "totalDuration": {"qualifierKey": "FAIR"},
                "stress": {"qualifierKey": "FAIR"},
                "awakeCount": {"qualifierKey": "GOOD"},
                "remPercentage": {
                    "value": 27,
                    "qualifierKey": "EXCELLENT",
                    "optimalStart": 21,
                    "optimalEnd": 31,
                },
                "restlessness": {
                    "qualifierKey": "EXCELLENT",
                    "optimalStart": 0,
                    "optimalEnd": 5,
                },
                "lightPercentage": {
                    "value": 50,
                    "qualifierKey": "EXCELLENT",
                    "optimalStart": 30,
                    "optimalEnd": 64,
                },
                "deepPercentage": {
                    "value": 23,
                    "qualifierKey": "EXCELLENT",
                    "optimalStart": 16,
                    "optimalEnd": 33,
                },
            },
        },
        "avgOvernightHrv": 38.0,
        "restingHeartRate": 49,
        "bodyBatteryChange": 45,
        "restlessMomentsCount": 24,
        "sleepLevels": [],
        "sleepHeartRate": [],
        "hrvData": [],
        "sleepStress": [],
    }

    internal = SleepIngestRequest(**payload).to_internal()

    assert internal["sleep_average_respiration_value"] == 15.0
    assert internal["sleep_lowest_respiration_value"] == 8.0
    assert internal["sleep_highest_respiration_value"] == 18.0
    assert internal["sleep_awake_count"] == 1

    assert internal["sleep_overall_score_value"] == 79
    assert internal["sleep_overall_score_qualifier"] == "FAIR"
    assert internal["sleep_total_duration_qualifier"] == "FAIR"
    assert internal["sleep_awake_count_qualifier"] == "GOOD"
    assert internal["sleep_stress_qualifier"] == "FAIR"

    assert internal["sleep_rem_percentage_value"] == 27
    assert internal["sleep_rem_percentage_qualifier"] == "EXCELLENT"
    assert internal["sleep_rem_optimal_start"] == 21
    assert internal["sleep_rem_optimal_end"] == 31

    assert internal["sleep_light_percentage_value"] == 50
    assert internal["sleep_light_percentage_qualifier"] == "EXCELLENT"

    assert internal["sleep_deep_percentage_value"] == 23
    assert internal["sleep_deep_percentage_qualifier"] == "EXCELLENT"

    assert internal["sleep_avg_overnight_hrv"] == 38.0
    assert internal["sleep_resting_heart_rate"] == 49
    assert internal["sleep_body_battery_change"] == 45
    assert internal["sleep_restless_moments_count"] == 24

    assert internal["time_offset"] == "02:00:00"
