# The five-minute demo

One attack, followed from raw telemetry to a documented case, on a machine with no
Elastic cluster and no paid AI account.

The story is a single intrusion against `ubuntu-target-01`: an attacker at
`192.168.64.2` brute-forces SSH, succeeds, escalates to root through `sudo`, and
establishes persistence by writing to `~/.ssh/authorized_keys` and dropping a cron
entry. Benign noise events sit alongside it so the detections have something to be
wrong about.

Every identifier in this document comes from `db/seed.py`, which derives every
timestamp from a fixed constant and looks up every row by a natural key. On a clean
database you will see exactly the identifiers printed here.

## Before you start

Complete the setup in [the README](../README.md). In short:

```bash
cp .env.example .env
make setup          # PostgreSQL, migrations, seed data, demo admin
make api            # terminal 1
make ui             # terminal 2
make smoke          # terminal 3, expect six passes
```

`make admin` prints a generated password once. Export it before running anything that
authenticates:

```bash
export DEMO_PASSWORD='the password make admin printed'
```

Two configuration values matter and both are already correct in `.env.example`:

| Setting | Value | Why |
|---|---|---|
| `ELASTIC_URL` | empty | Ingestion runs through the in-memory fixture adapter. |
| `AI_ENABLED` / `AI_PROVIDER` | `true` / `fake` | The deterministic offline provider. No network call, no API key. |

## Who you are signed in as

`make setup` creates a single Admin. That is deliberate. The narrative below crosses
four permissions and no lesser role holds all of them:

| Step | Permission | Roles that hold it |
|---|---|---|
| Ingest telemetry | `operate_integrations` | Admin |
| Execute detections | `manage_detections` | Detection Engineer, Admin |
| Triage, escalate, note, ask, report | `mutate_investigations`, `request_ai` | Analyst, Admin |
| Read audit history | `read_audit` | Admin |

If you would rather see the security model push back, bootstrap a second account with
`--role analyst` and try step 1 as that user. You will get
`403 Insufficient permission.` before the request touches any data. That denial is the
feature, not a bug. See [docs/permissions.md](permissions.md).

---

## Step 1: Bring in telemetry and run the detections

```bash
make pipeline
```

This logs in, runs one bounded fixture ingestion sync, then executes every enabled
rule. On a clean database:

```
OK    fixture_ingestion                              status=succeeded fetched=3 persisted=3 duplicate=0.
OK    Unusual Outbound Network Connection Volume     Scanned 16 events, created 4 alerts.
OK    SSH Authorized Keys Modification               Scanned 16 events, created 2 alerts.
OK    Sudo Privilege Escalation                      Scanned 16 events, created 4 alerts.
OK    Valid Account Login Following Failed Attempts  Scanned 16 events, created 4 alerts.
OK    SSH Brute Force Detection                      Scanned 16 events, created 1 alerts.
```

Run it a second time. Ingestion fetches nothing because the restartable checkpoint has
advanced, and every rule creates zero alerts because the fingerprints already exist.
Replay is a no-op by construction, not by luck.

Two window sizes are in play and the difference is worth understanding. Ingestion is
bounded only by `API_MAX_QUERY_WINDOW_DAYS`, so the pipeline asks for a full day.
Detection is bounded by each rule's own `lookback_window_seconds`, which every seeded
rule sets to 3600, so the pipeline asks for the one hour containing the attack.
Requesting more is rejected with a 422 rather than silently truncated.

**You can skip this step entirely**, and on a first read you probably should. The seed
already contains the attack chain and its alerts, so the whole story works without
ingesting anything. Run the pipeline when you want to watch the machinery move rather
than only see its output.

Skipping also keeps the next screen tidy, because executing the rules adds alerts of its
own. Step 2 says what you will see either way.

## Step 2: Find the critical alert

In the Streamlit app, open **Investigations** and filter severity to **Critical**.

If you skipped the pipeline, two alerts match:

| ID | Title |
|---|---|
| `ALERT-0006` | Correlated Attack Chain: SSH Brute Force to Persistence |
| `ALERT-0005` | SSH Authorized Keys Modified for mollysohaney |

If you ran the pipeline, there are four. The two extra rows are titled **SSH Authorized
Keys Modification**, after the rule that produced them, and they have **no external
ID**. That is the difference between a seeded alert, which carries a curated
`ALERT-NNNN` identifier, and an alert the detection engine just created, which is
identified by its fingerprint. Both are real alerts. Only the seeded ones have stable
names this document can cite.

Open **`ALERT-0005`** either way. `ALERT-0006` is the correlated narrative across the
whole chain and is worth reading, but `ALERT-0005` is the one with linked evidence rows,
so it is the one that demonstrates the evidence model.

## Step 3: Read the evidence, not the summary

The alert carries a risk score of 90 against host `ubuntu-target-01`, user
`mollysohaney`, from source `192.168.64.2`.

The **Timeline/Evidence** tab shows exactly three linked events:

