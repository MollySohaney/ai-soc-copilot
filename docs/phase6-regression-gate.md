# Phase 6 security regression gate

Executed 2026-09-02 against the stacked Phase 6 history. No product behavior
changes were made in this gate.

## Ordered implementation commits

| Step | Commit | PR |
| --- | --- | --- |
| 1 threat model | `766f3ec`, integrated/current in `62eb3dd` | #100/#108 |
| 2 auth/sessions | `1feac44` | #101 |
| 3 RBAC | `30bb0e3` | #102 |
| 4 audit events | `a3c1242` | #103 |
| 5 API hardening | `d02a3e8` | #104 |
| 6 reliability/idempotency | `64c29b2` | #105 |
| 7 CI/scanning | `b452421` | #106 |
| 8 recovery/runbooks | `d793024` | #107 |
| 9 regression gate | this commit | this PR |

Follow-up commit `dd698b8` upgrades vulnerable dependencies, repairs full-history
secret scanning, and keeps anonymous-route enumeration compatible with the
upgraded FastAPI router.

## Verification

`pytest -q` (336 passed), `git diff --check`, Python compileall, and the
PostgreSQL migration lifecycle (`upgrade head`, `downgrade -1`, re-upgrade,
`alembic check`) passed. Focused security suites cover auth/session expiry,
negative RBAC permissions for every sensitive endpoint family, audit redaction,
request/file bounds, rate limits, idempotency/concurrency, readiness, and
prompt-injection behavior. The seeded Analyst attack investigation remains
covered by the API/UI regression tests; Viewer and anonymous negative paths are
explicitly asserted as 401/403.

The final CI run is
[`33617463840`](https://github.com/MollySohaney/ai-soc-copilot/actions/runs/33617463840).
Its PostgreSQL service, compile/migration/pytest, pip-audit, and Gitleaks jobs
are required checks.

## Role matrix

Viewer: read-only SOC data. Analyst: alert/case/activity mutations and AI
requests. Detection Engineer: detection validation, authoring, and execution.
Admin: all capabilities, integrations, user/session administration, and audit
read access. Enforcement is server-side; UI hiding is advisory.

| Representative operation | Anonymous | Viewer | Analyst | Detection Engineer | Admin |
| --- | --- | --- | --- | --- | --- |
| Read SOC records | 401 | Allow | Allow | Allow | Allow |
| Mutate alerts/cases | 401 | 403 | Allow | 403 | Allow |
| Request AI | 401 | 403 | Allow | 403 | Allow |
| Manage/execute rules | 401 | 403 | 403 | Allow | Allow |
| Operate integrations | 401 | 403 | 403 | 403 | Allow |
| Manage users/read audit | 401 | 403 | 403 | 403 | Allow |

Direct API permission tests and Streamlit AppTest role-control tests passed in
the focused 87-test security run. Service-layer bypass attempts are rejected
independently of UI and route dependencies.

## Schema and environment

Migrations through `e1f2a3b4c5d6` add users/sessions, roles, audit events, and
idempotency records. Relevant controls are `AUTH_SESSION_IDLE_MINUTES`,
`AUTH_SESSION_ABSOLUTE_HOURS`, login/AI/ingestion/detection rate and concurrency
limits, `API_MAX_BODY_BYTES`, upload/query caps, provider timeout/retry values,
and `AI_ENABLED`/provider credentials. Secrets are environment-only.

## Security and outage evidence

- `pytest -q`: 336 passed.
- Focused auth, RBAC, Streamlit role, audit, HTTP-boundary, reliability,
  provider-outage, prompt-injection, and investigation tests: 87 passed.
- `pip-audit -r requirements.txt`: no known vulnerabilities found after
  upgrading pytest 9.0.3, FastAPI 0.141.1, and Starlette 1.3.1.
- Gitleaks 8.24.3 full-history scan: 61 commits, about 982 KB, no leaks found.
- Canary tests inject password, API-key, token, prompt, raw-evidence, database,
  and provider-error values. API/error/config/AI/audit assertions confirm they
  are absent or replaced by `[REDACTED]`; test-only canaries are explicitly
  allowlisted only under `tests/`.
- PostgreSQL unavailable returns generic readiness 503 and recovers without
  changing liveness. Elastic timeout/connection and AI unavailable/error paths
  remain isolated from deterministic SOC pages and do not mutate findings.
- Prompt-injection tests preserve untrusted-data labeling, reject fabricated or
  cross-case citations, bound context, redact secrets, and leave AI advisory.

## Recovery and accepted risks

The Step 8 disposable proof restored 60 events, 13 alerts, 3 cases, and 5
detection rules using PostgreSQL 16 `pg_dump -Fc`/`pg_restore`; readiness and
Alembic drift checks passed. Optional Elastic/AI outages are isolated and
advisory AI remains evidence-scoped. Remaining risks: local deployments still
need operator-managed TLS, secret rotation, backup retention, and external
monitoring; Gitleaks action upgrades and dependency advisories require review.
Owners: deployment operator; review on each dependency/action update or
security incident.
