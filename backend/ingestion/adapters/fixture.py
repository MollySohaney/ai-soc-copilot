"""Purpose: Provide a deterministic ingestion adapter for tests and demos."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.ingestion.dto import (
    AdapterHealth,
    IngestionCheckpointState,
    IngestionFetchRequest,
    IngestionPage,
    SourceRecord,
)


class FixtureIngestionAdapter:
    """Serve stable telemetry records from memory using offset checkpoints."""

    def __init__(
        self,
        records: list[SourceRecord] | None = None,
        *,
        source_name: str = "fixture-default",
    ) -> None:
        """Initialize the adapter with deterministic records sorted by timestamp and id."""
        self._source_name = source_name
        self._records = sorted(
            records or _default_records(source_name=source_name),
            key=lambda record: (record.timestamp, record.record_id),
        )

    @property
    def provider(self) -> str:
        """Return the fixture provider identifier."""
        return "fixture"

    @property
    def source_name(self) -> str:
        """Return the configured fixture source name."""
        return self._source_name

    def test_connection(self) -> AdapterHealth:
        """Return a successful health result for the in-memory fixture source."""
        return AdapterHealth(
            provider=self.provider,
            source_name=self.source_name,
            ok=True,
            message="Fixture ingestion source is available.",
        )

    def fetch_records(self, request: IngestionFetchRequest) -> IngestionPage:
        """Return one bounded deterministic page of fixture records."""
        matching_records = [
            record
            for record in self._records
            if request.start_time <= record.timestamp < request.end_time
        ]
        offset = _checkpoint_offset(request.checkpoint)
        page_records = matching_records[offset : offset + request.limit]
        next_offset = offset + len(page_records)
        has_more = next_offset < len(matching_records)

        next_checkpoint = IngestionCheckpointState(
            provider=self.provider,
            source_name=self.source_name,
            values={"offset": next_offset},
        )
        return IngestionPage(
            records=page_records,
            next_checkpoint=next_checkpoint,
            has_more=has_more,
        )


def _checkpoint_offset(checkpoint: IngestionCheckpointState | None) -> int:
    if checkpoint is None:
        return 0
    raw_offset = checkpoint.values.get("offset", 0)
    if not isinstance(raw_offset, int) or raw_offset < 0:
        return 0
    return raw_offset


def _default_records(source_name: str) -> list[SourceRecord]:
    timestamp = datetime(2026, 8, 15, 2, 0, tzinfo=timezone.utc)
    records: list[dict[str, Any]] = [
        {
            "record_id": "fixture-auth-failure-1",
            "source_index": "fixture-auth",
            "timestamp": timestamp,
            "payload": {
                "@timestamp": "2026-08-15T02:00:00Z",
                "event": {"category": "authentication", "action": "ssh_login", "outcome": "failure"},
                "source": {"ip": "192.168.64.2"},
                "destination": {"ip": "192.168.64.8", "port": 22},
                "host": {"name": "ubuntu-target-01"},
                "user": {"name": "mollysohaney"},
                "process": {"name": "sshd"},
                "message": "Failed password for mollysohaney from 192.168.64.2 port 51000 ssh2",
            },
        },
        {
            "record_id": "fixture-process-1",
            "source_index": "fixture-process",
            "timestamp": timestamp.replace(minute=6),
            "payload": {
                "@timestamp": "2026-08-15T02:06:00Z",
                "event": {"category": "process", "action": "sudo_exec", "outcome": "success"},
                "host": {"name": "ubuntu-target-01"},
                "user": {"name": "mollysohaney"},
                "process": {"name": "sudo", "command_line": "sudo -i"},
                "message": "session opened for user root by mollysohaney(uid=1000)",
            },
        },
        {
            "record_id": "fixture-network-1",
            "source_index": "fixture-network",
            "timestamp": timestamp.replace(hour=3),
            "payload": {
                "@timestamp": "2026-08-15T03:00:00Z",
                "event": {"category": "network", "action": "connection_opened", "outcome": "success"},
                "source": {"ip": "10.0.1.15"},
                "destination": {"ip": "93.184.216.34", "port": 443},
                "host": {"name": "web-prod-02"},
                "message": "Outbound connection from web-prod-02 to 93.184.216.34:443",
            },
        },
    ]
    return [
        SourceRecord(
            provider="fixture",
            source_name=source_name,
            cursor=[record["timestamp"].isoformat(), record["record_id"]],
            **record,
        )
        for record in records
    ]
