"""Body composition payload translators for Garmin integrations."""

from __future__ import annotations

from typing import Any, Iterable, Mapping, MutableMapping, Sequence

from features.garmin.schemas.queries import GarminDataQuery
from features.garmin.schemas.base import normalise_iterable

from .utils import coerce_date_key, walk_payload

_BODY_COMPOSITION_FIELDS: Sequence[str] = (
    "weight",
    "bmi",
    "body_fat_mass",
    "body_fat_percentage",
    "body_water_mass",
    "body_water_percentage",
    "bone_mass",
    "bone_mass_percentage",
    "muscle_mass",
    "muscle_mass_percentage",
    "visceral_fat",
    "basal_metabolic_rate",
)


def translate_body_composition(
    payload: Any, query: GarminDataQuery
) -> Iterable[Mapping[str, Any]]:
    """Merge Garmin and Withings body composition payloads on calendar date."""

    _ = query  # Body composition translation relies solely on payload content.

    if not payload:
        return []

    garmin_payload: Any = payload
    withings_payload: Iterable[Mapping[str, Any]] | None = None
    if isinstance(payload, Mapping):
        garmin_payload = payload.get("garmin")
        withings_payload = payload.get("withings")

    merged: dict[str, MutableMapping[str, Any]] = {}

    for record in normalise_garmin_body_composition(garmin_payload):
        date_key = coerce_date_key(record.get("calendar_date"))
        if date_key is None:
            continue
        container = merged.setdefault(date_key.isoformat(), {"calendar_date": date_key})
        container.update(record)

    if withings_payload:
        _merge_withings_payload(merged, withings_payload)

    return merged.values()


def normalise_garmin_body_composition(payload: Any) -> Iterable[Mapping[str, Any]]:
    """Extract Garmin body composition records with consistent field names."""

    if not payload:
        return []

    records: list[Mapping[str, Any]] = []
    for entry in walk_payload(payload):
        if not isinstance(entry, Mapping):
            continue
        if not any(key in entry for key in ("weight", "weightKg", "weight_kg")):
            continue

        record: dict[str, Any] = {}
        calendar_value = (
            entry.get("calendarDate") or entry.get("calendar_date") or entry.get("date")
        )
        calendar_date = coerce_date_key(calendar_value)
        if calendar_date is not None:
            record["calendar_date"] = calendar_date

        weight_value = entry.get("weight") or entry.get("weightKg") or entry.get("weight_kg")
        try:
            if weight_value is not None:
                record["weight"] = round(float(weight_value), 2)
        except (TypeError, ValueError):  # pragma: no cover - invalid payload
            pass

        for field in _BODY_COMPOSITION_FIELDS:
            if field in record:
                continue
            value = entry.get(field)
            if value is not None:
                record[field] = value

        if record:
            records.append(record)

    return records


def _merge_withings_payload(
    merged: MutableMapping[str, MutableMapping[str, Any]],
    payload: Iterable[Mapping[str, Any]] | None,
) -> None:
    """Overlay Withings measurements onto Garmin records keyed by date."""

    if not payload:
        return

    for record in normalise_iterable(payload):
        if not isinstance(record, Mapping):
            continue
        date_key = coerce_date_key(record.get("calendar_date"))
        if date_key is None:
            continue
        container = merged.setdefault(date_key.isoformat(), {"calendar_date": date_key})
        for field in _BODY_COMPOSITION_FIELDS:
            value = record.get(field)
            if value is not None:
                container[field] = value