| Event | Time (UTC) | What happened |
|---|---|---|
| `evt-signal-persist-01` | 02:08:00 | New SSH public key appended to `authorized_keys` |
| `evt-signal-persist-02` | 02:08:15 | Permissions changed on `authorized_keys` (chmod 600) |
| `evt-signal-persist-03` | 02:08:30 | New cron entry written to `/etc/cron.d/system-health` |

The **MITRE** tab maps this to **T1098.004**, Account Manipulation: SSH Authorized
Keys, under the **Persistence** tactic.

This is the point of the whole application. The alert is not a verdict. It is a claim
with the evidence attached, and the evidence has stable identifiers that everything
downstream must cite.

## Step 4: Ask the AI, and check what it cited

Request triage on the alert. The response comes back with `provider: fake` and
`status: succeeded`, and it cites five evidence identifiers:

```
alert-5
event-evt-signal-persist-01
event-evt-signal-persist-02
event-evt-signal-persist-03
mitre-5
```

Read the citation list, not the prose. The provider is a deterministic offline
responder, so the prose is filler. What is real is the machinery around it: the
evidence context assembled from the database, the prompt that labels that evidence as
untrusted data, the schema validation that rejects malformed output, and the check that
rejects any citation outside the supplied context. That last check is what stops a
model from inventing evidence.

**No real AI vendor is wired up.** Setting `AI_PROVIDER` to a vendor name does not
reach that vendor; it falls back to unavailable. See
[docs/ai-safety.md](ai-safety.md) for exactly what this does and does not prove.

## Step 5: Take ownership

Set the alert status to **In Progress**, then click **Escalate to Case**.

On a clean database the new case is **`CASE-2026-0004`**, because the seed ships three
cases before it. It opens with priority **High** and status **Open**, with `ALERT-0005`
linked to it.

## Step 6: Work the case

Three actions, in the **Activity** tab and the case header:

1. Add a note: *Confirmed the authorized_keys write and the cron entry on the host.*
2. Change status to **In Progress**.
3. Raise priority to **Critical**.

The activity timeline now holds four entries and you only wrote one of them:

```
case_created    note    status_change    priority_change
```

The other three are recorded automatically. An analyst cannot silently change a case's
state.

## Step 7: Ask a question and draft the report

Ask the case-scoped Copilot something concrete, such as *what established persistence
on this host?* The answer is scoped to evidence linked to this case and cites
`case-4`. Then generate the report draft. It returns seven sections: executive summary,
technical timeline, indicators, MITRE mapping, actions recorded, recommendations, and
evidence references.

The report's actions-recorded section is constrained to actions actually present in the
evidence. It cannot narrate work nobody did.

## Step 8: Read the audit log

Open the audit history as the Admin. Every action you just took is there, attributed,
in order:

```
auth.login              succeeded  demo-admin
ai.triage.request       succeeded  demo-admin
alert.update            succeeded  demo-admin
case.create             succeeded  demo-admin
case.activity.create    succeeded  demo-admin
case.update             succeeded  demo-admin
ai.copilot.request      succeeded  demo-admin
ai.report.request       succeeded  demo-admin
```

The audit table is append-only. A failed or denied action is recorded too, so a
permission denial leaves a trace rather than vanishing.

## Step 9: Prove it is real

Refresh the browser. Then stop both processes, start them again, and log back in.

`CASE-2026-0004` is still In Progress at Critical priority, still linked to
`ALERT-0005`, still carrying four activity entries. The alert is still In Progress. The
AI analysis is still attached to the alert with its citations intact.

Nothing here lived in Streamlit session state. Every screen you looked at was reading
PostgreSQL through the API.

To start over, `make reset` deletes every application row and reseeds. It refuses to
run unless `ENVIRONMENT` or `APP_ENV` is a local or demo value, and it requires you to
type the database name back to it.

---

## The short version

If you have five minutes: `make setup`, `make api`, `make ui`, `make smoke`, then jump
straight to Step 2 and follow through Step 6. Skip the pipeline, the report, and the
audit log. The seeded data alone tells the story.

## How this document was verified

Every step above was executed against PostgreSQL 16 on a freshly created database:
migrate, seed, bootstrap, then the full sequence through the HTTP API, then a process
restart and a re-read. The counts, identifiers, timestamps, case number, activity types,
and audit actions are transcribed from that run.

The Streamlit interface was confirmed to start and serve its login page. The screens
themselves are covered by the AppTest suites under `tests/` (`test_auth_page.py`,
`test_investigations_page.py`, `test_cases_page.py`, and the rest), and they call the
same API this document exercised directly, through the typed client in `api_client/`.

## If something does not match

Run `make smoke`. It checks database reachability, migration head, seed data, API
liveness and readiness, and an authenticated read, and it names the fix for whichever
one fails.

Read [docs/release-readiness.md](release-readiness.md) for known gaps, and
[docs/operations-runbook.md](operations-runbook.md) for recovery.
