# AI SOC Copilot

AI SOC Copilot is a production-oriented Python application scaffold for SOC analysts who need a clean foundation for AI-assisted alert triage. This repository intentionally focuses on architecture, configuration, logging, and a maintainable Streamlit user experience instead of implementing AI workflows prematurely.

## Highlights

- Python 3.12+ project structure with clear separation of concerns
- Streamlit frontend with sidebar navigation
- Centralized configuration loaded at startup
- Structured JSON logging for application observability
- Modular backend packages for parsers, services, models, utilities, and security
- Placeholder alert upload workflow for JSON, CSV, and TXT files
- Restartable telemetry ingestion scaffold with Elastic and fixture providers
- Test-ready code with type hints and Google-style docstrings

## Project Structure

```text
alembic/
api/
api_client/
app/
backend/
config/
data/
db/
docs/
logs/
tests/
```

## Getting Started

1. Create and activate a Python 3.12+ virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy the example environment file and adjust values if needed:

```bash
cp .env.example .env
```

4. Start PostgreSQL (used by the persistence layer in `db/`):

```bash
docker compose up -d
```

5. Apply database migrations:

```bash
alembic upgrade head
```

6. Seed deterministic demo data (a full SSH brute-force -> valid-login -> privilege-escalation -> persistence attack chain, plus benign noise events, alerts, detection rules, and cases):

```bash
python -m db.seed
```

This command is idempotent: every row is looked up by a natural key before insert, so re-running it against the same database does not create duplicates.

7. Start the Streamlit application and the FastAPI service as two separate local processes:

```bash
uvicorn api.main:app --reload --port 8000
```

```bash
streamlit run app/main.py
```

If the FastAPI service runs on a different host or port, set `API_BASE_URL` in `.env` so the Streamlit frontend's API client (`api_client/`) can reach it — it defaults to `http://localhost:8000`.

## Running Tests

```bash
pytest
```

The suite (137+ tests) spans backend API tests, ORM/DB-constraint tests, seed-idempotency tests, `api_client` tests, and AppTest-based frontend page tests.

## Telemetry Ingestion

Phase 3 introduces bounded telemetry ingestion for normalized events. See [docs/ingestion.md](docs/ingestion.md) for Elastic setup, fixture demo commands, retry/limit settings, and minimum read-only permissions.

## API Documentation

Once the API service is running, FastAPI auto-generates interactive documentation at `http://localhost:8000/docs` (Swagger UI) and `http://localhost:8000/redoc`.

## Demo Analyst Workflow

With the database seeded and both services running, this walkthrough exercises the full API-backed alert-to-case flow:

1. Open the **Dashboard** and note the Critical Alerts card.
2. Go to **Investigations**, filter by severity=Critical, and open **ALERT-0005** ("SSH Authorized Keys Modified for mollysohaney"). ALERT-0006, the correlated chain alert, also appears in this filter — it's part of the same attack narrative, but this walkthrough continues with ALERT-0005 specifically because it has real linked events.
3. Inspect its **Timeline/Evidence** tab (shows 3 linked events) and its **MITRE** tab (T1098.004, Persistence).
4. Change its status to "In Progress" using the status selector and the "Update Status" button.
5. Click **Escalate to Case**.
6. On the new case's detail page, add an analyst note via the **Activity** tab.
7. Update the case's priority.
8. Refresh the browser (or navigate away and back) and confirm the status, note, and priority all persisted — this proves they're backend-persisted through PostgreSQL, not just local Streamlit session state.

## Current Scope

Phase 2 wires the following pages to the FastAPI + PostgreSQL backend as real, persisted workflows:

- Dashboard
- Investigations (Alerts)
- Cases
- Detection Rules

Phase 3 adds telemetry ingestion status and sync controls to Integrations.

The following pages remain UI prototypes on mock data and are not wired this phase:

- MITRE Explorer
- Threat Intelligence
- Reports
- Analyze Alert
- Settings

Out of scope for this phase (deferred to future phases):

- A detection-rule execution engine
- AI/LLM functionality

## Development Notes

- Runtime logs are written to `logs/app.log`.
- Configuration is loaded through `config.settings`.
- Business logic stays in `backend/`; UI rendering stays in `app/`.
- Persistence (SQLAlchemy ORM models, sessions, migrations) lives in `db/` and `alembic/`, separate from `backend/` (Streamlit view models) and `api/schemas/` (HTTP DTOs).
- Tests can be added incrementally under `tests/`.
- Sample upload fixtures are available in `data/`.
- `db/seed.py` provides deterministic demo data (`python -m db.seed`); it derives every timestamp from a fixed constant rather than the current time so repeated clean runs produce identical records.

## Suggested Next Steps

- Add unit tests for parsers, validators, and services
- Introduce persistent storage for alert sessions and reports
- Add authentication, authorization, and audit controls
- Integrate approved AI workflows behind secure service boundaries
