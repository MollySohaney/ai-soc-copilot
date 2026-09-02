# Detection execution schema

Phase 4 uses `events.timestamp` as the canonical event time. Evaluators must
use this column for windows; `ingested_at` describes arrival time only and must
not move a late-arriving event into a different detection window.

`DetectionRule.version` starts at 1. A logic edit creates the next monotonically
increasing version and a `DetectionRuleVersion` row preserves the exact
structured logic, rule type, and legacy query associated with that version.
Existing Phase 2 rules are migrated as version 1 single-event rules with
`enabled_for_execution=false` until their structured logic is supplied.

Executable alerts retain the legacy string `rule_id` for compatibility and use
`detection_rule_id` as the foreign key. They also record `rule_version`, the
`detection_run_id`, a JSON `rule_logic_snapshot`, and a stable `fingerprint`.
The fingerprint is unique: future execution will derive it from the rule ID,
rule version, correlation keys, and deterministic evaluator evidence. Repeated
or overlapping runs therefore identify the same alert, while changes to rule
logic or correlation produce a new fingerprint.

`DetectionRun` records bounded execution metadata, including its event-time
window, scan count, result status, and dry-run flag. `alert_event.stage` is
reserved for labeling evidence belonging to a sequence stage.
