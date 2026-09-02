"""Purpose: Assemble bounded, redacted, case-scoped evidence for AI requests."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import Alert, Case, CaseActivity, CaseAlert, Event

_SECRET_KEY = re.compile(r"(password|passwd|secret|token|api[_-]?key|authorization|private[_-]?key)", re.I)
_SECRET_VALUE = re.compile(r"(?i)(password|passwd|secret|token|api[_-]?key|authorization|private[_-]?key)\s*[:=]\s*[^\s,;]+")


@dataclass(frozen=True)
class EvidenceItem:
    """Represent one cited item available to the model."""

    evidence_id: str
    source_type: str
    timestamp: datetime | None
    content: dict[str, Any]
    untrusted: bool = False


@dataclass(frozen=True)
class EvidenceContext:
    """Represent the bounded context and the IDs valid for citation."""

    items: tuple[EvidenceItem, ...]
    text: str
    truncated: bool

    @property
    def evidence_ids(self) -> frozenset[str]:
        """Return the only IDs that may be cited for this context."""
        return frozenset(item.evidence_id for item in self.items)


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: "[REDACTED]" if _SECRET_KEY.search(str(key)) else _redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, str):
        return _SECRET_VALUE.sub(lambda match: f"{match.group(1)}=[REDACTED]", value)
    return value


def _item(evidence_id: str, source_type: str, timestamp: datetime | None, content: dict[str, Any], *, untrusted: bool = False) -> EvidenceItem:
    return EvidenceItem(evidence_id, source_type, timestamp, _redact(content), untrusted)


def _event_item(event: Event) -> EvidenceItem:
    return _item(
        f"event-{event.event_id}",
        "event",
        event.timestamp,
        {
            "event_id": event.event_id,
            "source": event.source,
            "event_category": event.event_category,
            "event_action": event.event_action,
            "event_outcome": event.event_outcome,
            "severity": event.severity,
            "source_ip": event.source_ip,
            "destination_ip": event.destination_ip,
            "hostname": event.hostname,
            "username": event.username,
            "process_name": event.process_name,
            "process_command_line": event.process_command_line,
            "file_path": event.file_path,
            "message": event.message,
            "raw_event": event.raw_event,
            "raw_payload": event.raw_payload,
            "untrusted_fields": ["message", "raw_event", "raw_payload"],
        },
        untrusted=True,
    )


def build_evidence_context(
    db: Session,
    *,
    alert_id: int | None = None,
    case_id: int | None = None,
    max_items: int = 100,
    max_chars: int = 20_000,
) -> EvidenceContext:
    """Build deterministic context from one alert or one case and linked records."""
    if (alert_id is None and case_id is None) or max_items <= 0 or max_chars <= 0:
        raise ValueError("An alert or case scope and positive context limits are required.")
    case = db.scalar(select(Case).where(Case.id == case_id)) if case_id is not None else None
    if case_id is not None and case is None:
        raise ValueError("Case not found.")
    alert_ids: list[int]
    if case is not None:
        alert_ids = [link.alert_id for link in db.scalars(select(CaseAlert).where(CaseAlert.case_id == case.id))]
        if alert_id is not None and alert_id not in alert_ids:
            raise ValueError("Alert is not linked to the requested case.")
    else:
        alert_ids = [alert_id]  # type: ignore[list-item]
    alerts = list(db.scalars(select(Alert).where(Alert.id.in_(alert_ids)).order_by(Alert.id)))
    if len(alerts) != len(set(alert_ids)):
        raise ValueError("One or more scoped alerts were not found.")

    items: list[EvidenceItem] = []
    if case is not None:
        items.append(_item(f"case-{case.id}", "case", case.created_at, {"case_number": case.case_number, "title": case.title, "description": case.description, "status": case.status.value, "priority": case.priority.value}))
    for alert in alerts:
        items.append(_item(f"alert-{alert.id}", "alert", alert.created_at, {"external_id": alert.external_id, "title": alert.title, "description": alert.description, "severity": alert.severity.value, "status": alert.status.value, "risk_score": alert.risk_score, "first_seen": alert.first_seen, "last_seen": alert.last_seen}))
        if alert.rule_logic_snapshot is not None:
            items.append(_item(f"rule-snapshot-{alert.id}", "rule_snapshot", alert.last_seen, {"rule_id": alert.rule_id, "rule_version": alert.rule_version, "logic": alert.rule_logic_snapshot}))
        if alert.mitre_technique_id or alert.mitre_tactic:
            items.append(_item(f"mitre-{alert.id}", "mitre", alert.last_seen, {"tactic": alert.mitre_tactic, "technique_id": alert.mitre_technique_id, "technique_name": alert.mitre_technique_name}))
        items.extend(_event_item(event) for event in sorted(alert.events, key=lambda event: (event.timestamp, event.event_id)))
    if case is not None:
        notes = db.scalars(select(CaseActivity).where(CaseActivity.case_id == case.id).order_by(CaseActivity.created_at, CaseActivity.id))
        items.extend(_item(f"note-{note.id}", "analyst_note", note.created_at, {"activity_type": note.activity_type, "message": note.message, "author": note.author}) for note in notes)

    selected: list[EvidenceItem] = []
    used = 0
    truncated = len(items) > max_items
    for candidate in items:
        if len(selected) >= max_items:
            break
        encoded = json.dumps({"evidence_id": candidate.evidence_id, "source_type": candidate.source_type, "timestamp": candidate.timestamp, "content": candidate.content, "untrusted": candidate.untrusted}, sort_keys=True, default=str)
        if used + len(encoded) > max_chars:
            truncated = True
            break
        selected.append(candidate)
        used += len(encoded)
    text = "\n".join(json.dumps({"evidence_id": item.evidence_id, "source_type": item.source_type, "timestamp": item.timestamp, "content": item.content, "untrusted": item.untrusted}, sort_keys=True, default=str) for item in selected)
    return EvidenceContext(tuple(selected), text, truncated)
