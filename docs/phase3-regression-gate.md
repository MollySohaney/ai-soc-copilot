# Phase 3 Regression Gate

This gate was run on 2026-08-31 from branch `phase3-regression-gate`.

## Database Upgrade

An isolated PostgreSQL 16 container was started on host port `55432`. The
existing Phase 2 schema was applied with revision `88a1df0e92a3`, upgraded to
head (`3baf1c2d7e90`), and then seeded twice:

```bash
COMPOSE_PROJECT_NAME=ai_soc_copilot_phase3_gate POSTGRES_PORT=55432 docker compose up -d
POSTGRES_PORT=55432 alembic upgrade 88a1df0e92a3
POSTGRES_PORT=55432 alembic upgrade head
POSTGRES_PORT=55432 python -m db.seed
POSTGRES_PORT=55432 python -m db.seed
```

The second seed remained idempotent; the database contained `60` events after
both runs. The Phase 2 ORM cannot seed while the database is still at the old
revision because the current seed module loads the Phase 3 model fields. An
existing Phase 2 database must therefore be migrated to head before running
the current seed command.

A separate populated Phase 2 database was also upgraded. A legacy event was
inserted before the migration and remained intact afterward with its original
`event_id`, source, and message.

## Application Smoke

FastAPI and Streamlit were launched against the isolated database:

```bash
POSTGRES_PORT=55432 uvicorn api.main:app --host 127.0.0.1 --port 8001
POSTGRES_PORT=55432 API_BASE_URL=http://127.0.0.1:8001 streamlit run app/main.py --server.address 127.0.0.1 --server.port 8503
```

FastAPI health and the fixture connection test returned HTTP success. A
fixture sync persisted `3` events and advanced its checkpoint. Repeating the
same bounded sync fetched `0` records from the checkpoint, persisted `0`, and
left the event total at `63` after the initial `60` seeded events.

## Tests

```text
pytest -> 196 passed in 8.91s
```

No detection execution, alert generation, AI calls, or remediation behavior
was added by Phase 3.
