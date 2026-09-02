# AI SOC Copilot threat model

**Architecture snapshot:** 2026-09-02
**Scope:** Local portfolio deployment of the Streamlit application, FastAPI API,
PostgreSQL persistence, telemetry ingestion, deterministic detections, and
optional advisory AI assistance.

This document describes the hardened Phase 6 architecture. Remaining accepted
risks are explicit below. The implementation issues are tracked under
[Phase 6 issue #90](https://github.com/MollySohaney/ai-soc-copilot/issues/90).

## Security objectives

1. Only authenticated users can access SOC data, and every authorization
   decision is enforced by FastAPI and the service layer.
2. Viewer, Analyst, Detection Engineer, and Admin capabilities follow least
   privilege. Hiding a Streamlit widget is not authorization.
3. Credentials, integration keys, session material, and other secrets never
   appear in plaintext application persistence, source control, logs, API
   responses, or UI output.
4. Security-relevant changes are attributable and recorded in append-only audit
   events.
5. Untrusted uploaded and ingested content cannot become code, instructions, or
   cross-investigation AI context.
6. Expensive work is bounded, idempotent where appropriate, and resilient to
   retries, concurrency, and provider outages.
7. PostgreSQL data and operational evidence can be recovered using a tested
   procedure.

## Architecture and data flows

```text
Analyst browser
    |
    | HTTP to local Streamlit (:8501)
    v
Streamlit UI  ---- local upload/paste ----> parser and upload validator
    |
    | typed api_client over HTTP
    v
FastAPI /api/v1 (:8000)
    |
    +---- SQLAlchemy/Alembic ----> PostgreSQL (:5432)
    |
    +---- bounded adapter request ----> Elasticsearch (optional)
    |
    +---- bounded evidence prompt ----> AI provider (optional; fake only today)
    |
    +---- structured operational logs ----> console and logs/app.log
```

The browser communicates with Streamlit. Streamlit holds page state and uses a
cached `httpx.Client` from `app/components/api_state.py` to call the versioned
FastAPI API. It does not access PostgreSQL directly. FastAPI routes use the
`db.get_db` dependency and SQLAlchemy services/models. Alembic manages schema
changes, and `db.seed` creates deterministic demo records.

The Analyze Alert prototype accepts JSON, CSV, or text into the Streamlit
process and invokes `AlertUploadService`; it is not the persisted ingestion
path. The ingestion API invokes either a deterministic fixture adapter or an
Elasticsearch adapter. The adapter normalizes source records and stores both
selected normalized fields and raw source payloads.

Detection execution reads persisted rules and events, stores run provenance,
and can create alerts. AI triage, case Q&A, and report endpoints construct
bounded alert- or case-scoped evidence, mark raw evidence as untrusted, redact
common secret patterns, validate structured results and citations, and persist
`AIAnalysis` results. The only implemented provider is deterministic fake;
unsupported or unavailable providers fail closed.

The API requires opaque authenticated sessions for protected routers, applies
central RBAC, records security mutations in append-only audit events, returns a
consistent bounded error contract, and applies identity-aware abuse limits.
CORS accepts only configured origins, methods, and headers.

## Assets and classification

| Asset | Examples | Sensitivity and integrity needs |
| --- | --- | --- |
| SOC telemetry and evidence | Normalized events, raw payloads, command lines, IPs, usernames | Confidential; attacker-controlled content; high evidentiary integrity |
| Alerts and investigations | Alert status, risk, match explanations, case links | Confidential; high integrity and availability |
| Cases and analyst work | Case details, assignments, activities, notes | Confidential; actor attribution and ordering matter |
| Detection content | Rules, structured logic, versions, run windows and results | High integrity; unauthorized changes can suppress or fabricate findings |
| AI material | Evidence context, questions, outputs, citations, usage/error metadata | Confidential; advisory only; scope and provenance must be preserved |
| Identity and session material | User records, roles, password hashes, sessions | Critical confidentiality and integrity; Argon2 hashes and revocable opaque sessions |
| Integration credentials | PostgreSQL password, Elastic API key/password, future AI API key | Critical confidentiality; environment-only by design |
| Audit evidence | Actor, action, target, outcome, before/after details | High integrity and retention; append-only application records |
| Configuration | Origins, provider/model, limits, database/endpoint addresses | Integrity-sensitive; some values reveal topology |
| Logs | Request/provider/job diagnostics and correlation metadata | Potentially confidential; integrity and bounded retention required |
| Database backups | Complete database copy, including identities and audit history | Critical confidentiality, integrity, and recoverability |
| Source and delivery chain | Git history, dependencies, CI workflows and artifacts | High integrity; compromise can affect every runtime asset |

## Actors

| Actor | Intended access | Trust assumptions |
| --- | --- | --- |
| Anonymous/network client | Login and minimal liveness only after Phase 6 | Untrusted; may enumerate, replay, flood, or send malformed input |
| Viewer | Read SOC records and existing analysis results | Authenticated but not trusted to mutate data or invoke expensive work |
| Analyst | Investigate alerts/cases and request scoped AI help | Trusted for investigation mutations, not rules, integrations, or administration |
| Detection Engineer | Read SOC data and manage/test/execute detections | Trusted for detection content, not analyst casework or administration |
| Admin | Identity/role, integration, audit, and all product operations | Highly privileged; account compromise has broad impact |
| Local operator/maintainer | Configure, migrate, seed, back up, restore, and deploy | Trusted host and environment access; must protect secrets and backups |
| Elasticsearch service | Return telemetry for configured indices | External trust domain; responses and record content remain untrusted |
| AI provider | Return advisory structured output | External trust domain; must receive only bounded, redacted, scoped context |
| Evidence/content attacker | Controls log messages, raw JSON, filenames, pasted text, or analyst-visible fields | Fully untrusted; content may attempt injection, prompt injection, or resource exhaustion |
| Dependency/CI publisher | Supplies packages, actions, images, and scanner updates | External supply-chain trust domain |

These roles are enforced by FastAPI permission dependencies and privileged
service-layer checks. Streamlit visibility is not an authorization boundary.

## Trust boundaries

| Boundary | Data crossing it | Required controls |
| --- | --- | --- |
| Browser -> Streamlit | Credentials/session state, navigation and form/file input, rendered SOC data | Authentication, secure session handling, CSRF where applicable, output safety, upload limits |
| Streamlit -> FastAPI | Session credentials, resource IDs, filters, mutations, expensive-work requests | TLS outside loopback, server-side authentication/RBAC, validation, timeouts, consistent errors |
| FastAPI/service -> PostgreSQL | Queries, mutations, raw evidence, analyses, future identities/audit events | Parameterized ORM operations, transactions, constraints, least-privilege DB user, migrations, backups |
| FastAPI -> Elasticsearch | Endpoint credentials, bounded queries/checkpoints; untrusted results return | Read-only Elastic privilege, certificate verification, limits, timeout/retry, secret redaction |
| FastAPI -> AI provider | System instruction and bounded redacted evidence; untrusted output returns | Explicit enablement, environment-only key, prompt/data separation, schema/citation validation, limits/timeouts |
| Runtime -> logs | Messages, exceptions and structured context | Central redaction, no credentials/raw payloads, restrictive access, rotation/retention |
| Operator -> environment/CLI | Secrets, migration/reset/backup commands | Protected environment, safe defaults, exact-target checks, no shell-history leakage |
| Repository -> CI/dependencies | Workflow code, packages, actions, test artifacts | Least-privilege workflow token, pinned dependencies/actions, scanning, no secrets in untrusted jobs |
| Database -> backup storage | Full application dataset | Restricted permissions, encryption appropriate to location, integrity validation, tested restore |

## Entry points

| Entry point | Current behavior and risk |
| --- | --- |
| `GET /api/v1/health` and `/ready` | Unauthenticated liveness and bounded database readiness; no sensitive details |
| Events, alerts, dashboard reads | Authenticated, paginated/filterable SOC data |
| `PATCH /alerts/{id}` | Analyst/Admin mutation with atomic audit attribution |
| Case create/update/link/unlink/activity routes | Analyst/Admin transactionally audited investigation mutations |
| Detection rule validate/test/execute/create/update and run history | Detection Engineer/Admin operations with validation, abuse controls, and audit |
| Ingestion connection test/sync/status/history | Admin-only bounded provider operations with safe failure mapping |
| AI triage, case Q&A, report, and history routes | Analyst/Admin, evidence-scoped, rate-limited, idempotent, audited advisory AI |
| Streamlit forms and navigation | Provide friendly access to the same API actions; UI state is not a security boundary |
| Analyze Alert upload/paste | Processes attacker-controlled filenames and JSON/CSV/text in the Streamlit process |
| Report/export controls | Some controls remain prototypes; any completed export becomes a file/content boundary |
| Environment and `.env` | Supplies database, Elastic, and AI secrets plus CORS/limit configuration |
| Alembic and `python -m db.seed` | Privileged local commands that alter schema or bulk-create demo data |
| PostgreSQL and Elastic network listeners | Direct service interfaces outside application authorization if exposed |
| Logs and backup files | Local filesystem artifacts that may bypass application access controls |
| Dependency installation and GitHub Actions | Executes third-party code during development/delivery |

## Threats, mitigations, and verification

The issue references below preserve implementation traceability. Controls
described as planned in the original snapshot are implemented as of this
revision unless explicitly retained under accepted risks.

| ID | Threat and impact | Baseline mitigation | Phase 6 mitigation | Verification |
| --- | --- | --- | --- | --- |
| T01 | Anonymous access or broken object/function authorization exposes or mutates SOC data | Layer separation only; no auth at this snapshot | Authentication in #92; centralized RBAC and negative endpoint/service tests in #93 | Anonymous `401` tests; per-role allow/deny matrix; direct service bypass tests |
| T02 | Password guessing, user enumeration, session theft/fixation, stale sessions, or unsafe demo credentials compromise an identity | No credentials/sessions exist yet | Adaptive hashing, non-enumerating login, secure idle/absolute expiry, logout/revocation, safe bootstrap, login abuse controls in #92/#95 | Hash/session unit tests; brute-force and expiry tests; repository/log secret scan |
| T03 | CSRF or overly broad CORS causes an authenticated browser to perform unwanted actions | Configured origin list; credentials enabled; all methods/headers allowed | Narrow methods/headers/origins and CSRF protection appropriate to the selected session mechanism in #92/#95 | Preflight matrix and forged cross-origin mutation tests |
| T04 | SQL/logic injection, malformed identifiers, or unbounded filters alter queries or exhaust PostgreSQL | SQLAlchemy parameterization; Pydantic types; some pagination caps | Uniform request/query/time-window bounds and validation in #95 | Malicious/boundary input tests and database query review |
| T05 | Malicious upload names/content cause traversal, parser abuse, memory exhaustion, formula injection, or unsafe exports | Extension allowlist and configured upload size check; parsing is non-executing | Request/file limits, content checks, normalized/server-generated filenames and safe export encoding in #95 | Oversize, traversal, polyglot, control-character, and spreadsheet-formula tests |
| T06 | Ingested log text or analyst notes perform prompt injection, cross-case data access, or unsupported AI claims/actions | Bounded case/alert context; secret-pattern redaction; untrusted markers; system instruction; structured schema and citation validation; AI is advisory/fake/disabled by default | Preserve authorization, rate limits, audit coverage, and full adversarial regression in #93–#99 | Prompt-injection, cross-case, invalid-citation, secret-canary, and non-mutation tests |
| T07 | Secrets leak through config views, errors, logs, audit details, database fields, UI, prompts, git, CI, or shell commands | `to_safe_dict` redacts known config secrets; AI context redacts common patterns; provider logs omit credentials | Central error/audit/log redaction, canary scanning, safe operational commands and CI secret scanning in #94/#95/#97–#99 | Canary values scanned across every output/persistence channel and tracked files |
| T08 | Audit records are absent, incomplete, forged, mutated, or contain secrets, preventing accountability | Operational logs and domain timestamps only; no actor identity or audit table | Atomic actor-attributed append-only audit events, Admin-only bounded reads and redaction in #94 | Mutation-family coverage, atomicity, immutability, attribution and redaction tests |
| T09 | AI, detection, ingestion, search, login, or large-body abuse exhausts CPU, memory, database connections, provider quotas, or cost | Some list limits, ingestion limit, detection scan limit, AI token/time limits | Global/route-specific body, rate, concurrency, pagination and window controls in #95 | Burst/bypass tests, `429`/retry metadata tests, boundary load checks |
| T10 | Retry, replay, or concurrent work duplicates cases, rule versions, runs, alerts, analyses, audit events, or advances checkpoints incorrectly | Several unique constraints; ingestion/detection dedup logic; transaction commits | Mutation inventory, atomic allocation/locking, scoped idempotency and race handling in #96 | Independent-session duplicate/replay/concurrency tests against PostgreSQL |
| T11 | PostgreSQL failure or partial commit corrupts related domain and audit state | SQLAlchemy transactions in individual workflows; rollback in ingestion/detection paths | Explicit transaction boundaries, atomic audit writes, readiness and interruption recovery in #94/#96 | Fault injection around flush/commit, outage/recovery, and invariant checks |
| T12 | Elastic or AI outage, timeout, authentication failure, or unsafe retry crashes unrelated workflows or duplicates side effects | Elastic timeout and bounded retries for connection/timeout; AI timeout contract and fail-closed unavailable provider | Capped transient-only backoff/jitter, dependency degradation, liveness/readiness isolation in #96 | Timeout/auth/connection simulations; deterministic workflow smoke tests during outages |
| T13 | Raw events, exception strings, or unchecked structured log context expose sensitive evidence or fill disk | JSON logging to console/file; ingestion logs mostly counts/IDs; no rotation | Central redaction plus rotation, retention, permissions and disk-exhaustion guidance in #94/#98 | Secret canaries through success/failure paths; rotation/permission inspection |
| T14 | Backup theft, incomplete backup, unsafe reset, or untested restore causes disclosure or unrecoverable loss | Named Docker volume; deterministic idempotent seed | Protected backup commands, exact-target reset guards, documented/tested restore and smoke proof in #98 | Seed -> backup -> disposable reset -> restore -> migration/readiness/Analyst smoke test |
| T15 | Malicious or compromised package, container, action, or pull request executes in CI/runtime | Exact versions for direct Python dependencies; official PostgreSQL image tag | Least-privilege CI, PostgreSQL tests, pinned actions and practical dependency/secret scanning in #97 | Clean-checkout CI, workflow permission review, scanner results and documented limitations |
| T16 | Error detail, timing, or status differences enumerate users/resources or reveal provider/database internals | Some provider exceptions are translated to safe messages | Consistent error schema/correlation IDs and `401`/`403`/`404` disclosure policy in #92/#93/#95 | Enumeration comparisons and canary exception tests |
| T17 | Detection rule tampering suppresses findings or fabricated rules create misleading alerts | Version snapshots, structured DSL validation, deterministic execution provenance | Detection Engineer/Admin authorization and audit events in #93/#94 | Unauthorized role tests; before/after audit and rule-version provenance checks |
| T18 | Privileged operator mistakes or compromised Admin account disables access, destroys data, or removes the final administrator | Host/database access is outside app controls; no Admin role yet | Least-privilege Admin operations, final-Admin protection, session revocation, auditing and recovery runbook in #93/#94/#98 | Admin negative/invariant tests and documented recovery exercise |

## Security assumptions

- The host, Python environment, browser, and operator account are trusted and
  patched. Host compromise is outside the application's ability to contain.
- PostgreSQL is the system of record and is reachable only by intended local or
  deployment-network principals. Direct database administrators can bypass
  application RBAC and append-only application policy.
- The Streamlit and FastAPI processes receive configuration from a protected
  environment. `.env` is a development convenience, not a production secret
  manager.
- TLS termination and network exposure are deployment responsibilities. Plain
  HTTP is acceptable only on loopback or inside an equivalently protected local
  boundary.
- Elasticsearch credentials are read-only and restricted to required indices.
  Returned telemetry remains untrusted even when the server is trusted.
- AI remains advisory and receives no database, shell, remediation, or external
  query tools. Enabling a real provider is a separate data-egress decision.

## Accepted risks

These risks are accepted for the local portfolio scope, not silently treated as
resolved.

| Risk | Rationale and compensating control | Owner | Review trigger/date |
| --- | --- | --- | --- |
| Local HTTP between browser, Streamlit, and FastAPI | The documented demo runs on loopback. Bind services to trusted interfaces and do not expose them directly; use TLS at a reverse proxy before remote access. | Deployment operator | Before any non-loopback deployment, or 2026-12-01 |
| Environment variables/`.env` instead of a managed secret store | Keeps the local demo reproducible. `.env` is gitignored, safe config views redact known values, and operators must restrict file/process access. | Project maintainer | Before shared/multi-user hosting, or 2026-12-01 |
| Direct database administrators can alter audit rows | PostgreSQL administration is an explicitly trusted operator boundary. Application APIs will be append-only and backups provide supporting evidence, but no external immutable/WORM sink is planned. | Project maintainer | Before compliance use or untrusted DBA access, or 2026-12-01 |
| In-process/local rate-limit storage may not coordinate multiple API workers | A single-process local deployment can enforce reasonable abuse controls without new infrastructure. Document and refuse to imply cluster-wide enforcement. | API owner | Before adding a second worker/replica or public exposure |
| Only the deterministic fake AI provider is implemented/tested | AI is disabled by default and deterministic workflows do not depend on it. A real provider requires a fresh privacy, retention, regional, timeout, and cost review. | AI integration owner | Before configuring any real provider |
| Backups rely on operator-controlled filesystem protection | The portfolio deployment does not introduce a backup service or key-management system. The recovery runbook documents permissions/encryption expectations and records a disposable restore proof. | Deployment operator | Before storing non-demo data, or 2026-12-01 |
| Uploaded/raw telemetry can contain sensitive data not recognized by pattern redaction | Pattern redaction reduces common leakage but is not a data-loss-prevention guarantee. Access is restricted, context is bounded/scoped, and real AI egress remains disabled by default. | Security owner | Before real-provider enablement or ingesting production telemetry |
| Single local PostgreSQL instance has no automatic failover | Availability goals for the portfolio demo are recovery-based, not high availability. Health/readiness and tested backup/restore are the compensating controls. | Deployment operator | Before setting an uptime SLO or multi-user production use |

## Validation and maintenance

The Phase 6 regression gate records the role matrix, migrations/environment
variables, CI checks, canary secret scan, provider outage tests,
prompt-injection tests, backup/restore proof, authorized Analyst workflow, and
remaining accepted risks.

Update this threat model whenever a trust boundary changes; a real AI provider,
remote deployment, new integration, new upload/export format, additional API
worker, external identity provider, secret manager, or immutable audit sink is
introduced; or an accepted-risk review trigger is reached.
