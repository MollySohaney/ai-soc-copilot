# Telemetry Ingestion

Phase 3 adds a restartable telemetry ingestion pipeline. The first real provider is Elastic, and a deterministic fixture provider is available for tests and demos.

## Scope

The ingestion pipeline fetches source records, normalizes common ECS fields into canonical Event fields, preserves raw source payloads, deduplicates by source identity, records run metrics, and advances checkpoints only after successful persistence.

It does not execute detection rules, generate alerts, call AI services, or run remediation.

## Environment Variables

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

## Elastic Permissions

Use a read-only Elastic principal. The ingestion adapter only needs to test cluster connectivity and run bounded searches over the configured index pattern.

Minimum recommended permissions:

- Cluster: `monitor`
- Index privileges on `ELASTIC_INDEX_PATTERN`: `read`, `view_index_metadata`

Avoid write, manage, delete, ingest pipeline administration, security administration, or superuser roles.

## Fixture Demo

The fixture provider requires no external services or credentials. With PostgreSQL, API, and Streamlit running:

```bash
curl -sS -X POST http://localhost:8000/api/v1/ingestion/fixture/test \
  -H 'Content-Type: application/json' \
  -d '{"source_name":"fixture-demo"}'
```

```bash
curl -sS -X POST http://localhost:8000/api/v1/ingestion/fixture/sync \
  -H 'Content-Type: application/json' \
  -d '{
    "source_name": "fixture-demo",
    "start_time": "2026-08-15T02:00:00Z",
    "end_time": "2026-08-15T04:00:00Z",
    "limit": 100,
    "dry_run": false
  }'
```

Run the same sync again to verify checkpointed restart behavior. To inspect status:

```bash
curl -sS http://localhost:8000/api/v1/ingestion/status
curl -sS http://localhost:8000/api/v1/ingestion/runs
```

The Streamlit Integrations page exposes the same fixture path through the provider selector.

## Elastic Demo

Set Elastic environment variables first, then start the API:

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
  -H 'Content-Type: application/json' \
  -d '{}'
```

Run a bounded sync:

```bash
curl -sS -X POST http://localhost:8000/api/v1/ingestion/elastic/sync \
  -H 'Content-Type: application/json' \
  -d '{
    "start_time": "2026-08-15T02:00:00Z",
    "end_time": "2026-08-15T03:00:00Z",
    "limit": 100,
    "dry_run": false
  }'
```

## Limits And Retry

Manual sync requests are capped by `MAX_INGESTION_SYNC_LIMIT`. Elastic requests use `ELASTIC_REQUEST_TIMEOUT_SECONDS`. The orchestrator retries transient connection and timeout failures up to `INGESTION_RETRY_ATTEMPTS` with linear backoff from `INGESTION_RETRY_BACKOFF_SECONDS`.

Checkpoints are advanced only after normalized events and run metrics commit successfully.

## Logging

Ingestion logs include provider, source name, run id, status, counts, retry attempts, and checkpoint movement. Logs must not include credentials or raw source payload values.
