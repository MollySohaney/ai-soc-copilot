# Architecture Overview

AI SOC Copilot is structured to keep the Streamlit user interface isolated from backend logic so future security-sensitive features can be introduced with minimal coupling.

## Layers

- `api/`: FastAPI HTTP surface exposing versioned endpoints (`/api/v1`); runs as a separate process from the Streamlit app and is not the place for business logic, which stays in `backend/`.
- `api/schemas/`: Pydantic request/response DTOs for the HTTP API, distinct from both the Streamlit view models in `backend/models/` and the SQLAlchemy ORM models in `db/models/`.
- `app/`: Page rendering and shared UI components only.
- `api_client/`: Typed Python HTTP client for the SOC API, sitting between `app/` and `api/`. Framework-agnostic (no Streamlit import) and reuses `api/schemas` models directly for zero type drift; `app/components/api_state.py` is the only module allowed to bridge it into Streamlit.
- `backend/models/`: Typed data contracts passed between services and the UI.
- `backend/security/`: Validation and security-focused controls.
- `backend/parsers/`: File parsing and normalization helpers.
- `backend/ingestion/`: Provider-neutral telemetry ingestion adapters, source-record DTOs, ECS normalization, and restartable orchestration.
- `backend/services/`: Business workflows and orchestration.
- `backend/utils/`: Cross-cutting utilities such as logging.
- `config/`: Centralized runtime configuration.
- `db/`: The persistence layer — SQLAlchemy 2.0 ORM models (`db/models/`), the declarative `Base`, the engine/session factory (`db/session.py`), and the FastAPI `get_db()` dependency. This is where SOC data (events, alerts, cases, detection rules) is defined and stored; it is not the same as `backend/` (Streamlit UI logic) or `api/schemas/` (HTTP DTOs).
- `alembic/`: Database migrations, generated from `db/models`'s metadata.

## Database

PostgreSQL is the system of record for SOC data. For local development:

```bash
docker compose up -d      # start Postgres (postgres:16-alpine, named volume, healthcheck)
alembic upgrade head      # apply migrations
alembic downgrade -1      # roll back one migration, if needed
```

Connection settings are read from `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, and `POSTGRES_PASSWORD` (see `.env.example`), assembled into `config.settings.AppConfig.database_url`. Both `db/session.py` and `alembic/env.py` build their connection from this same setting, so application code and migrations never drift apart.

## Phase 2 API Surface

Phase 2's API surface (`api/v1/endpoints/`, covering events, alerts, cases, dashboard, and detection rules) is backed by PostgreSQL via `db/`, and the Streamlit frontend consumes it through the typed `api_client/` HTTP client rather than talking to the database directly.

## Phase 3 Ingestion Surface

Phase 3 adds `/api/v1/ingestion` endpoints for provider connection tests, bounded manual sync, current status, and run history. The core pipeline is provider-neutral: adapters return source records, the normalizer maps common ECS fields into canonical Event fields, and the orchestrator persists events plus run/checkpoint state.

Elastic configuration is environment-driven and secrets are never returned through API, UI, or logs. Fixture ingestion remains available for deterministic demos without external services.

## Design Principles

- UI should never contain parsing or validation logic.
- Services should compose validators and parsers rather than duplicating their behavior.
- Configuration should load once at startup and be injected into services.
- Logs should remain structured so later ingestion into observability tooling is straightforward.
- Security-sensitive capabilities such as AI access, secrets handling, and external lookups should be added behind dedicated service boundaries.
