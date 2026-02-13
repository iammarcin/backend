# Garmin Backend Integration Overview

This document captures the current Garmin implementation in the new FastAPI backend, covering request flow, dependency wiring, persistence, automation, and the key differences from the legacy stack and supporting scripts.

## High-Level Architecture

- **GarminConnectClient** wraps the third-party `garth` client, centralising session storage, retry policy, re-authentication, and error translation so feature code only coordinates dataset orchestration.[F:docker/storage-backend/core/providers/garmin/client.py L1-L142]
- **GarminProviderService** pulls raw datasets from Garmin (and optionally Withings), translates payloads, validates them with Pydantic schemas, persists through the database service when requested, and returns both cleaned items and ingest metadata.[F:docker/storage-backend/features/garmin/service.py L1-L275]
- **GarminService** composes ingestion and retrieval mixins with repository instances and a central dataset registry, exposing helper methods for request validation, transactional execution, and dataset lookups.[F:docker/storage-backend/features/db/garmin/service.py L1-L69][F:docker/storage-backend/features/db/garmin/ingestion.py L1-L192][F:docker/storage-backend/features/db/garmin/retrieval.py L1-L185][F:docker/storage-backend/features/db/garmin/datasets.py L1-L191]
- **FastAPI routes** under `/api/v1/garmin` provide RESTful access to sleep, summary, body-composition, status, and analysis endpoints, handling error envelopes consistently and supporting optional persistence via `save_to_db` and managed DB sessions.[F:docker/storage-backend/features/garmin/routes.py L1-L186]

## Dependency Wiring & Configuration

- `get_garmin_provider_service` constructs a singleton provider service using environment-driven settings (session path, credentials, retry policy, default persistence flag) and lazily injects Withings support when fully configured.[F:docker/storage-backend/features/garmin/dependencies.py L1-L156][F:docker/storage-backend/features/garmin/settings.py L1-L130]
- `get_garmin_session` defers creation of the async MySQL dependency until `GARMIN_DB_URL` is available; if the URL is missing the dependency yields `None` so routes can return structured configuration errors without failing app startup.[F:docker/storage-backend/features/garmin/dependencies.py L38-L127]
- The provider defaults to persisting results unless `save_to_db` overrides the flag. When persistence is requested a database session is mandatory; otherwise the service returns validated payloads without touching the DB.[F:docker/storage-backend/features/garmin/service.py L104-L154]
- Withings is optional: the provider surface reports configuration status and enriches body-composition payloads only when a fully initialised client is available.[F:docker/storage-backend/features/garmin/service.py L95-L194][F:docker/storage-backend/features/garmin/dependencies.py L130-L156]

## API Surface & Query Model

- `/status` exposes client metadata, enabled datasets, default persistence behaviour, and Withings configuration so operators can quickly verify wiring.[F:docker/storage-backend/features/garmin/routes.py L22-L89][F:docker/storage-backend/features/garmin/service.py L95-L153]
- `/sleep`, `/summary`, and `/body-composition` accept a shared `GarminDataQuery`, require `customer_id`, and optionally persist fetched items before re-querying the database for canonical rows.[F:docker/storage-backend/features/garmin/routes.py L92-L135][F:docker/storage-backend/features/garmin/service.py L104-L154]
- `/analysis/overview` requires a DB session, aggregates multiple datasets (defaulting to summary, body composition, sleep, HRV, training readiness/endurance/status, and activity), and can return an “optimized” bundle for dashboards.[F:docker/storage-backend/features/garmin/routes.py L136-L176][F:docker/storage-backend/features/db/garmin/datasets.py L82-L184][F:docker/storage-backend/features/db/garmin/retrieval.py L99-L121]
- `GarminDataQuery` normalises date bounds, sort order, pagination, correlation mode, and dataset-specific toggles (`ignore_null_vo2max`, `activity_id`, etc.), matching both camelCase and snake_case aliases for backwards compatibility.[F:docker/storage-backend/features/garmin/schemas/queries.py L1-L84]

## Persistence & Dataset Registry

