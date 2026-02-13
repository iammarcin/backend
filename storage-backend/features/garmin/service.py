"""High level orchestration for Garmin Connect dataset ingestion.

This module defines :class:`GarminProviderService`, a thin coordinator that
delegates the translation of raw Garmin responses to helper utilities and
optionally persists the cleaned records using :class:`GarminService`.  The
actual translation logic lives in :mod:`features.garmin.translators` so the
service file focuses on request/response orchestration rather than low level
payload munging.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import ConfigurationError, ProviderError, ValidationError
from core.providers.garmin import GarminConnectClient
from core.providers.withings import WithingsClient
from features.db.garmin.service import GarminService
from features.garmin.dataset_registry import (
    DatasetConfig,
    GarminDatasetContext,
    build_dataset_configs,
    fetch_dataset_raw,
)
from features.garmin.results import IngestResult
from features.garmin.schemas.queries import DataSource, GarminDataQuery
from features.garmin.schemas.requests import GarminRequest

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class DatasetResult:
    """Container describing dataset fetch outcomes."""

    dataset: str
    items: list[dict[str, Any]]
    raw: list[Any]
    ingested: list[IngestResult]
    saved: bool

    def to_payload(self) -> tuple[dict[str, Any], dict[str, Any]]:
        data = {"items": self.items, "count": len(self.items)}
        meta = {
            "dataset": self.dataset,
            "count": len(self.items),
            "saved": self.saved,
        }
        if self.ingested:
            meta["ingested"] = [result.to_dict() for result in self.ingested]
        return data, meta


@dataclass(slots=True)
class GarminProviderService:
    """Coordinate Garmin Connect fetches and optional persistence."""

    _context: GarminDatasetContext = field(init=False, repr=False)
    _garmin_service: GarminService = field(init=False, repr=False)
    _save_to_db_default: bool = field(init=False)
    _datasets: dict[str, DatasetConfig] = field(init=False, repr=False)

    def __init__(
        self,
        *,
        client: GarminConnectClient,
        garmin_service: GarminService,
        save_to_db_default: bool = True,
        withings_client: WithingsClient | None = None,
    ) -> None:
        object.__setattr__(
            self,
            "_context",
            GarminDatasetContext(client=client, withings=withings_client),
        )
        object.__setattr__(self, "_garmin_service", garmin_service)
        object.__setattr__(self, "_save_to_db_default", save_to_db_default)
        object.__setattr__(self, "_datasets", build_dataset_configs())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def status(self) -> Mapping[str, Any]:
        """Return provider metadata for diagnostics."""

        metadata = self._context.client.metadata()
        metadata["save_to_db_default"] = self._save_to_db_default
        metadata["available_datasets"] = sorted(self._datasets.keys())
        metadata["withings"] = self._withings_metadata()
        return metadata

    async def fetch_dataset(
        self,
        dataset: str,
        query: GarminDataQuery,
        *,
        customer_id: int,
        save_to_db: bool | None = None,
        session: AsyncSession | None = None,
    ) -> DatasetResult:
        """Fetch ``dataset`` from Garmin Connect and optionally persist results."""

        config = self._require_dataset(dataset)
        save_flag = self._resolve_save_flag(save_to_db)

        # Handle database-only queries (skip Garmin API fetch)
        if query.source == DataSource.DATABASE:
            if session is None:
                raise ConfigurationError("Database session required for database-only queries", key="GARMIN_DB_URL")
            items = await self._garmin_service.fetch_dataset(session, dataset, query, customer_id)
            return DatasetResult(
                dataset=dataset,
                items=items,
                raw=[],
                ingested=[],
                saved=False,
            )

        # Standard flow: fetch from Garmin API
        try:
            raw_payloads = await fetch_dataset_raw(dataset, config, self._context, query)
        except Exception as exc:
            logger.error(
                "Failed to fetch Garmin dataset from API",
                exc_info=exc,
                extra={
                    "dataset": dataset,
                    "customer_id": customer_id,
                    "start_date": query.start_date.isoformat() if query.start_date else None,
                    "end_date": query.end_date.isoformat() if query.end_date else None,
                },
            )
            raise

        try:
            translated = list(config.translator(raw_payloads, query))
        except Exception as exc:
            logger.error(
                "Failed to translate Garmin dataset",
                exc_info=exc,
                extra={"dataset": dataset, "customer_id": customer_id, "raw_count": len(raw_payloads) if raw_payloads else 0},
            )
            raise

        if not translated:
            logger.info(
                "Garmin dataset returned no rows",
                extra={"dataset": dataset, "customer_id": customer_id},
            )
            items = []
            return DatasetResult(
                dataset=dataset,
                items=items,
                raw=self._prepare_raw(raw_payloads),
                ingested=[],
                saved=False,
            )

        requests = self._validate_payloads(config.schema, translated)

        ingest_results: list[IngestResult] = []
        saved = False
        if save_flag:
            if session is None:
                raise ConfigurationError("Database session required to persist Garmin data", key="GARMIN_DB_URL")
            ingest_results = await self._ingest(dataset, requests, customer_id, session, config.ingest_method)
            saved = bool(ingest_results)
            items = await self._garmin_service.fetch_dataset(session, dataset, query, customer_id)
        else:
            items = [jsonable_encoder(request.to_internal()) for request in requests]

        return DatasetResult(
            dataset=dataset,
            items=items,
            raw=self._prepare_raw(raw_payloads),
            ingested=ingest_results,
            saved=saved,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _ingest(
        self,
        dataset: str,
        requests: Sequence[GarminRequest],
        customer_id: int,
        session: AsyncSession,
        ingest_method: str | None,
    ) -> list[IngestResult]:
        if ingest_method is None:
            return []

        handler = getattr(self._garmin_service, ingest_method)
        results: list[IngestResult] = []
        for payload in requests:
            result = await handler(session, payload, customer_id)  # type: ignore[arg-type]
            results.append(result)
        return results

    def _validate_payloads(
        self,
        schema: type[GarminRequest],
        payloads: Iterable[Mapping[str, Any]],
    ) -> list[GarminRequest]:
        validated: list[GarminRequest] = []
        for payload in payloads:
            try:
                validated.append(schema.model_validate(payload))
            except Exception as exc:  # pragma: no cover - validation errors surfaced to caller
                raise ValidationError(str(exc)) from exc
        return validated

    def _resolve_save_flag(self, save_to_db: bool | None) -> bool:
        if save_to_db is None:
            return self._save_to_db_default
        return bool(save_to_db)

    def _require_dataset(self, dataset: str) -> DatasetConfig:
        try:
            return self._datasets[dataset]
        except KeyError as exc:  # pragma: no cover - defensive guard
            raise ProviderError(f"Unsupported Garmin dataset '{dataset}'", provider="garmin") from exc

    def _prepare_raw(self, payload: Any) -> list[Any]:
        if payload is None:
            return []
        if isinstance(payload, list):
            return list(payload)
        return [payload]

    def _withings_metadata(self) -> Mapping[str, Any]:
        if not self._context.withings:
            return {"configured": False}
        metadata = dict(self._context.withings.metadata())
        metadata["configured"] = True
        return metadata


__all__ = ["GarminProviderService", "DatasetResult"]

