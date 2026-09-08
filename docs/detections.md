# Detections

**Audience:** anyone authoring a rule or trying to understand why an alert did or did
not fire.

The storage contract, versioning rules, and window boundary semantics live in
[docs/detection-schema.md](detection-schema.md). This document covers authoring and
execution. Neither repeats the other.

## What a detection is here

A rule is structured logic evaluated against events in a bounded event-time window. No
part of it involves a language model. Given the same events, the same rule version, and
the same window, execution produces the same alerts. That determinism is the whole
point: it makes the AI layer's opinions checkable against something stable.

## The three rule types

Rules live in `backend/detection/`. `dsl.py` parses structured logic; the evaluators are
separate modules.

**Single event** (`matcher.py`). One event satisfying a condition tree. Conditions
combine with `equals`, `contains`, and similar operators over event fields.

**Threshold** (`threshold.py`). At least *N* events matching a condition within a fixed
tumbling window, grouped by shared keys. Windows are anchored at the requested run
start, and every window is `[start, end)`. The seeded SSH brute force rule is this
shape: five or more authentication failures from one source.

**Sequence** (`sequence.py`). Ordered stages that must all occur within
`max_span_seconds`, correlated by shared keys. The seeded attack chain rule is this
shape:

```json
{
  "dsl_version": "1",
  "rule_type": "sequence",
  "shared_keys": ["source_ip", "username", "hostname"],
  "max_span_seconds": 900,
  "stages": [
    {"label": "failed", "condition": {"operator": "equals", "field": "event_outcome", "value": "failure"}, "min_count": 5},
    {"label": "success", "condition": {"operator": "equals", "field": "event_outcome", "value": "success"}},
    {"label": "privilege_escalation", "condition": {"operator": "equals", "field": "process_name", "value": "sudo"}},
    {"label": "persistence", "condition": {"operator": "contains", "field": "file_path", "value": ".ssh/authorized_keys"}}
  ]
}
```

That rule is the reason the demo has a story rather than a pile of alerts.

## Authoring a rule

Four routes, all requiring `manage_detections` (Detection Engineer or Admin):

| Purpose | Route |
|---|---|
| Check logic parses, without saving | `POST /api/v1/rules/validate` |
| Dry run against real events, no writes | `POST /api/v1/rules/test` |
| Create or update | `POST /api/v1/rules`, `PATCH /api/v1/rules/{id}` |
| Execute for real | `POST /api/v1/rules/execute` |

Validate first, then dry run, then execute. A dry run returns `would_fire` entries and
creates no alerts and no persisted run.

## Fields that govern execution

| Field | Meaning |
|---|---|
| `enabled_for_execution` | Execution returns `skipped` when false. Distinct from `enabled`. |
| `lookback_window_seconds` | The default window, and a hard cap on any explicit window |
| `max_events_scanned` | Candidate limit; retrieval fetches one extra so truncation is visible |
| `suppression_window_seconds` | Suppresses repeat alerts |
| `severity`, `risk_score` | Applied to alerts the rule creates |
| `mitre_tactic`, `mitre_technique_id` | Attached to alerts for the MITRE view |

## The window rule that trips people up

An explicit window wider than the rule's own `lookback_window_seconds` is **rejected**
with a 422, not silently truncated:

```python
if end - start > timedelta(seconds=rule.lookback_window_seconds):
    raise ValueError("requested window exceeds the rule lookback window")
```

Every seeded rule sets 3600. So a one-day execution window fails, while a one-hour
window succeeds. The demo pipeline uses one hour for exactly this reason, and a
separate one-day window for ingestion, which has no such constraint.

Omit `window_start` and the service computes it as `window_end` minus the rule's
lookback, which is always valid.

## What execution does

1. Load the rule. A missing rule is a 404.
2. Compute the window and validate it against the rule's lookback.
3. Return `skipped` if the rule is not enabled for execution.
4. Write a `DetectionRun` header before evaluating, so a crash leaves a trace.
5. Select candidate events by `events.timestamp`, ordered, limited to
   `max_events_scanned + 1`.
6. Evaluate.
7. Create alerts, each with a fingerprint, a rule version, a run reference, and a JSON
   snapshot of the logic that fired.
8. Commit the run and its alerts together, and record an audit event.

Event time, not arrival time. `ingested_at` never moves a late-arriving event into a
different window.

## Why re-running is safe

Alerts carry a unique fingerprint derived from the rule, its version, the correlation
keys, and the deterministic evidence. Re-executing the same rule over an overlapping
window matches the same events and produces the same fingerprints, which the unique
index rejects. So a replay creates nothing new.

Editing rule logic bumps the version and changes the fingerprint, so a genuinely
different rule produces genuinely new alerts. A `DetectionRuleVersion` row preserves the
exact logic behind every version, which is what makes an old alert explainable.

## Seeing it work

```bash
make pipeline
```

On a clean database this executes all five seeded rules over the attack window. First
run creates alerts; second run creates none. Full walkthrough in
[docs/demo.md](demo.md).

## Related

- [docs/detection-schema.md](detection-schema.md) — storage, versioning, window boundaries
- [docs/ingestion.md](ingestion.md) — where events come from
- [docs/architecture.md](architecture.md) — where detection sits
- [docs/permissions.md](permissions.md) — who may author and execute
- [docs/phase4-regression-gate.md](phase4-regression-gate.md) — point-in-time record
