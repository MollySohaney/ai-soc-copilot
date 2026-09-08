# Release readiness audit

**Audited:** 2026-09-07 on branch `phase7-release-audit`, at commit `5f6f697`.
**Method:** read the repository as a first-time reader would, then verify each claim
against the code, the configuration, and a running stack.
**Status:** findings only. No fix is applied in this step. Every finding names the
Phase 7 step that resolves it.

## How to read this document

Each finding has an identifier, a priority, an owning step, and the evidence used
to reach it. Priorities are:

| Priority | Meaning |
|---|---|
| Blocker | A first-time reader cannot complete the demo, or the repository states something false about what it does. |
| Correctness | The repository works, but documentation or configuration disagrees with the code. |
| Polish | Real but cosmetic. Fix if cheap. |
| Deferred | Out of Phase 7 scope. Record in the roadmap instead of fixing. |

## Verification commands run

| Command | Outcome |
|---|---|
| `.venv/bin/python -m pytest -q` | `336 passed, 1 warning in 18.26s` |
| `docker compose ps` | `ai-soc-copilot-postgres-1` up 8 days, healthy, host port 5435 |
| `.venv/bin/python --version` | `Python 3.14.3` |
| `git ls-files` | no `.pyc`, `__pycache__`, `.log`, or `.DS_Store` tracked |
| `grep -rn "mock_data" app tests api backend` | 8 importing modules, listed below |
| `grep -rn "os.getenv\|os.environ" api api_client app backend db alembic` | 4 reads outside `config.settings` |
| `grep -o "](\([^)]*\))" README.md` | 3 relative links, all resolve |
| `grep -rno "](\([^)h][^)]*\))" docs/*.md SECURITY.md` | no relative links at all |

---

## Blockers

### B1 — AI is unavailable under the documented default configuration

`backend/ai/provider.py:136` resolves the provider as follows:

```python
def build_ai_provider(config: AppConfig) -> AIProvider:
    if not config.ai_enabled:
        return UnavailableAIProvider()
    if config.ai_provider.lower() == "fake":
        return FakeAIProvider()
    return UnavailableAIProvider()
```

`.env.example` ships `AI_ENABLED=false`. `UnavailableAIProvider.complete` always
raises `AIUnavailableError`. A reader who copies `.env.example` to `.env` and follows
the README therefore gets no AI result at all.

The failure is graceful, which makes it easy to miss. `api/v1/endpoints/ai.py:81`
catches `AIProviderError`, persists an `AIAnalysis` row with `status="unavailable"`
and the message "AI assistance is unavailable or not configured", and writes an audit
event with outcome `failed`. Nothing crashes. The demo simply has no AI output, and a
reviewer would reasonably conclude the AI layer does not work.

The safe demo configuration is `AI_ENABLED=true` with `AI_PROVIDER=fake`. Nothing in
the repository says so. The Phase 7 issue text itself repeated the same mistake and
must be corrected alongside the documentation.

**Owner:** Step 2 for the configuration, Step 3 and Step 4 for the wording.

### B2 — No real AI provider exists, but the configuration implies one does

`build_ai_provider` has exactly two outcomes: the deterministic fake, or unavailable.
There is no Anthropic, OpenAI, or other client anywhere in `backend/ai/`, and
`requirements.txt` pins no LLM SDK.

Meanwhile `.env.example` documents `AI_PROVIDER`, `AI_MODEL`, `AI_API_KEY`,
`AI_REQUEST_TIMEOUT_SECONDS`, `AI_MAX_INPUT_TOKENS`, and `AI_MAX_OUTPUT_TOKENS`, all
of which read as though a paid provider can be plugged in by setting a key. Setting
`AI_PROVIDER=anthropic` and a real `AI_API_KEY` silently produces
`UnavailableAIProvider`.

This must be stated plainly rather than papered over. The correct framing is that the
AI layer is a complete provider abstraction with prompt construction, context
assembly, schema validation, and abuse controls, exercised by a deterministic fake,
and that wiring a live vendor is deliberately left as the next step.

**Owner:** Step 5 for `docs/ai-safety.md`, Step 4 for the README limitations section,
Step 7 for the release notes.

