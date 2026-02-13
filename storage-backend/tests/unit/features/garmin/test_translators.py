from __future__ import annotations

from datetime import date, datetime

from features.garmin.schemas.activity import ActivityRequest
from features.garmin.schemas.queries import GarminDataQuery
from features.garmin.translators import (
    translate_activity,
    translate_activity_gps,
    translate_daily_health_events,
    translate_endurance_score,
    translate_hrv,
    translate_training_status,
)


def test_translate_hrv_extracts_summary_fields() -> None:
    query = GarminDataQuery(start_date=date(2024, 7, 7))
    payload = {
        "hrvSummary": {
            "calendarDate": "2024-07-07",
            "weeklyAvg": 49,
            "lastNightAvg": 51,
            "status": "BALANCED",
            "baseline": {"balancedLow": 43, "balancedUpper": 55},
        }
    }

    records = list(translate_hrv(payload, query))

    assert records == [
        {
            "calendar_date": date(2024, 7, 7),
            "hrv_weekly_avg": 49,
            "hrv_last_night_avg": 51,
            "hrv_status": "BALANCED",
            "hrv_baseline_balanced_low": 43,
            "hrv_baseline_balanced_upper": 55,
        }
    ]


def test_translate_endurance_score_includes_contributors() -> None:
    query = GarminDataQuery(start_date=date(2024, 6, 13))
    payload = {
        "enduranceScoreDTO": {
            "calendarDate": "2024-06-13",
            "overallScore": 5730,
            "classification": 2,
            "classificationLowerLimitIntermediate": 5100,
            "classificationLowerLimitTrained": 5800,
            "classificationLowerLimitWellTrained": 6500,
            "classificationLowerLimitExpert": 7200,
            "classificationLowerLimitSuperior": 7900,
            "classificationLowerLimitElite": 8600,
            "contributors": [
                {"activityTypeId": 3, "contribution": 78.04},
                {"activityTypeId": 13, "contribution": 13.86},
            ],
        }
    }

    records = list(translate_endurance_score(payload, query))

    assert records[0]["endurance_score"] == 5730
    assert records[0]["endurance_score_classification_lower_limit_trained"] == 5800
    assert records[0]["endurance_score_contributors"] == [
        {"activityTypeId": 3, "contribution": 78.04},
        {"activityTypeId": 13, "contribution": 13.86},
    ]


def test_translate_training_status_combines_sections() -> None:
    query = GarminDataQuery(start_date=date(2024, 6, 13))
    payload = {
        "mostRecentTrainingStatus": {
            "latestTrainingStatusData": {
                "device": {
                    "calendarDate": "2024-06-13",
                    "trainingStatusFeedbackPhrase": "RECOVERY_1",
                    "acuteTrainingLoadDTO": {
                        "dailyTrainingLoadAcute": 107,
                        "dailyTrainingLoadChronic": 219,
                        "minTrainingLoadChronic": 175.2,
                        "maxTrainingLoadChronic": 328.5,
                    },
                }
            }
        },
        "mostRecentTrainingLoadBalance": {
            "metricsTrainingLoadBalanceDTOMap": {
                "device": {
                    "calendarDate": "2024-06-13",
                    "monthlyLoadAerobicLow": 431.0,
                    "monthlyLoadAerobicHigh": 0.0,
                    "monthlyLoadAnaerobic": 132.5,
                    "monthlyLoadAerobicLowTargetMin": 142,
                    "monthlyLoadAerobicLowTargetMax": 353,
                    "monthlyLoadAerobicHighTargetMin": 244,
                    "monthlyLoadAerobicHighTargetMax": 456,
                    "monthlyLoadAnaerobicTargetMin": 0,
                    "monthlyLoadAnaerobicTargetMax": 211,
                    "trainingBalanceFeedbackPhrase": "AEROBIC_HIGH_SHORTAGE",
                }
            }
        },
        "mostRecentVO2Max": {
            "generic": {"calendarDate": "2024-06-08", "vo2MaxPreciseValue": 48.6}
        },
    }

    records = list(translate_training_status(payload, query))

    record = records[0]
    assert record["calendar_date"] == date(2024, 6, 13)
    assert record["daily_training_load_acute"] == 107
    assert record["monthly_load_aerobic_low"] == 431.0
    assert record["training_balance_feedback_phrase"] == "AEROBIC_HIGH_SHORTAGE"
    assert record["vo2_max_precise_value"] == 48.6


def test_translate_activity_flattens_summary_fields() -> None:
    query = GarminDataQuery(start_date=date(2024, 6, 6))
    payload = [
        {
            "activityId": 15774991090,
            "activityName": "Morning Run",
            "activityType": {"typeKey": "running"},
            "locationName": "La Bisbal",
            "summaryDTO": {
                "calendarDate": "2024-06-06",
                "startTimeLocal": "2024-06-06T08:01:54",
                "duration": 3600.0,
                "distance": 10000.0,
                "averageHR": 140,
                "maxHR": 160,
                "timeInHrZone5": 120.0,
            },
        }
    ]

    records = list(translate_activity(payload, query))

    assert records == [
        {
            "calendar_date": date(2024, 6, 6),
            "activity_id": 15774991090,
            "activity_type": "running",
            "activity_name": "Morning Run",
            "activity_location_name": "La Bisbal",
            "activity_start_time": "08:01",
            "activity_duration": 3600.0,
            "activity_distance": 10000.0,
            "activity_average_hr": 140,
            "activity_max_hr": 160,
            "activity_secs_in_zone5": 120.0,
        }
    ]


