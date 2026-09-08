# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Entries before `Unreleased` were reconstructed from merged pull requests and the phase
regression-gate records, and are grouped by the phase that delivered them rather than by
a tagged release. No release has been tagged yet.

## [Unreleased]

Phase 7: portfolio demonstration, documentation, and release preparation. No product
features were added.

### Added

- `docs/release-readiness.md`, an audit of the repository as a first-time reader
  encounters it
- `docs/demo.md`, the end-to-end narrative from telemetry to a documented case
- `docs/ai-safety.md`, `docs/detections.md`, and `docs/development.md`
- `docs/images/` and a screenshot capture guide with a secret-hygiene checklist
- `scripts/smoke.py`, a one-command stack health check that names the fix for whichever
  check fails and exits non-zero
- `scripts/demo_pipeline.py`, which drives fixture ingestion and detection execution
  over the API, neither of which had a command-line entry point
- A `Makefile` wrapping the documented commands
- This changelog

### Changed

- `.env.example` now defaults to `AI_ENABLED=true` with `AI_PROVIDER=fake`. The previous
  default made every AI action return "unavailable", which read as a broken feature
  rather than a safe one
- `.env.example` documents `ENVIRONMENT`, the `POSTGRES_PORT` collision with a system
  PostgreSQL, the empty `ELASTIC_URL` contract, and why the demo account is an Admin
- `DEMO_USERNAME` defaults to `demo-admin`, because the demo narrative spans four
  permissions and only Admin holds all of them
- `README.md` rewritten as a technical landing page. It previously described a Phase 2
  scaffold and listed the detection engine and AI functionality as out of scope
- `docs/architecture.md` extended from Phase 3 through Phase 6
- `docs/ingestion.md` presents the fixture adapter as the default, and its examples now
  send the `Authorization` header that Phase 6 made mandatory
- The four phase regression gates are marked as point-in-time historical records
- `db/reset_demo.py` falls back to `APP_ENV` when `ENVIRONMENT` is unset

### Fixed

- The fake AI provider returned triage-shaped output for every workflow, so case
  question answering and report drafting both failed schema validation on the default
  demo path. It now returns output shaped for whichever workflow asked

### Removed

- `.idea/` JetBrains project files, which were tracked but editor-local

## Phase 6 — Security, reliability, and operational hardening — 2026-09-06

### Added

- Local authentication with argon2 hashing and opaque bearer sessions; PostgreSQL stores
  only a SHA-256 digest of each token
- Server-enforced RBAC across Viewer, Analyst, Detection Engineer, and Admin, from a
  single permission matrix, checked before resource lookup
- Append-only audit events with actor attribution and secret redaction, recording
  failures and denials as well as successes
- Request boundaries: body size cap enforced during receipt, request-target validation,
  and explicit CORS origins
- Rate and concurrency limits on the login, AI, ingestion, and detection paths
- Actor-scoped idempotency keys, and a PostgreSQL advisory lock for case-number
  allocation
- Liveness and readiness endpoints that distinguish process health from dependency
  health
- CI against a real PostgreSQL service, with migration downgrade and re-upgrade,
  `alembic check` drift detection, `pip-audit`, and a gitleaks scan
- `db/reset_demo.py`, and backup and restore procedures
- `docs/threat-model.md`, `docs/permissions.md`, `docs/api-security.md`,
  `docs/reliability-inventory.md`, `docs/operations-runbook.md`, `docs/ci.md`

## Phase 5 — Evidence-grounded AI assistance — 2026-09-02

### Added

- An AI provider abstraction with a deterministic fake provider and a fail-closed
  unavailable provider
- Bounded evidence context assembly from alerts, events, MITRE mappings, and analyst
  notes, each item carrying a stable evidence identifier
- Versioned response schemas with citation enforcement: output referencing evidence
  outside the supplied context is rejected
- Prompt-injection defences treating all event content as untrusted data
- Alert triage, case-scoped question answering, and report drafting, each persisted with
  provider, model, prompt version, schema version, and latency

## Phase 4 — Detection and correlation engine — 2026-09-02

### Added

- A structured rule DSL with single-event, threshold, and sequence evaluators
- Deterministic execution over `events.timestamp`, with bounded candidate scans and
  observable truncation
- Rule versioning, with each version's exact logic preserved
- Alert fingerprints making replay a no-op, and durable detection run records
- A seeded rule pack covering the demo attack chain

## Phase 3 — Telemetry ingestion and normalization — 2026-09-01

### Added

- A provider-neutral ingestion pipeline: adapters, ECS normalization, and a restartable
  orchestrator
- An Elastic adapter and a deterministic in-memory fixture adapter
- Checkpointed, idempotent syncs that advance only after a successful commit
- Bounded sync limits with retry and backoff
- Ingestion endpoints and Integrations UI controls

## Phase 2 — Backend, database, API, and frontend integration — 2026-08-20

### Added

- A versioned FastAPI service at `/api/v1`
- PostgreSQL persistence with SQLAlchemy 2.0 models and Alembic migrations
- A deterministic demo dataset covering a full SSH brute force to persistence attack
  chain, plus benign noise
- Endpoints for events, alerts, cases, dashboard, and detection rules
- A typed `api_client/` reusing the API's own schemas
- Dashboard, Investigations, Cases, and Detection Rules wired to the API

## Phase 1 — Scaffold — 2026-07-14

### Added

- Project structure, centralized configuration, structured JSON logging, a Streamlit
  frontend, and file upload parsers
