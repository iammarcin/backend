"""Endurance score translation for Garmin performance data."""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from features.garmin.schemas.base import normalise_iterable
from features.garmin.schemas.queries import GarminDataQuery

from .utils import coerce_date_key, query_default_date


def normalize_endurance_score(raw_score: Any) -> int | None:
    """Convert Garmin's raw endurance score to the 0-100 range expected downstream."""

    if raw_score is None:
        return None

    try:
        score = float(raw_score)
    except (TypeError, ValueError):
        return None

    normalized = int(score / 100)
    return max(0, min(100, normalized))


def translate_endurance_score(payload: Any, query: GarminDataQuery) -> Iterable[Mapping[str, Any]]:
    """Normalise endurance score payloads."""

    if not payload:
        return []

    entries: list[Mapping[str, Any]] = []
    if isinstance(payload, Mapping) and payload.get("enduranceScoreDTO"):
        entries.append(payload["enduranceScoreDTO"])
    elif isinstance(payload, Mapping):
        entries.append(payload)
    elif isinstance(payload, Sequence) and not isinstance(payload, (str, bytes)):
        entries.extend(item for item in payload if isinstance(item, Mapping))

    records: list[dict[str, Any]] = []
    for entry in entries:
        calendar_source = entry.get("calendarDate") or entry.get("calendar_date") or query_default_date(query)
        calendar_date = coerce_date_key(calendar_source)
        if calendar_date is None:
            continue

        contributors = entry.get("contributors") or entry.get("endurance_score_contributors")
        if isinstance(contributors, Mapping):
            contributors_payload: Any = dict(contributors)
        elif isinstance(contributors, Sequence) and not isinstance(contributors, (str, bytes)):
            contributors_payload = normalise_iterable(contributors)
        else:
            contributors_payload = contributors

        record = {
            "calendar_date": calendar_date,
            "endurance_score": entry.get("overallScore") or entry.get("endurance_score"),
            "endurance_score_classification": entry.get("classification")
            or entry.get("endurance_score_classification"),
            "endurance_score_classification_lower_limit_intermediate": entry.get(
                "classificationLowerLimitIntermediate"
            ),
            "endurance_score_classification_lower_limit_trained": entry.get(
                "classificationLowerLimitTrained"
            ),
            "endurance_score_classification_lower_limit_well_trained": entry.get(
                "classificationLowerLimitWellTrained"
            ),
            "endurance_score_classification_lower_limit_expert": entry.get(
                "classificationLowerLimitExpert"
            ),
            "endurance_score_classification_lower_limit_superior": entry.get(
                "classificationLowerLimitSuperior"
            ),
            "endurance_score_classification_lower_limit_elite": entry.get(
                "classificationLowerLimitElite"
            ),
        }

        if contributors_payload is not None:
            record["endurance_score_contributors"] = contributors_payload

        records.append({key: value for key, value in record.items() if value is not None})

    return records
