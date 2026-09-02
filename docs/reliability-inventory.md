# Reliability and idempotency inventory

| Operation | Transaction boundary | Duplicate/concurrency protection | Retry/outage behavior |
|---|---|---|---|
| Alert/case mutation | Domain row, timeline/link rows, and audit event commit together | FK/unique constraints; case-number allocation uses a PostgreSQL transaction advisory lock | Integrity failures roll back; caller retries with an idempotency key where supported |
| Detection execution | Detection run and created alerts commit together; run header is durable before evaluation | Alert fingerprint unique index makes replay a no-op; bounded event scan | Deterministic evaluator failures mark the run failed; no provider retry |
| Ingestion sync | Run, normalized events, checkpoint, and audit callback commit together | Event dedup key and checkpoint unique constraints; retries are capped by configured attempts | Elastic connection/timeout errors are classified and isolated; failed run is persisted |
| AI triage | Analysis and audit commit together | `Idempotency-Key` is actor/operation/payload scoped with 24-hour retention | Provider unavailable/invalid output is persisted as a safe failed analysis; no automatic duplicate side effect |
| Case creation | `Idempotency-Key` reserves before mutation and caches only successful response | Actor/operation/key unique record; payload mismatch and in-flight replay return 409 | Failed mutation leaves no cached success; authorization failures are never cached |
| Authentication/admin | Session/auth or user mutation and audit commit together | Opaque session digest unique index; role changes revoke sessions | Expired/revoked sessions fail closed; admin invariants prevent removing final active admin |
| Audit writes | Staged in caller transaction | PostgreSQL trigger and ORM listeners reject update/delete | Audit persistence failure rolls back the associated domain mutation |

Liveness is `/health`; readiness is `/ready` and performs only a safe `SELECT 1`.
Readiness returns generic `503` when PostgreSQL is unavailable. Optional Elastic
and AI outages are degraded provider results, not process-wide failures. In-memory
abuse limits remain process-local as documented in `docs/api-security.md`.
