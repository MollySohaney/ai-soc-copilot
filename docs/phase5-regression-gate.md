# Phase 5 regression gate and demo runbook

Phase 5 adds advisory AI assistance around the deterministic SOC workflow. The
provider receives bounded context assembled from the active alert or case; it
does not receive database, shell, remediation, or arbitrary external-system
tools.

## Configuration

AI is disabled by default. Copy `.env.example` and set only environment
variables; never put an API key in a request, database row, source file, or log.

```text
AI_ENABLED=false
AI_PROVIDER=fake
AI_MODEL=fake-model
AI_API_KEY=
AI_REQUEST_TIMEOUT_SECONDS=30
AI_MAX_INPUT_TOKENS=4000
AI_MAX_OUTPUT_TOKENS=1000
AI_PROMPT_VERSION=v1
AI_RESPONSE_SCHEMA_VERSION=v1
```

The current provider implementation is the deterministic fake provider. It is
intended for tests and local demos; unsupported providers fail closed. A future
provider adapter must preserve the same normalized request/response/error and
usage contract.

## Architecture and safety boundary

1. `backend.ai.context` retrieves only an explicit alert or case and linked
   events, rule snapshots, MITRE metadata, and analyst notes.
2. Context has stable evidence IDs, deterministic item/character bounds,
   timestamps, redaction, and raw-field untrusted-data markers.
3. `backend.ai.prompts` states that evidence is data, not instructions.
4. `backend.ai.provider` exposes one completion operation and normalized usage
   and safe errors. The unavailable provider keeps the rest of the app working.
5. `backend.ai.triage` validates structured output and rejects citations absent
   from the current context.
6. `AIAnalysis` records each finalized attempt append-only with provenance.
   GET/history endpoints never invoke a provider.

## Usage and cost controls

- Use `AI_MAX_INPUT_TOKENS`, `AI_MAX_OUTPUT_TOKENS`, and
  `AI_REQUEST_TIMEOUT_SECONDS` as hard request bounds.
- Keep provider/model selection server-side and credentials environment-only.
- Preserve usage, latency, rate-limit remaining, and estimated-cost fields on
  analysis records for future quotas and budgets.
- Add rate limiting and budget enforcement before enabling a real provider in
  production. The application currently does not enforce a monetary budget.
- Use the fake provider for CI and most development to avoid cost and data
  egress.

## Privacy and prompt-injection model

Raw messages, raw events, raw payloads, analyst questions, and analyst notes
are untrusted input. They may contain instructions such as “ignore prior
instructions,” requests to reveal secrets, or requests to change conclusions.
The prompt labels them as data, redacts secret-like keys and values, and the
server validates output citations and schema after completion. The model is
never authorized to mutate SOC state or execute actions.

## Regression commands

Run with AI disabled:

```bash
AI_ENABLED=false pytest -q
```

Run Phase 5 provider/API/adversarial coverage with the fake provider:

```bash
AI_ENABLED=true AI_PROVIDER=fake pytest -q tests/test_ai_api.py tests/test_ai_copilot.py tests/test_ai_reports.py tests/test_ai_injection.py tests/test_ai_triage.py tests/test_ai_context.py
```

The final gate on this branch produced 264 passing tests with AI disabled and
19 focused fake-provider/adversarial tests. No real API key was present or
used, so no real-provider smoke request was made.

## Exact seeded demo

1. Start PostgreSQL and apply migrations: `docker compose up -d`, then
   `alembic upgrade head`.
2. Seed the deterministic attack investigation: `python -m db.seed`.
3. Enable the fake provider with `AI_ENABLED=true AI_PROVIDER=fake`, then
   start `uvicorn api.main:app --reload --port 8000` and
   `streamlit run app/main.py`.
4. Open Investigations and select seeded `ALERT-0005`.
5. Confirm the page does not run AI on load. Click **Analyze with AI**.
6. Verify the result separates observed facts and assessment, shows confidence,
   missing information, next steps, and valid `event-*`/`alert-*` references.
7. Put malicious text in a test event and repeat; it remains untrusted evidence
   and cannot create a valid citation or change alert state.
8. Open Cases, select `CASE-2026-0001`, and use the case-scoped Ask Copilot or
   report-draft action when enabled by the corresponding UI workflow.
9. Set `AI_ENABLED=false` and verify deterministic alerts, cases, rules, and
   reports still load and operate.

## Known limitations

- The only provider currently implemented is deterministic fake; a production
  provider adapter and real-key smoke test remain future work.
- Authentication/authorization is not yet implemented in the application, so
  deployment still requires a trusted network boundary.
- Rate limiting and monetary budget enforcement are metadata/planning fields,
  not active controls.
- Analyst feedback is currently session-only.
- Report and Q&A UI coverage is intentionally incremental while later Phase 5
  integration work expands it.
