"""Persistence boundary for bounded, idempotent detection execution."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from backend.detection.dsl import DetectionLogic, parse_logic
from backend.detection.matcher import match_event
from backend.detection.sequence import SequenceMatch, evaluate_sequence
from backend.detection.threshold import ThresholdMatch, evaluate_threshold
from db.models import Alert, DetectionRule, DetectionRun, Event, SeverityEnum
from db.models.alert import alert_event


@dataclass(frozen=True)
class ExecutionResult:
    """Summary returned by a real or dry-run execution."""

    status: str
    run_id: int | None
    events_scanned: int
    alerts_created: tuple[int, ...]
    would_fire: tuple[dict[str, Any], ...] = ()
    truncated: bool = False
    error_detail: str | None = None


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("execution windows must be timezone-aware")
    return value.astimezone(timezone.utc)


def _fingerprint(rule: DetectionRule, firing: dict[str, Any]) -> str:
    payload = {"rule_id": rule.id, "version": rule.version, **firing}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _event_field(event: Event, field: str) -> Any:
    # Evaluator output only asks for these stable summary fields.
    return {"hostname": event.hostname, "username": event.username, "source_ip": event.source_ip}.get(field)


def execute_rule(
    db: Session,
    rule: DetectionRule,
    *,
    window_start: datetime,
    window_end: datetime,
    dry_run: bool = False,
) -> ExecutionResult:
    """Execute one enabled rule over a bounded event-time window.

    Candidate retrieval is limited to ``max_events_scanned + 1`` so truncation
    is observable. Real runs are recorded before evaluation and finalized on
    success or failure. Dry runs perform no database writes.
    """
    if not rule.enabled_for_execution:
        return ExecutionResult("skipped", None, 0, ())
    start, end = _utc(window_start), _utc(window_end)
    if end <= start:
        raise ValueError("window_end must be after window_start")
    if end - start > timedelta(seconds=rule.lookback_window_seconds):
        raise ValueError("requested window exceeds the rule lookback window")
    logic = parse_logic(rule.structured_logic or {})
    query = (
        select(Event).where(Event.timestamp >= start, Event.timestamp < end)
        .order_by(Event.timestamp.asc(), Event.event_id.asc())
        .limit(rule.max_events_scanned + 1)
    )
    candidates = list(db.scalars(query))
    truncated = len(candidates) > rule.max_events_scanned
    candidates = candidates[: rule.max_events_scanned]
    run = None
    if not dry_run:
        run = DetectionRun(
            detection_rule_id=rule.id, rule_version=rule.version,
            window_start=start, window_end=end, status="running", dry_run=False,
        )
        db.add(run)
        db.flush()
        # Commit the run header first so a later evaluator or persistence
        # failure can be recorded as a failed run without being rolled back.
        db.commit()
    try:
        firings: list[dict[str, Any]] = []
        if logic.rule_type == "single" and logic.condition is not None:
            firings = [
                {"evidence_event_ids": [event.event_id], "explanation": match_event(event, logic.condition).explanation.to_dict()}
                for event in candidates if match_event(event, logic.condition).matched
            ]
        elif logic.rule_type == "threshold":
            firings = [{"group": item.group, "evidence_event_ids": list(item.evidence_event_ids)} for item in evaluate_threshold(candidates, logic, start, end)]
        else:
            firings = [{"correlation": item.correlation, "stage_evidence": {key: list(value) for key, value in item.stage_evidence.items()}, "explanation": {"matched": True, "operator": "sequence", "stages": {key: list(value) for key, value in item.stage_evidence.items()}}} for item in evaluate_sequence(candidates, logic)]
        if dry_run:
            return ExecutionResult("dry_run", None, len(candidates), (), tuple(firings), truncated)
        alert_ids: list[int] = []
        for firing in firings:
            fingerprint = _fingerprint(rule, firing)
            existing = db.scalar(select(Alert).where(Alert.fingerprint == fingerprint))
            evidence_ids = set(firing.get("evidence_event_ids", []))
            for ids in firing.get("stage_evidence", {}).values():
                evidence_ids.update(ids)
            evidence = list(db.scalars(select(Event).where(Event.event_id.in_(evidence_ids))))
            if not evidence:
                continue
            last_seen = max(event.timestamp for event in evidence)
            if existing is not None:
                existing.last_seen = max(existing.last_seen or last_seen, last_seen)
                continue
            alert = Alert(
                title=rule.name, description=rule.description, severity=rule.severity,
                risk_score=rule.risk_score, source="detection_engine", rule_id=str(rule.id),
                detection_rule_id=rule.id, rule_version=rule.version, detection_run_id=run.id,
                fingerprint=fingerprint, rule_logic_snapshot=rule.structured_logic,
                match_explanation=firing.get("explanation"), first_seen=min(event.timestamp for event in evidence),
                last_seen=last_seen, hostname=next((_event_field(e, "hostname") for e in evidence if _event_field(e, "hostname")), None),
                username=next((_event_field(e, "username") for e in evidence if _event_field(e, "username")), None),
                source_ip=next((_event_field(e, "source_ip") for e in evidence if _event_field(e, "source_ip")), None),
                mitre_tactic=rule.mitre_tactic, mitre_technique_id=rule.mitre_technique_id,
                mitre_technique_name=rule.mitre_technique_name, events=evidence,
            )
            db.add(alert)
            db.flush()
            for stage, stage_ids in firing.get("stage_evidence", {}).items():
                db.execute(
                    update(alert_event)
                    .where(alert_event.c.alert_id == alert.id)
                    .where(alert_event.c.event_id.in_(
                        [event.id for event in evidence if event.event_id in stage_ids]
                    ))
                    .values(stage=stage)
                )
            alert_ids.append(alert.id)
        run.status = "completed"
        run.events_scanned = len(candidates)
        run.alerts_created = len(alert_ids)
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        return ExecutionResult("completed", run.id, len(candidates), tuple(alert_ids), tuple(firings), truncated)
    except Exception as error:
        if run is not None:
            db.rollback()
            run = db.get(DetectionRun, run.id)
            if run is not None:
                run.status, run.error_detail = "failed", str(error)
                run.events_scanned, run.finished_at = len(candidates), datetime.now(timezone.utc)
                db.commit()
        raise


class DetectionExecutionService:
    """Service wrapper exposing the execution operation."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def execute(self, rule: DetectionRule, **kwargs: Any) -> ExecutionResult:
        return execute_rule(self.db, rule, **kwargs)


__all__ = ["DetectionExecutionService", "ExecutionResult", "execute_rule"]