### B3 — README describes a project that no longer exists

`README.md:122` opens "Phase 2 wires the following pages...". `README.md:142` lists
under "Out of scope for this phase":

- A detection-rule execution engine
- AI/LLM functionality

Both shipped. `backend/detection/` contains the rule DSL, matcher, threshold and
sequence evaluators, and the execution service. `backend/ai/` contains the provider
abstraction, prompt construction, context assembly, and triage. Phase 6 added
authentication, RBAC, audit events, rate limiting, and reliability controls, none of
which the README mentions in its scope section.

`README.md:157` still offers "Suggested Next Steps" that were completed two phases
ago, including "Add authentication, authorization, and audit controls".

A reader evaluating this repository would conclude the project stopped at Phase 2.

**Owner:** Step 4.

### B4 — Neither ingestion nor detection execution has a command-line entry point

The Step 2 demo path has to "run fixture ingestion" and "execute detections". Both are
reachable only over HTTP:

- Ingestion: `POST /api/v1/ingestion/sync` and `/test-connection`
  (`api/v1/endpoints/ingestion.py:46,88`), with the adapter chosen by a `provider`
  value routed through `_build_adapter` at line 198.
- Detection: `POST /api/v1/rules/{rule_id}/execute` (`api/v1/endpoints/rules.py:166`).

Both require an authenticated session and both are rate limited. There is no
`python -m` equivalent. Any scripted demo or smoke helper must log in and drive the
API, or the demo must be documented as a click-through in Streamlit. Neither approach
is documented today.

**Owner:** Step 2.

### B5 — The demo has no documented starting point for a reader

The README quick start is eight numbered steps spread across two terminals, with
undocumented ordering constraints. `alembic upgrade head` must precede
`python -m db.seed`, which must precede `python -m db.bootstrap_user`, which must
precede login. Nothing states this. Step 7 of the quick start creates the demo user
with an interactive password prompt, and the walkthrough in "Demo Analyst Workflow"
never tells the reader to log in with it.

There is no `docs/demo.md`, no smoke check, and no single command that tells a reader
whether their stack is actually working.

**Owner:** Step 2 for the path and the health helper, Step 3 for the narrative.

### B6 — The demo role in the README cannot perform the demo

`README.md:70` instructs the reader to bootstrap `--role analyst`. The permission
matrix in `backend/security/rbac.py:23` grants Analyst only `READ_SOC`,
`MUTATE_INVESTIGATIONS`, and `REQUEST_AI`. Mapping that against the routes the demo
narrative needs:

| Demo action | Route | Permission | Analyst |
|---|---|---|---|
| Fixture telemetry ingestion | `POST /api/v1/ingestion/{provider}/sync` | `OPERATE_INTEGRATIONS` | Denied |
| Detection execution | `POST /api/v1/rules/execute` | `MANAGE_DETECTIONS` | Denied |
| Alert triage, case mutation, Copilot, reports | various | `MUTATE_INVESTIGATIONS`, `REQUEST_AI` | Allowed |
| Audit history | `GET /api/v1/audit-events` | `READ_AUDIT` | Denied |

Three of the ten steps in the intended narrative return `403 Insufficient permission.`
for the account the README tells the reader to create. `OPERATE_INTEGRATIONS` and
`READ_AUDIT` are Admin-only; `MANAGE_DETECTIONS` belongs to Detection Engineer and
Admin. Only Admin holds all four.

This is correct RBAC design and should not be weakened. The documentation is what is
wrong. The demo path must either bootstrap an Admin, or bootstrap several accounts and
say which one performs which part of the story. Showing a denial deliberately is a
better demonstration of the security model than hiding it.

**Owner:** Step 2 to choose and implement, Step 3 to narrate the role switches.

---

## Correctness

### C1 — Stated test count is stale by a factor of two and a half

`README.md:97` claims "The suite (137+ tests)". The actual run is 336 passed. Either
verify the number at release time or drop the hard count.

**Owner:** Step 4.

### C2 — `ENVIRONMENT` is undocumented and conflicts with `APP_ENV`

