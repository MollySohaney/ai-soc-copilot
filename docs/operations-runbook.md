# Operations and recovery runbook

## Startup and access

Run migrations before starting the API: `python -m alembic upgrade head`.
Create a local analyst with `DEMO_PASSWORD` in the process environment and
`python -m db.bootstrap_user --username demo-analyst --role analyst`; the
command is idempotent and never changes an existing password. Check `/health`
for liveness and `/ready` for database readiness.

## Database backup and restore

Use PostgreSQL custom format so schema, data, identities, audit history, and
relationships are captured: `pg_dump --format=custom --file=backup.dump
"$DATABASE_URL"`. Keep the file mode 600, outside the repository, and record
`pg_dump --version`, PostgreSQL server version, migration revision, and elapsed
time. Restore into an empty disposable database with
`createdb ...` followed by `pg_restore --clean --if-exists --no-owner --dbname
"$DATABASE_URL" backup.dump`; never put passwords in command arguments (use
`PGPASSWORD` only in a protected process environment or `.pgpass`). Run
`alembic upgrade head`, `/ready`, and an authorized Analyst investigation smoke
test after restore.

## Reset/reseed

`ENVIRONMENT=demo python -m db.reset_demo --database-name ai_soc_copilot_demo
--confirm-database ai_soc_copilot_demo` is intentionally explicit. It refuses
non-local environments and mismatched database names, deletes only application
rows, then runs the deterministic idempotent seed. No password is committed;
bootstrap users separately with an interactive prompt or `DEMO_PASSWORD`.

## Troubleshooting and escalation

Migration failures: stop writes, inspect `alembic current`, and restore the
latest verified dump before escalating. A failed `/ready` means PostgreSQL is
unavailable or migrations are incomplete. Elastic and AI outages are isolated:
use fixture data, retry with bounded timeouts, and inspect audit events. A
stuck or rate-limited job should be retried with its idempotency key; do not
manually duplicate mutations. Investigate security-relevant changes in the
append-only audit table and correlate operational logs by request ID.

## Logs and collection

Prefer JSON stdout under a process supervisor; file logging writes `logs/app.log`.
Rotate daily or at 100 MB, retain 14 days (audit retention is governed by
policy), and use owner-readable permissions. Never log passwords, tokens,
provider payloads, or raw sensitive event fields. Collect a bounded time window
with request IDs and redact before sharing. Validate redaction with canary
values such as `CANARY_SECRET_DO_NOT_LOG`; if present, treat it as an incident.
Disk exhaustion requires stopping file logging or expanding the volume before
restarting. Roll back code only after preserving audit/log evidence and
confirming migration compatibility.

## Recovery proof (2026-09-02)

On disposable PostgreSQL database `ai_soc_copilot_recovery_20260902`, the
following was executed: migrate to head, `python -m db.seed` twice, counted
events/alerts/cases/rules/users/audit rows, `pg_dump --format=custom`, reset and
reseed, dropped/recreated the database, `pg_restore`, migrate/check, readiness,
and an Analyst alert-to-case smoke request. Counts and relationships matched;
the seed was idempotent. Cleanup removed only that uniquely named database and
dump file. Commands were run with PostgreSQL 16 and Alembic head
`e1f2a3b4c5d6`; secrets were supplied through protected environment variables.
