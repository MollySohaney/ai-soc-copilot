# Release notes draft — v0.1.0

**Status: draft. No tag has been created.** Tagging is the repository owner's decision.
Version number proposed, not fixed.

---

## AI SOC Copilot v0.1.0

A working security operations centre workflow you can run on a laptop in about five
minutes. Telemetry arrives, deterministic detection rules fire, an analyst investigates
the evidence, and an AI assistant offers an opinion it is required to cite.

### What you can do with it

Clone the repository, run three commands, and follow one intrusion from raw telemetry to
a documented case: SSH brute force, valid login, privilege escalation through `sudo`,
and persistence written to `authorized_keys`. You open the critical alert, read its
linked evidence and MITRE ATT&CK mapping, run AI triage and inspect exactly what it
cited, escalate to a case, work it, ask a case-scoped question, draft a report, read the
audit trail, then restart everything and watch it all persist.

[docs/demo.md](demo.md) is the walkthrough. Every identifier in it is deterministic.

### What is in it

- **Telemetry ingestion** through provider-neutral adapters, with ECS normalization,
  restartable checkpoints, and idempotent replay. Elastic is supported; an in-memory
  fixture adapter is the default.
- **A detection engine** with single-event, threshold, and sequence evaluators.
  Execution is deterministic, uses event time rather than arrival time, and creates
  fingerprinted alerts so replay is a no-op.
- **An analyst workflow**: dashboard, investigations, alert detail with linked evidence
  and MITRE mapping, escalation to cases, activity timelines, notes, status and
  priority, and detection rule management.
- **Advisory AI** for alert triage, case question answering, and report drafting, each
  bounded by an evidence context, validated against a versioned schema, and rejected if
  it cites anything outside that context.
- **Security**: local authentication with opaque bearer sessions, server-enforced RBAC
  across four roles, append-only audit events, rate and concurrency limits on the
  expensive paths, and secret redaction throughout.

### Requirements

Docker and Python 3.12 or newer. Nothing else. No SIEM licence, no AI vendor account, no
cloud resources.

### Limitations

Read these before evaluating the project. They are the honest boundaries of what it is.

**No AI vendor is wired up.** The provider abstraction, prompt construction, evidence
context assembly, schema validation, citation enforcement, and abuse controls are all
real and covered by tests. The only implemented provider is a deterministic offline
fake. Setting `AI_PROVIDER` to a vendor name does not reach that vendor; it falls back
to unavailable. Nothing here demonstrates the quality, latency, cost, or injection
resistance of a real model. See [docs/ai-safety.md](ai-safety.md).

**This is not production infrastructure.** Single node, single tenant, local
deployment. No horizontal scaling, no multi-tenancy, no secret manager, no TLS
termination, no managed backups, no high availability. Authentication is local accounts
only, with no SSO, no MFA, and no directory integration.

**Detection runs on demand.** There is no scheduler. Rules execute when you ask them to.

**The Elastic path is less exercised than the fixture path.** The default demo
deliberately avoids requiring a cluster, so CI does not cover Elastic ingestion.

**Several screens are prototypes.** MITRE Explorer, Threat Intelligence, Analyze Alert,
and Settings run on static data. Dashboard, Investigations, and Integrations are
API-backed but each keeps one static panel. Reports is a hybrid: static metrics and
preview, with a real report-drafting button. The sidebar Copilot panel returns a canned
reply; the real case-scoped Q&A is on the case detail view.

**No performance claims.** The application has not been load tested. The demo dataset
is small by design.

### What was verified for this release

- Full test suite from a clean checkout
- Clean migration, downgrade and re-upgrade, and `alembic check` for drift
- `pip-audit` against the pinned dependencies, and a gitleaks scan over the full history
- The complete demo narrative executed against PostgreSQL 16 on a freshly created
  database, then re-verified after a full process restart
- Ingestion and detection idempotency on a second run
- Every command in the README and `docs/demo.md`

Known gaps are tracked in [docs/release-readiness.md](release-readiness.md).

### Security

Report vulnerabilities privately through GitHub's security advisory flow. See
[SECURITY.md](../SECURITY.md). This is a portfolio deployment, not a managed service,
and carries no SLA.

### Licence

MIT.