`db/reset_demo.py:17` reads `os.getenv("ENVIRONMENT", "development")` and refuses to
run unless the value is one of `development`, `demo`, `test`, `local`. Every other
part of the application reads `APP_ENV` (`config/settings.py:289`), and
`.env.example` documents `APP_ENV` but never `ENVIRONMENT`.

The default makes the reset work by accident. A reader who sets `APP_ENV=demo`
expecting it to apply will find that `reset_demo` ignores it. Either document
`ENVIRONMENT` in `.env.example` or make `reset_demo` read the same setting the rest
of the application reads.

**Owner:** Step 2 to decide and document, Step 7 to verify `.env.example` is complete.

### C3 — `docs/architecture.md` stops at Phase 3

The document has sections for "Phase 2 API Surface" and "Phase 3 Ingestion Surface"
and then stops. Missing entirely:

- The detection engine in `backend/detection/` (Phase 4).
- The AI provider abstraction, prompts, and context assembly in `backend/ai/`
  (Phase 5).
- Authentication, sessions, RBAC, audit events, rate and concurrency limiting, and
  the middleware stack (Phase 6). `backend/security/`, `backend/audit/`, and
  `backend/reliability/` are not mentioned; `backend/security/` is described only as
  "Validation and security-focused controls".

**Owner:** Step 5.

### C4 — `docs/` files do not link to each other or to the README

There are thirteen documents under `docs/` and not one relative link between them,
confirmed by grep. The security story alone is spread across `threat-model.md`,
`api-security.md`, `permissions.md`, `SECURITY.md`, and four regression gates, with no
navigation path. The README links to only three of the thirteen.

**Owner:** Step 5.

### C5 — Phase regression gates are point-in-time records presented as current docs

`docs/phase3-regression-gate.md` through `docs/phase6-regression-gate.md` are dated
execution records. `phase3` opens "This gate was run on 2026-08-31"; `phase6` opens
"Executed 2026-09-02". They sit alongside living documents with no visual or
structural distinction, and `README.md:139` points a reader at
`phase5-regression-gate.md` as though it were the current AI setup guide.

They should be preserved as history and labeled as such, with living content moved
into `docs/ai-safety.md` and the other durable documents.

**Owner:** Step 5 to relabel and relocate, Step 4 to fix the README pointer.

### C6 — `requirements.txt` mixes test tooling into runtime and calls the project a scaffold

The file header reads "Define the minimal runtime dependencies for the project
scaffold." The project is no longer a scaffold. `pytest==9.0.3` is pinned in the same
list as `fastapi` and `sqlalchemy`, so anyone installing to run the demo also installs
the test framework.

Splitting runtime and development dependencies is a real improvement but changes what
CI installs, so treat the split as optional. Correcting the header is not optional.

**Owner:** Step 7.

### C7 — Local Python is 3.14 while CI pins 3.12

`.github/workflows/ci.yml` sets `python-version: "3.12"`. `README.md:34` asks for
"Python 3.12+". The working virtual environment is 3.14.3, and `__pycache__`
directories contain both `cpython-311` and `cpython-314` artifacts, indicating at
least three interpreters have been used against this tree.

The suite passes on 3.14 locally and on 3.12 in CI, so this is not breakage. It should
be stated: what is tested in CI, and what is known to work.

**Owner:** Step 4 for the stack section.

### C8 — Default PostgreSQL port in `.env.example` differs from the working local setup

`.env.example` sets `POSTGRES_PORT=5432`. The running container publishes 5435,
because `docker-compose.yml` maps `${POSTGRES_PORT:-5432}:5432` and the local `.env`
overrides the value. The compose file and the application agree with each other, so
nothing is broken.

It is worth documenting, because 5432 frequently collides with a system PostgreSQL and
the failure mode is a confusing connection error against the wrong database.

**Owner:** Step 2.

---

## Mock data inventory

`app/data/mock_data.py` is 641 lines and is imported by eight modules. Classification
below is based on whether the importing view also calls `api_client`, and on the
README's own prototype list at `README.md:131`.

