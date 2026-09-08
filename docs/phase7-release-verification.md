# Phase 7 release-candidate verification

> **Historical record.** A point-in-time execution log, kept for provenance. It is not
> maintained. For current behaviour see [docs/demo.md](demo.md) and the
> [README](../README.md).

Executed 2026-09-07 against the stacked Phase 7 history, on branch
`phase7-release-verification`.

## Method

A database named `p7rc` was created fresh inside the project's PostgreSQL 16 container,
so nothing pre-existing could make a step appear to pass. The API ran on port 8123
against that database with `AI_ENABLED=true`, `AI_PROVIDER=fake`, and `ELASTIC_URL`
empty. No Elastic cluster and no paid AI provider was involved at any point.

The one thing not exercised from a clean state was destroying the Docker volume, because
that would have deleted the repository owner's existing local demo database. Creating a
new database inside the running container gives the same empty-schema starting point for
every step below.

## CI-equivalent checks

| Check | Result |
|---|---|
| `compileall api api_client app backend config db scripts tests` | pass |
| `alembic upgrade head` on an empty database | pass, head `e1f2a3b4c5d6` |
| `alembic downgrade -1 && alembic upgrade head` | pass, reverses cleanly |
| `alembic check` | `No new upgrade operations detected` |
| `pytest -q` | **379 passed**, 1 warning, 19.65s |
| `pip-audit -r requirements.txt` | `No known vulnerabilities found` |
| gitleaks over full history | 78 commits scanned, **no leaks found** |
| GitHub Actions on the branch stack | all three jobs green |

## Demo path

| Step | Result |
|---|---|
| Fresh database, migrate | head applied |
| `python -m db.seed` | 5 detection rules, `ALERT-0005` present |
| `python -m db.bootstrap_user --role admin` | `Created demo user 'demo-admin'` |
| `python -m scripts.smoke` | all six checks pass, exit 0 |
| Fixture ingestion | `fetched=3 persisted=3 duplicate=0` |
| Detection execution | 5 rules, 16 events scanned each, 15 alerts created |
| Second pipeline run | `fetched=0 persisted=0`, 0 alerts created |

## Analyst narrative

Every step below returned success.

| Step | Observed |
|---|---|
| Critical alert filter | `ALERT-0005`, `ALERT-0006`, plus 2 engine-created alerts after the pipeline |
| `ALERT-0005` linked evidence | 3 events at 02:08:00, 02:08:15, 02:08:30 |
| MITRE mapping | T1098.004, Account Manipulation: SSH Authorized Keys, Persistence |
| AI triage | `status=succeeded`, `provider=fake`, 5 evidence references |
| Alert status change | `in_progress` |
| Escalation to case | `CASE-2026-0004`, priority High, status Open |
| Analyst note | created |
| Priority and status update | Critical, In Progress |
| Case Copilot question | `status=succeeded`, `provider=fake` |
| Report draft | `status=succeeded`, 7 sections |
| Audit history | 25 events, every action attributed to `demo-admin` |

## Persistence after restart

The API process was stopped and started again, and a new session was established.

| Record | State after restart |
|---|---|
| `CASE-2026-0004` | In Progress, Critical, 1 alert linked |
| Case activities | 4: `case_created`, `note`, `status_change`, `priority_change` |
| `ALERT-0005` | In Progress |
| AI analyses on the alert | 1, citations intact |

Nothing was held in Streamlit session state.

## Blockers found and fixed during verification

**One.** `docs/demo.md` stated that the Critical filter shows exactly two alerts. That
holds only if the reader skips the pipeline. Running it creates two more critical alerts
titled "SSH Authorized Keys Modification" with no external ID, so the filter shows four,
and the document contradicted its own step ordering.

Fixed in a single commit. The document now states both cases and explains why an
engine-created alert has no `ALERT-NNNN` identifier.

No other blocker was found. No other change was made during verification.

## Not verified

- Destroying and recreating the Docker volume, for the reason given above.
- Clicking through the authenticated Streamlit screens. That would mean typing a
  password into a browser form. The app was confirmed to start and serve its login page,
  and the screens are covered by the AppTest suites, which call the same API this
  verification exercised directly.
- Elastic ingestion. The default demo deliberately avoids requiring a cluster, and CI
  does not cover it. This is recorded as a limitation in the release notes.
- Any real AI vendor, because none is implemented. See
  [docs/ai-safety.md](ai-safety.md).

## Release state

No tag was created and `main` was not merged. Both require the repository owner's
explicit instruction.

The proposed release notes are in
[docs/release-notes-draft.md](release-notes-draft.md).