def test_translate_activity_gps_infers_calendar_date() -> None:
    query = GarminDataQuery(start_date=date(2024, 6, 6), activity_id=15774991090)
    payload = {
        "activityId": 15774991090,
        "summaryDTO": {"startTimeLocal": "2024-06-06T08:01:54"},
        "geoPolylineDTO": {"geoPolyline": [1, 2, 3]},
    }

    records = list(translate_activity_gps(payload, query))

    assert records == [
        {
            "activity_id": 15774991090,
            "calendar_date": date(2024, 6, 6),
            "gps_data": {"geoPolyline": [1, 2, 3]},
        }
    ]


def test_translate_activity_gps_builds_coordinates_from_detail_metrics() -> None:
    query = GarminDataQuery(start_date=date(2024, 10, 24), activity_id=20784961405)
    payload = {
        "activityId": 20784961405,
        "summaryDTO": {
            "calendarDate": "2024-10-24",
            "activityName": "Quart Hiking",
            "startTimeLocal": "2024-10-24T09:26:00",
        },
        "metricDescriptors": [
            {"key": "directLatitude", "metricsIndex": 0},
            {"key": "directLongitude", "metricsIndex": 1},
            {"key": "directElevation", "metricsIndex": 2},
            {"key": "directHeartRate", "metricsIndex": 3},
            {"key": "directTimestamp", "metricsIndex": 4},
        ],
        "activityDetailMetrics": [
            {"metrics": [41.12345, 2.12345, 180.2, 132, 1729771560]},
            {"metrics": [41.12365, 2.12365, 181.4, 134, 1729771620]},
        ],
    }

    records = list(translate_activity_gps(payload, query))

    assert records == [
        {
            "activity_id": 20784961405,
            "calendar_date": date(2024, 10, 24),
            "activity_name": "Quart Hiking",
            "gps_data": {
                "coordinates": [
                    {
                        "lat": 41.12345,
                        "lon": 2.12345,
                        "elevation": 180.2,
                        "heartRate": 132,
                        "timestamp": 1729771560,
                    },
                    {
                        "lat": 41.12365,
                        "lon": 2.12365,
                        "elevation": 181.4,
                        "heartRate": 134,
                        "timestamp": 1729771620,
                    },
                ]
            },
        }
    ]


def test_translate_daily_health_events_parses_timestamps() -> None:
    query = GarminDataQuery(start_date=date(2024, 6, 6))
    payload = [
        {
            "calendarDate": "2024-06-06",
            "lastMealTime": "2024-06-06T18:35:00",
            "lastDrinkTime": "2024-06-06T12:15:00",
        }
    ]

    records = list(translate_daily_health_events(payload, query))

    assert records[0]["calendar_date"] == date(2024, 6, 6)
    assert records[0]["last_meal_time"] == datetime(2024, 6, 6, 18, 35)
    assert records[0]["last_drink_time"] == datetime(2024, 6, 6, 12, 15)
    assert "last_screen_time" not in records[0]


def test_translate_activity_merges_weather_and_zone_details() -> None:
    query = GarminDataQuery(start_date=date(2024, 8, 12))
    payload = [
        {
            "activityId": 445566,
            "activityName": "Evening Ride",
            "summaryDTO": {
                "calendarDate": "2024-08-12",
                "startTimeLocal": "2024-08-12T19:05:00",
                "duration": 1800.0,
            },
            "zones": [
                {"zoneNumber": 1, "secsInZone": 120.0},
                {"zoneNumber": 2, "secsInZone": 240.0},
            ],
            "weather": {
                "temp": 50.0,
                "relativeHumidity": 45,
                "windDirectionCompassPoint": "NW",
                "windSpeed": 10,
                "windGust": 15,
                "weatherTypeDTO": {"desc": "Partly Cloudy"},
            },
        }
    ]

    records = list(translate_activity(payload, query))

    assert records == [
        {
            "calendar_date": date(2024, 8, 12),
            "activity_id": 445566,
            "activity_name": "Evening Ride",
            "activity_start_time": "19:05",
            "activity_duration": 1800.0,
            "activity_weather_temperature_on_start": 10.0,
            "activity_weather_relative_humidity_on_start": 45,
            "activity_weather_wind_direction_on_start": "NW",
            "activity_weather_wind_speed_on_start": 16.1,
            "activity_weather_wind_gust_on_start": 24.1,
            "activity_weather_type_desc": "Partly Cloudy",
            "activity_secs_in_zone1": 120.0,
            "activity_secs_in_zone2": 240.0,
        }
    ]


def test_translate_activity_includes_stride_length_synonyms() -> None:
    query = GarminDataQuery(start_date=date(2024, 3, 4))
    payload = [
        {
            "activityId": 998877,
            "activityName": "Morning Walk",
            "summaryDTO": {
                "calendarDate": "2024-03-04",
                "startTimeLocal": "2024-03-04T07:45:00",
                "avgStrideLength": 0.85,
            },
        }
    ]

    records = list(translate_activity(payload, query))

    assert records == [
        {
            "calendar_date": date(2024, 3, 4),
            "activity_id": 998877,
            "activity_name": "Morning Walk",
            "activity_start_time": "07:45",
            "activityAvgStrideLength": 0.85,
        }
    ]


def test_activity_request_to_internal_promotes_stride_length() -> None:
    request = ActivityRequest.model_validate(
        {
            "calendarDate": "2024-03-04",
            "activityId": 123,
            "activityAvgStrideLength": 0.92,
        }
    )

    internal = request.to_internal()

    assert internal["activity_avgStrideLength"] == 0.92
    assert "activity_avg_stride_length" not in internal
