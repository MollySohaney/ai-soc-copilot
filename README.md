# AI SOC Copilot

AI SOC Copilot is a production-oriented Python application scaffold for SOC analysts who need a clean foundation for AI-assisted alert triage. This repository intentionally focuses on architecture, configuration, logging, and a maintainable Streamlit user experience instead of implementing AI workflows prematurely.

## Highlights

- Python 3.12+ project structure with clear separation of concerns
- Streamlit frontend with sidebar navigation
- Centralized configuration loaded at startup
- Structured JSON logging for application observability
- Modular backend packages for parsers, services, models, utilities, and security
- Placeholder alert upload workflow for JSON, CSV, and TXT files
- Test-ready code with type hints and Google-style docstrings

## Project Structure

```text
alembic/
api/
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

4. Start the Streamlit application and the FastAPI service as two separate local processes:

```bash
streamlit run app/main.py
```

```bash
uvicorn api.main:app --reload --port 8000
```

5. Start PostgreSQL (used by the persistence layer in `db/`):

```bash
docker compose up -d
```

6. Apply database migrations:

```bash
alembic upgrade head
```

7. Seed deterministic demo data (a full SSH brute-force -> valid-login -> privilege-escalation -> persistence attack chain, plus benign noise events, alerts, detection rules, and cases):

```bash
python -m db.seed
```

This command is idempotent: every row is looked up by a natural key before insert, so re-running it against the same database does not create duplicates.

## Current Scope

This scaffold includes:

- Dashboard page
- Analyze Alert page with upload placeholder
- MITRE Explorer placeholder page
- Reports placeholder page
- Settings page

This scaffold does not yet include:

- AI alert analysis
- MITRE ATT&CK lookups
- Threat intelligence enrichment
- Authentication or RBAC

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
