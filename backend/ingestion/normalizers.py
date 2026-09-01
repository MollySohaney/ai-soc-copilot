"""Purpose: Normalize provider source records into canonical Event fields."""

from __future__ import annotations

from datetime import datetime
from ipaddress import ip_address
from typing import Any

from pydantic import BaseModel, Field

from backend.ingestion.dto import SourceRecord

NORMALIZATION_VERSION = "ecs-v1"


class NormalizedEvent(BaseModel):
    """Represent an Event-compatible normalized telemetry payload."""

    event_id: str
    dedup_key: str
    timestamp: datetime
    source: str
    source_provider: str
    source_instance: str
    source_index: str | None = None
    source_record_id: str
    dataset: str | None = None
    event_category: str | None = None
    event_action: str | None = None
    event_outcome: str | None = None
    message: str | None = None
    severity: str | None = None
    source_ip: str | None = None
    source_port: int | None = None
    destination_ip: str | None = None
    destination_port: int | None = None
    hostname: str | None = None
    username: str | None = None
    process_name: str | None = None
    process_command_line: str | None = None
    file_path: str | None = None
    normalization_version: str = NORMALIZATION_VERSION
    normalization_warnings: list[str] = Field(default_factory=list)
    raw_payload: dict[str, Any]
    raw_event: dict[str, Any]

    def to_event_kwargs(self) -> dict[str, Any]:
        """Return keyword arguments suitable for constructing an Event ORM instance."""
        return self.model_dump()


class EcsEventNormalizer:
    """Normalize common Elastic Common Schema fields into canonical event fields."""

    version = NORMALIZATION_VERSION

    def normalize(self, record: SourceRecord) -> NormalizedEvent:
        """Normalize one source record into canonical Event fields."""
        warnings: list[str] = []
        payload = record.payload
        timestamp = _timestamp(payload.get("@timestamp"), fallback=record.timestamp, warnings=warnings)
        source_ip = _ip(_nested(payload, "source", "ip"), "source.ip", warnings)
        destination_ip = _ip(_nested(payload, "destination", "ip"), "destination.ip", warnings)

        event_id = f"{record.provider}:{record.source_name}:{record.record_id}"
        return NormalizedEvent(
            event_id=event_id,
            dedup_key=record.dedup_key,
            timestamp=timestamp,
            source=record.provider,
            source_provider=record.provider,
            source_instance=record.source_name,
            source_index=record.source_index,
            source_record_id=record.record_id,
            dataset=_text(_nested(payload, "event", "dataset")),
            event_category=_text(_nested(payload, "event", "category")),
            event_action=_text(_nested(payload, "event", "action")),
            event_outcome=_text(_nested(payload, "event", "outcome")),
            message=_text(payload.get("message")),
            severity=_text(_nested(payload, "event", "severity") or _nested(payload, "log", "level")),
            source_ip=source_ip,
            source_port=_port(_nested(payload, "source", "port"), "source.port", warnings),
            destination_ip=destination_ip,
            destination_port=_port(
                _nested(payload, "destination", "port"), "destination.port", warnings
            ),
            hostname=_text(_nested(payload, "host", "name")),
            username=_text(_nested(payload, "user", "name")),
            process_name=_text(_nested(payload, "process", "name")),
            process_command_line=_text(_nested(payload, "process", "command_line")),
            file_path=_text(_nested(payload, "file", "path")),
            normalization_version=self.version,
            normalization_warnings=warnings,
            raw_payload=payload,
            raw_event=payload,
        )


def _nested(payload: dict[str, Any], *path: str) -> Any:
    value: Any = payload
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        return ",".join(str(item) for item in value if item is not None) or None
    return str(value)


def _timestamp(value: Any, *, fallback: datetime, warnings: list[str]) -> datetime:
    if value is None:
        warnings.append("missing @timestamp; used source record timestamp")
        return fallback
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            warnings.append("invalid @timestamp; used source record timestamp")
            return fallback
    warnings.append("invalid @timestamp type; used source record timestamp")
    return fallback


def _ip(value: Any, field_name: str, warnings: list[str]) -> str | None:
    if value is None:
        return None
    try:
        return str(ip_address(str(value)))
    except ValueError:
        warnings.append(f"invalid {field_name}; omitted")
        return None


def _port(value: Any, field_name: str, warnings: list[str]) -> int | None:
    if value is None:
        return None
    try:
        port = int(value)
    except (TypeError, ValueError):
        warnings.append(f"invalid {field_name}; omitted")
        return None
    if port < 0 or port > 65535:
        warnings.append(f"invalid {field_name}; omitted")
        return None
    return port
