# Phase 4 regression gate and demo runbook

Phase 4 uses deterministic, data-only detection rules. There are no AI/LLM
calls in the detection DSL, matcher, evaluators, execution service, or seeded
pack. The canonical event-time column is `events.timestamp`; ingestion time is
never used for rule windows.

## Run from a clean checkout

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
docker compose up -d
alembic upgrade head
python -m db.seed
uvicorn api.main:app --reload --port 8000
streamlit run app/main.py
```

Use the Detection Rules page to review a structured rule, click **Test rule**
for a no-write dry run, and use the confirmed **Run now** action to persist a
run and its alerts. The same operations are available at
`POST /api/v1/rules/validate`, `POST /api/v1/rules/test`, and
`POST /api/v1/rules/execute`.

## Semantics and safeguards

- Threshold windows are fixed tumbling windows with `[start, end)` boundaries.
- Sequence matching is earliest-match-per-stage; unrelated interleaved events
  do not break a chain, and sequence stages have bounded count/span limits.
- Missing fields never satisfy ordinary predicates. Use `exists` or
  `not_exists` explicitly; `not_equals` on a missing field is false.
- Rule fingerprints include rule ID, rule version, correlation values, and
  deterministic evidence. A repeated or overlapping run updates the existing
  alert rather than duplicating it.
- Every execution has a configured lookback and `max_events_scanned` cap.
  Oversized windows are rejected and truncation is returned in the result.
- Seed data and rule timestamps are fixed; `python -m db.seed` is idempotent.

## Verification

Run the full gate with:

```bash
pytest -q
```

The Phase 4 gate includes all prior Phase 2/3 tests plus deterministic seeded
execution, overlap reruns, oversized-window rejection, scan-cap surfacing,
and DSL/matcher/evaluator unit tests. The closing run on this branch produced
`230 passed`.

Known limitation: the seeded pack retains the existing Phase 2 network-volume
rule for compatibility, while its structured sequence logic exercises the
complete brute-force → login → privilege-escalation → SSH-key persistence
chain. Production tuning should review thresholds, lookback windows, and
suppression periods against the tenant's event volume.