- The dataset registry enumerates every Garmin table, its repository attribute, fetch method, display label, next-day adjustments, and any extra parameters. Public routes currently expose three datasets, but ingestion/retrieval helpers cover HRV, training readiness/endurance/status, fitness age, activity metadata, GPS tracks, and daily health events for scheduled jobs or future endpoints.[F:docker/storage-backend/features/garmin/service.py L234-L275][F:docker/storage-backend/features/db/garmin/datasets.py L82-L191][F:docker/storage-backend/features/db/garmin/ingestion.py L41-L189]
- Retrieval helpers apply date-window corrections for “next day” tables, fan out to repositories with pagination and filter controls, and optionally compute optimized health aggregates for dashboard consumers.[F:docker/storage-backend/features/db/garmin/retrieval.py L50-L121]
- Ingest helpers perform idempotent upserts per dataset, capturing lightweight metrics (e.g., nap segments, readiness scores, GPS point counts) to include in API metadata and logs.[F:docker/storage-backend/features/db/garmin/ingestion.py L41-L189]

## Background Automation

- `run_nightly_sync` iterates the default dataset trio (sleep, summary, body composition) for a target date, forcing persistence and returning per-dataset status summaries suitable for schedulers. `build_nightly_sync_job` wraps the coroutine for APScheduler/Celery registration.[F:docker/storage-backend/features/garmin/tasks.py L1-L88]
- `python/garmin/update-garmin-data.py` wraps `run_nightly_sync`, performs an `/api/v1/garmin/status` pre-flight check, optionally verifies `/analysis/overview`, and emits JSON lines for each dataset plus a consolidated summary that can be written to disk via `--summary-file`. Flags such as `--date`, repeated `--dataset`, `--analysis-check`, and `--skip-status-check` allow tailored automation runs while still failing fast on configuration issues.[F:python/garmin/update-garmin-data.py L1-L211]
- `python/garmin/garmin_cron_sync.sh` drives the nightly job: it reads overrides from `GARMIN_CRON_*` environment variables, defaults to the previous calendar day when no target is supplied, rotates log/summary files under `GARMIN_LOG_DIR`, and exits with the Python script's status so schedulers can alert on ingestion failures.[F:python/garmin/garmin_cron_sync.sh L1-L76]

## Differences from the Legacy Workflow

- Legacy scripts (e.g., `python/garmin/garminHelper.py`) still POST to `/api/garmin` with action strings and route results through `/api/db` insert actions such as `insert_sleep_data` and `insert_training_status`. They expect the backend to branch on `action` names and manually transform certain datasets before storage.[F:python/garmin/garminHelper.py L7-L188]
- The new backend exposes RESTful GET endpoints with typed query parameters instead of action-based POSTs. Persistence happens inside the provider service through repository upserts, and aggregated reads surface through `/api/v1/garmin/analysis/overview` instead of `/api/db` fetch actions.[F:docker/storage-backend/features/garmin/routes.py L92-L176][F:docker/storage-backend/features/garmin/service.py L104-L154][F:docker/storage-backend/features/db/garmin/retrieval.py L50-L121]
- Several datasets covered by the new ingestion/retrieval mixins (training readiness, HRV, endurance, etc.) lack public endpoints today; they are accessible programmatically via scheduled jobs or future router additions.[F:docker/storage-backend/features/garmin/service.py L234-L275][F:docker/storage-backend/features/db/garmin/datasets.py L82-L184]

## Impact on Existing Tooling

- Scripts that currently call `/api/garmin` or `/api/db` must migrate to the new REST endpoints, include `customer_id` (and optionally `save_to_db`), and adjust to the JSON envelope returned by `api_ok` with `data`/`meta` sections.[F:docker/storage-backend/features/garmin/routes.py L54-L176][F:python/garmin/garminHelper.py L14-L188]
- Database writes now require the Garmin DB URL to be configured for the FastAPI container; otherwise the routes respond with a structured configuration error instead of silently failing.[F:docker/storage-backend/features/garmin/dependencies.py L38-L127][F:docker/storage-backend/features/garmin/routes.py L136-L176]
- To mirror the old end-to-end flow, use `run_nightly_sync` (or its job wrapper) to fetch and persist the default datasets on a schedule, then query `/analysis/overview` for combined dashboards.[F:docker/storage-backend/features/garmin/tasks.py L16-L88][F:docker/storage-backend/features/garmin/routes.py L136-L176]
- Operators should run `update-garmin-data.py --analysis-check --summary-file <path>` (or the cron wrapper) to capture the JSON summary, then verify health by calling `/api/v1/garmin/status` and `/api/v1/garmin/analysis/overview` for the target date. The summary file contains per-dataset `items` and `saved` counts, streamlining log shipping and dashboard validation.[F:python/garmin/update-garmin-data.py L24-L211][F:python/garmin/garmin_cron_sync.sh L1-L76]

