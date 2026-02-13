"""GPS and coordinate extraction utilities for Garmin activities."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

# Mapping from Garmin descriptor keys to our normalized field names
GPS_DESCRIPTOR_MAPPING: dict[str, str] = {
    "directLatitude": "lat",
    "directLongitude": "lon",
    "directElevation": "elevation",
    "directHeartRate": "heartRate",
    "directBodyBattery": "bodyBattery",
    "directDoubleCadence": "doubleCadence",
    "directTimestamp": "timestamp",
}


def coordinates_from_detail(entry: Mapping[str, Any]) -> Mapping[str, Any] | None:
    """Extract coordinate dictionaries from legacy detail payloads.

    Legacy format uses metricDescriptors to define field indices and
    activityDetailMetrics containing arrays of values.

    Args:
        entry: Activity entry with potential metricDescriptors and activityDetailMetrics

    Returns:
        Dictionary with 'coordinates' key containing list of coordinate dicts,
        or None if no valid coordinates found
    """
    descriptors = entry.get("metricDescriptors")
    metrics = entry.get("activityDetailMetrics")
    if not isinstance(descriptors, Iterable) or not isinstance(metrics, Iterable):
        return None

    # Build index map from descriptors
    index_map: dict[str, int] = {}
    for descriptor in descriptors:
        if not isinstance(descriptor, Mapping):
            continue
        key = descriptor.get("key")
        index = descriptor.get("metricsIndex")
        if isinstance(key, str) and isinstance(index, int):
            index_map[key] = index

    # Require at least lat/lon
    if "directLatitude" not in index_map or "directLongitude" not in index_map:
        return None

    coordinates: list[dict[str, Any]] = []
    for detail in metrics:
        if not isinstance(detail, Mapping):
            continue
        values = detail.get("metrics")
        if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
            continue

        coordinate: dict[str, Any] = {}
        for descriptor_key, target_key in GPS_DESCRIPTOR_MAPPING.items():
            index = index_map.get(descriptor_key)
            if index is None or index >= len(values):
                continue
            value = values[index]
            if value is None:
                continue
            coordinate[target_key] = value

        if "lat" in coordinate and "lon" in coordinate:
            coordinates.append(coordinate)

    if not coordinates:
        return None

    return {"coordinates": coordinates}


def coordinates_from_polyline(entry: Mapping[str, Any]) -> Mapping[str, Any] | None:
    """Extract coordinate dictionaries from polyline format payloads.

    Modern format with geoPolylineDTO/geoPolyline containing structured coordinate data.

    Args:
        entry: Activity entry with potential geoPolylineDTO or geoPolyline

    Returns:
        Dictionary with 'coordinates' key containing list of coordinate dicts,
        or None if no valid coordinates found
    """
    polyline_container = entry.get("geoPolylineDTO") or entry.get("geoPolyline")
    if not isinstance(polyline_container, Mapping):
        return None

    polyline = polyline_container.get("polyline")
    if not isinstance(polyline, Iterable):
        return None

    coordinates: list[dict[str, Any]] = []
    for point in polyline:
        if not isinstance(point, Mapping):
            continue
        lat = point.get("lat")
        lon = point.get("lon")
        if lat is None or lon is None:
            continue

        coordinate: dict[str, Any] = {"lat": lat, "lon": lon}

        # Add optional fields if present
        altitude = point.get("altitude") or point.get("altitudeInMeters")
        if altitude is not None:
            coordinate["elevation"] = altitude
        if point.get("heartRate") is not None:
            coordinate["heartRate"] = point.get("heartRate")
        if point.get("bodyBattery") is not None:
            coordinate["bodyBattery"] = point.get("bodyBattery")
        if point.get("doubleCadence") is not None:
            coordinate["doubleCadence"] = point.get("doubleCadence")

        timestamp = point.get("time") or point.get("timestamp")
        if timestamp is not None:
            coordinate["timestamp"] = timestamp

        coordinates.append(coordinate)

    if not coordinates:
        return None

    return {"coordinates": coordinates}


def resolve_gps_payload(entry: Mapping[str, Any]) -> Any:
    """Return the best-effort GPS payload for an activity entry.

    Tries multiple extraction strategies in priority order:
    1. Legacy detail format (metricDescriptors + activityDetailMetrics)
    2. Modern polyline format (geoPolylineDTO/geoPolyline with structured data)
    3. Raw samples or trackPoints
    4. Raw polyline container

    Args:
        entry: Activity entry potentially containing GPS data

    Returns:
        GPS payload in whatever format was successfully extracted, or None
    """
    # Try structured extractions first
    coordinates = coordinates_from_detail(entry)
    if coordinates:
        return coordinates

    coordinates = coordinates_from_polyline(entry)
    if coordinates:
        return coordinates

    # Fallback to raw payloads
    payload = entry.get("samples") or entry.get("trackPoints")
    if payload:
        return payload

    polyline_payload = entry.get("geoPolylineDTO") or entry.get("geoPolyline")
    if polyline_payload:
        return polyline_payload

    return None