| Module | Imported symbols | Classification | Basis |
|---|---|---|---|
| `app/views/dashboard.py:25` | `MITRE_ACTIVITY` | Mixed: live view, one mock panel | Dashboard is wired to the API; a single MITRE activity panel is still static. |
| `app/views/investigations.py:31` | `INVESTIGATION_NOTES` | Mixed: live view, one mock panel | Investigations is API-backed; the notes panel is still static. |
| `app/views/integrations.py:18` | `SIEM_INTEGRATIONS`, `TI_INTEGRATIONS` | Mixed: live ingestion controls, mock catalogue | Phase 3 wired ingestion status and sync; the integration catalogue is decorative. |
| `app/views/reports.py:20` | `REPORT_METRICS`, `REPORT_PREVIEW`, `REPORTS` | Prototype | Listed as unwired in the README. Note that Phase 5 added real report generation, so this page and that capability may now disagree. |
| `app/views/analyze_alert.py:15` | `ANALYSIS_RESULT`, `PLATFORM_OPTIONS`, `SAMPLE_ALERT_JSON` | Prototype | Listed as unwired in the README. |
| `app/views/mitre_explorer.py:9` | `MITRE_TACTICS`, `MITRE_TECHNIQUES` | Prototype, reference data | Static ATT&CK reference content, reasonable to keep as data. |
| `app/views/threat_intel.py:9` | several | Prototype | Listed as unwired in the README. No threat-intel backend exists. |
| `app/components/copilot.py:11` | `COPILOT_CONVERSATION` | Needs a decision | Phase 5 shipped real case-scoped Copilot Q&A. A mock conversation in the shared Copilot component may shadow or sit beside the real one. |

Two items need resolution before anything is deleted:

- **M1 (Correctness):** `app/components/copilot.py` and `app/views/reports.py` use mock
  data for capabilities that Phase 5 actually implemented. Determine whether the real
  path is reachable in the UI, or whether the mock is what a reviewer would see.
  **Owner:** Step 1 findings, resolved in Step 7 after evidence.
- **M2 (Correctness):** The README's prototype list is stale in at least the reports
  case and does not mention that dashboard, investigations, and integrations each keep
  one mock panel. **Owner:** Step 4.

Nothing in `mock_data.py` is provably dead. Every symbol has at least one importer.
Step 7 must not delete this file wholesale.

---

## Environment variable audit

`config/settings.py` makes 54 `os.getenv` reads through `load_config`.
`.env.example` documents 56 keys. The differences:

| Variable | In `.env.example` | Read by | Finding |
|---|---|---|---|
| `ENVIRONMENT` | No | `db/reset_demo.py:17` | Undocumented. See C2. |
| `DEMO_USERNAME` | Yes | `db/bootstrap_user.py:50` | Correct, read outside `config.settings` by design. |
| `DEMO_PASSWORD` | Yes, empty | `db/bootstrap_user.py:33` | Correct. Empty value is intentional and the README explains it. |
| `APP_ENV` | Yes | `config/settings.py:289` maps it to `environment` | Correct, but the name mismatch with `ENVIRONMENT` is confusing. |

All four reads outside `config.settings` are accounted for. No variable in
`.env.example` is unused. No secret value is present in `.env.example`; `ELASTIC_API_KEY`,
`ELASTIC_PASSWORD`, `AI_API_KEY`, and `DEMO_PASSWORD` are all empty.

`config.settings.AppConfig.to_safe_dict` redacts `postgres_password`,
`elastic_api_key`, `elastic_password`, and `ai_api_key`. That list matches the
sensitive variables present.

---

## Release artifacts

| Artifact | State | Finding | Owner |
|---|---|---|---|
| `LICENSE` | Present, MIT | Copyright line reads `Copyright (c) 2026` with no holder named. Polish. | Step 7 |
| `SECURITY.md` | Present, accurate | Reporting flow and no-SLA framing are appropriate for a portfolio project. No change needed. | — |
| `.gitignore` | Present, effective | Covers `.env`, `.venv/`, caches, logs, `.DS_Store`. Verified no generated file is tracked. | — |
| `.gitleaks.toml` | Present | Wired into CI via `gitleaks/gitleaks-action@v2`. Should also be runnable locally and documented. | Step 7 |
| `.env.example` | Present | Missing `ENVIRONMENT`. See C2. | Step 7 |
| `CHANGELOG.md` | Absent | No release history exists for six shipped phases. | Step 7 |
| `docs/demo.md` | Absent | The only walkthrough lives in the README. | Step 3 |
| `docs/ai-safety.md` | Absent | The AI posture is the most misunderstood part of this project. See B1, B2. | Step 5 |
| `docs/development.md` | Absent | No contributor setup, migration, or testing guide. | Step 5 |
| `docs/detections.md` | Absent | `docs/detection-schema.md` covers event-time semantics only, not rule authoring or execution. | Step 5 |
| `docs/images/` | Absent | No screenshot exists anywhere in the repository. | Step 6 |

