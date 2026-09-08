# Telemetry ingestion

**Audience:** anyone connecting a telemetry source or debugging a sync.

A restartable ingestion pipeline with two providers. The in-memory **fixture adapter is
the default**: it needs no external service, no credentials, and no network, and it is
what the demo uses. **Elastic is optional** and is the real-world provider.

Leave `ELASTIC_URL` empty and only the fixture path is reachable. That is the intended
state for a local demo.

## Scope

The ingestion pipeline fetches source records, normalizes common ECS fields into canonical Event fields, preserves raw source payloads, deduplicates by source identity, records run metrics, and advances checkpoints only after successful persistence.

It does not execute detection rules, generate alerts, call AI services, or run remediation.

## Environment variables

Elastic configuration is environment-driven. Do not commit credentials to `.env`, source code, tests, docs, or screenshots.

```bash
ELASTIC_URL=https://elastic.example.com:9200
ELASTIC_INDEX_PATTERN=logs-*
ELASTIC_SOURCE_NAME=elastic-default
ELASTIC_API_KEY=
ELASTIC_USERNAME=
ELASTIC_PASSWORD=
ELASTIC_REQUEST_TIMEOUT_SECONDS=10
ELASTIC_VERIFY_CERTS=true
MAX_INGESTION_SYNC_LIMIT=1000
INGESTION_RETRY_ATTEMPTS=3
INGESTION_RETRY_BACKOFF_SECONDS=0.5
```

Use either `ELASTIC_API_KEY` or `ELASTIC_USERNAME` plus `ELASTIC_PASSWORD`. Prefer API keys with the minimum permissions below.

## Elastic permissions

Use a read-only Elastic principal. The ingestion adapter only needs to test cluster connectivity and run bounded searches over the configured index pattern.

Minimum recommended permissions:

- Cluster: `monitor`
- Index privileges on `ELASTIC_INDEX_PATTERN`: `read`, `view_index_metadata`

Avoid write, manage, delete, ingest pipeline administration, security administration, or superuser roles.

## Authentication and permissions

Every ingestion route requires an authenticated bearer session **and** the
`operate_integrations` permission, which only Admin holds. An Analyst receives
`403 Insufficient permission.` See [docs/permissions.md](permissions.md).

The `curl` examples below therefore need a token:

```bash
TOKEN=$(curl -sS -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d "{\"username\":\"demo-admin\",\"password\":\"$DEMO_PASSWORD\"}" \
  | python -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
```

## Fixture demo

The simplest path is the helper, which logs in and runs ingestion and detection for
you:

```bash
make pipeline
```

To drive the routes directly:

```bash
curl -sS -X POST http://localhost:8000/api/v1/ingestion/fixture/test \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"source_name":"fixture-demo"}'
```

```bash
curl -sS -X POST http://localhost:8000/api/v1/ingestion/fixture/sync \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "source_name": "fixture-demo",
    "start_time": "2026-08-15T00:00:00Z",
    "end_time": "2026-08-16T00:00:00Z",
    "limit": 100,
    "dry_run": false
  }'
```

The fixture adapter serves three records anchored at 2026-08-15 02:00 UTC, the same
anchor `db/seed.py` uses. A first sync reports `fetched=3 persisted=3`. Run it again and
it fetches nothing, because the checkpoint has advanced. That is the restart behaviour
working, not a failure.

Window size is capped by `API_MAX_QUERY_WINDOW_DAYS`, which defaults to 31. Detection
execution has a much tighter cap of its own; see [docs/detections.md](detections.md).

To inspect state:

```bash
curl -sS http://localhost:8000/api/v1/ingestion/status -H "Authorization: Bearer $TOKEN"
curl -sS http://localhost:8000/api/v1/ingestion/runs   -H "Authorization: Bearer $TOKEN"
```

The Streamlit Integrations page exposes the same fixture path through the provider
selector.

## Elastic (optional)

Not required for the demo, and not exercised by CI. Set the Elastic environment
variables first, then start the API:

```bash
export ELASTIC_URL='https://elastic.example.com:9200'
export ELASTIC_INDEX_PATTERN='logs-*'
export ELASTIC_SOURCE_NAME='elastic-lab'
export ELASTIC_API_KEY='REDACTED'
uvicorn api.main:app --reload --port 8000
```

Test the connection:

```bash
curl -sS -X POST http://localhost:8000/api/v1/ingestion/elastic/test \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{}'
```

Run a bounded sync:

```bash
curl -sS -X POST http://localhost:8000/api/v1/ingestion/elastic/sync \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "start_time": "2026-08-15T02:00:00Z",
    "end_time": "2026-08-15T03:00:00Z",
    "limit": 100,
    "dry_run": false
  }'
```

## Limits and retry

Manual sync requests are capped by `MAX_INGESTION_SYNC_LIMIT`. Elastic requests use `ELASTIC_REQUEST_TIMEOUT_SECONDS`. The orchestrator retries transient connection and timeout failures up to `INGESTION_RETRY_ATTEMPTS` with linear backoff from `INGESTION_RETRY_BACKOFF_SECONDS`.

Checkpoints are advanced only after normalized events and run metrics commit successfully.

## Logging

Ingestion logs include provider, source name, run id, status, counts, retry attempts, and checkpoint movement. Logs must not include credentials or raw source payload values.

## Related

- [docs/architecture.md](architecture.md) — where ingestion sits
- [docs/detections.md](detections.md) — what consumes these events
- [docs/permissions.md](permissions.md) — who may run a sync
- [docs/demo.md](demo.md) — the fixture path in context
- [docs/phase3-regression-gate.md](phase3-regression-gate.md) — point-in-time record
