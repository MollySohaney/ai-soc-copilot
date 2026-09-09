# Development

**Audience:** anyone changing the code.

For running the demo rather than changing it, start at the
[README](../README.md) and [docs/demo.md](demo.md).

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
make setup
```

CI runs Python 3.12. The suite also passes on 3.14. `requirements.txt` pins every
dependency exactly, including `pytest`, so one install covers running and testing.

## Two processes

```bash
make api    # FastAPI on :8000
make ui     # Streamlit on :8501
```

They are separate processes on purpose. Streamlit never touches the database; it goes
through `api_client/` over HTTP. If `API_BASE_URL` does not match where the API is
listening, the UI loads and every data call fails.

## Layout

| Directory | Holds | Never holds |
|---|---|---|
| `app/` | Streamlit views and components | Parsing, validation, business logic |
| `api_client/` | Typed HTTP client | Any Streamlit import |
| `api/` | Routes, middleware, HTTP schemas | Business logic |
| `backend/` | Workflows: ingestion, detection, AI, audit, security | HTTP or UI concerns |
| `db/` | ORM models, session, seed, bootstrap | View models or HTTP DTOs |
| `alembic/` | Migrations generated from `db/models` | Hand-written schema drift |
| `scripts/` | Operator helpers | Anything the API cannot already do |

Three model layers exist and they are not interchangeable: `db/models/` is SQLAlchemy
ORM, `api/schemas/` is HTTP request and response DTOs, and `backend/models/` is typed
contracts between services and the UI.

`api_client/` reuses `api/schemas` models directly, so the frontend and backend cannot
drift. `app/components/api_state.py` is the only module allowed to bridge the client
into Streamlit.

## Tests

```bash
make test                                   # everything
pytest tests/test_detection_engine.py       # one file
pytest -k "rbac or audit"                   # by name
pytest -x -q                                # stop at the first failure
```

Tests run against in-memory SQLite seeded with the real demo dataset, with the app's
`get_db` dependency overridden. They exercise real endpoint and schema code rather than
mocks. Fixtures live in `tests/conftest.py`:

| Fixture | Gives you |
|---|---|
| `db_session` | Seeded session, plus an Admin with a pre-issued token |
| `client` | `TestClient` already carrying that bearer token |
| `anonymous_client` | Unauthenticated client, for login and denial tests |
| `api_client_transport` | `httpx.Client` wired into the app, for `api_client/` tests |

Streamlit pages are tested through AppTest, with the driver scripts in
`tests/_apptest_scripts/`.

Two conventions worth keeping. Assert on the message a failure produces, not only on
its status code, because those messages are what a reader acts on. And when a change
touches permissions, add the negative test, because a permission that is never denied
in a test is a permission nobody has checked.

## Migrations

```bash
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
alembic downgrade -1     # confirm it reverses
alembic check            # confirm no drift from db/models
```

CI runs upgrade, then downgrade and re-upgrade, then `alembic check`. A migration that
cannot reverse fails there, so check it locally first.

Both `db/session.py` and `alembic/env.py` build their URL from
`config.settings.AppConfig.database_url`, so migrations and the application always
agree on the target.

## Seed and reset

`db/seed.py` is deterministic: every timestamp derives from `BASE_TIME`, and every row
is looked up by a natural key before insert. Re-running changes nothing.

Documentation cites specific records such as `ALERT-0005` and `CASE-2026-0004`. Adding
seed rows before existing ones shifts case numbers, so add at the end, or update
[docs/demo.md](demo.md) when you do not.

```bash
make reset    # delete every application row and reseed
```

`reset` refuses unless `ENVIRONMENT`, or `APP_ENV` when that is unset, is
`development`, `demo`, `test`, or `local`, and it requires the database name typed back
to it.

## Configuration

Every setting flows through `config/settings.py`, loaded once and validated by Pydantic.
Adding a variable means adding the field, the `os.getenv` read, a validator if it has
bounds, and a line in `.env.example`. Add it to `to_safe_dict`'s exclusion list if it is
a secret.

Four variables are read outside `config.settings`, all deliberately:
`ENVIRONMENT` and `POSTGRES_DB` in `db/reset_demo.py`, `DEMO_USERNAME` and
`DEMO_PASSWORD` in `db/bootstrap_user.py`. Nothing else should read the environment
directly.

## Conventions

Every module opens with a one-line `"""Purpose: ..."""` docstring. Public functions
carry Google-style docstrings with type hints. Business logic composes validators and
parsers rather than re-implementing them.

Passwords and tokens are read from the process environment, never from a command-line
argument, and never printed or logged.

## Committing

Commit each logical step separately, with the reasoning in the body rather than a
restatement of the diff. Run the focused tests for what you touched, then the full
suite, then inspect the diff before committing.

## Before opening a pull request

```bash
python -m compileall -q api api_client app backend config db scripts tests
alembic upgrade head && alembic downgrade -1 && alembic upgrade head
alembic check
pytest -q
pip-audit -r requirements.txt
```

That is what CI runs, minus the gitleaks scan. Details in [docs/ci.md](ci.md).

## Related

- [docs/architecture.md](architecture.md) — layer boundaries and request path
- [docs/detections.md](detections.md) — authoring and executing rules
- [docs/ingestion.md](ingestion.md) — adapters and normalisation
- [docs/ai-safety.md](ai-safety.md) — the AI boundary
- [docs/operations-runbook.md](operations-runbook.md) — recovery
- [docs/release-readiness.md](release-readiness.md) — known gaps