### R1 — `.idea/` is tracked

Five JetBrains project files are committed: `.idea/.gitignore`,
`ai-soc-copilot.iml`, `misc.xml`, `modules.xml`, `vcs.xml`. These are editor-local and
carry no value for a reader. Removing them is safe but is a deletion, so it needs the
Step 7 evidence rule applied.

**Priority:** Polish. **Owner:** Step 7.

---

## Screenshot and privacy considerations

The seeded attack chain uses real-looking identifiers defined at `db/seed.py:35-40`:

- `TARGET_USER = "mollysohaney"`, which is the repository owner's name and appears in
  alert titles, event messages, and file paths such as
  `/home/mollysohaney/.ssh/authorized_keys`.
- `ATTACKER_IP = "192.168.64.2"`, `TARGET_IP = "192.168.64.8"`, and
  `TARGET_HOST = "ubuntu-target-01"`, all RFC 1918 or clearly synthetic.

The addresses and hostname are fine. The username is the owner's own name and will
appear in every screenshot taken for Step 6. That is the owner's choice to make, not a
leak, but it should be a deliberate decision rather than an accident.

**S1 (Polish):** Decide whether the seeded username stays. Changing it touches seed
data and the tests that assert on it, so it is only worth doing if the owner wants it.
**Owner:** Step 6 to raise, owner to decide.

---

## Confirmed accurate

Recording what checks out, so later steps do not re-litigate it:

- `db/seed.py` is deterministic. `BASE_TIME` is a fixed constant at line 35 and every
  timestamp derives from it. Alert identifiers `ALERT-0001` through `ALERT-0006` are
  hardcoded `external_id` values, so `docs/demo.md` may cite them safely.
- The README's walkthrough claim that `ALERT-0005` has three linked events is correct:
  `persistence_specs` at `db/seed.py:290` defines exactly three, and
  `_link_alert_events` at line 583 links them.
- The README's MITRE claim for `ALERT-0005` is correct: `mitre_technique_id`
  is `T1098.004` and `mitre_tactic` is `Persistence`, seeded at lines 572-574.
- Seed idempotency holds. Every insert goes through `get_or_create` on a natural key.
- All three relative links in the README resolve.
- The full test suite passes from the current tree.
- No generated artifact, log, cache, or `.env` is tracked.
- `docker-compose.yml`, `db/session.py`, and `alembic/env.py` all derive their
  connection from `config.settings.AppConfig.database_url`, so migrations and the
  application cannot drift apart.

---

## Prioritized fix order

1. **B1, B4, B5, B6, C2, C8** in Step 2. Without a working, documented demo path
   nothing downstream can be validated.
2. **B1 wording, B6 narration, C1** in Step 3, once the path is real and the AI
   configuration and demo roles are settled.
3. **B3, C1, C5 pointer, C7, M2** in Step 4.
4. **B2, C3, C4, C5** in Step 5.
5. **S1** raised in Step 6.
6. **M1, C6, R1, `ENVIRONMENT` documentation, `CHANGELOG.md`** in Step 7.
7. Everything re-verified end to end in Step 8.

## Deferred

- Wiring a live AI vendor behind the existing provider abstraction. The abstraction,
  prompts, context assembly, schema validation, and abuse controls all exist; only the
  vendor client is missing. This is a product change and is out of Phase 7 scope.
- Replacing the remaining prototype pages (`analyze_alert`, `threat_intel`, and the
  static panels on dashboard, investigations, and integrations) with live data.
- Splitting `requirements.txt` into runtime and development sets, which changes what CI
  installs.
