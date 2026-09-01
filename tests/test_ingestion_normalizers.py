"""Purpose: Verify ECS telemetry normalization into canonical event fields."""

from __future__ import annotations

from datetime import datetime, timezone

from backend.ingestion import EcsEventNormalizer, FixtureIngestionAdapter, NORMALIZATION_VERSION
from backend.ingestion.dto import SourceRecord


BASE_TIME = datetime(2026, 8, 15, 2, 0, tzinfo=timezone.utc)


def test_normalizes_attack_chain_authentication_event() -> None:
    """Common ECS authentication fields map to canonical Event fields."""
    record = FixtureIngestionAdapter().fetch_records(
        request=_request("2026-08-15T02:00:00+00:00", "2026-08-15T02:01:00+00:00")
    ).records[0]

    normalized = EcsEventNormalizer().normalize(record)

    assert normalized.event_id == "fixture:fixture-default:fixture-auth-failure-1"
    assert normalized.dedup_key == "fixture:fixture-default:fixture-auth:fixture-auth-failure-1"
    assert normalized.timestamp == BASE_TIME
    assert normalized.source == "fixture"
    assert normalized.source_provider == "fixture"
    assert normalized.source_instance == "fixture-default"
    assert normalized.source_index == "fixture-auth"
    assert normalized.source_record_id == "fixture-auth-failure-1"
    assert normalized.event_category == "authentication"
    assert normalized.event_action == "ssh_login"
    assert normalized.event_outcome == "failure"
    assert normalized.source_ip == "192.168.64.2"
    assert normalized.destination_ip == "192.168.64.8"
    assert normalized.destination_port == 22
    assert normalized.hostname == "ubuntu-target-01"
    assert normalized.username == "mollysohaney"
    assert normalized.process_name == "sshd"
    assert normalized.message is not None
    assert "Failed password" in normalized.message
    assert normalized.normalization_version == NORMALIZATION_VERSION
    assert normalized.normalization_warnings == []


def test_normalizes_benign_network_event() -> None:
    """Benign fixture telemetry maps network fields while tolerating missing user data."""
    record = FixtureIngestionAdapter().fetch_records(
        request=_request("2026-08-15T03:00:00+00:00", "2026-08-15T03:01:00+00:00")
    ).records[0]

    normalized = EcsEventNormalizer().normalize(record)

    assert normalized.event_category == "network"
    assert normalized.event_action == "connection_opened"
    assert normalized.event_outcome == "success"
    assert normalized.source_ip == "10.0.1.15"
    assert normalized.destination_ip == "93.184.216.34"
    assert normalized.destination_port == 443
    assert normalized.hostname == "web-prod-02"
    assert normalized.username is None
    assert normalized.normalization_warnings == []


def test_normalizer_preserves_raw_payload_and_event_kwargs() -> None:
    """Normalized output preserves raw evidence and can construct Event kwargs."""
    payload = {
        "@timestamp": "2026-08-15T02:06:00Z",
        "event": {"category": ["process", "session"], "action": "sudo_exec"},
        "process": {"name": "sudo", "command_line": "sudo -i"},
        "file": {"path": "/tmp/example"},
    }
    record = SourceRecord(
        provider="elastic",
        source_name="elastic-test",
        source_index="logs-process",
        record_id="abc123",
        timestamp=BASE_TIME,
        payload=payload,
    )

    normalized = EcsEventNormalizer().normalize(record)
    event_kwargs = normalized.to_event_kwargs()

    assert normalized.event_category == "process,session"
    assert normalized.process_name == "sudo"
    assert normalized.process_command_line == "sudo -i"
    assert normalized.file_path == "/tmp/example"
    assert normalized.raw_payload == payload
    assert normalized.raw_event == payload
    assert event_kwargs["raw_payload"] == payload
    assert event_kwargs["normalization_version"] == NORMALIZATION_VERSION


def test_normalizer_records_warnings_for_invalid_optional_fields() -> None:
    """Malformed timestamp, IP, and port values are omitted with warnings."""
    record = SourceRecord(
        provider="elastic",
        source_name="elastic-test",
        source_index="logs-bad",
        record_id="bad-1",
        timestamp=BASE_TIME,
        payload={
            "@timestamp": "not-a-date",
            "event": {"category": "network", "severity": 4},
            "source": {"ip": "not-an-ip", "port": "not-a-port"},
            "destination": {"ip": "2001:db8::1", "port": 70000},
        },
    )

    normalized = EcsEventNormalizer().normalize(record)

    assert normalized.timestamp == BASE_TIME
    assert normalized.severity == "4"
    assert normalized.source_ip is None
    assert normalized.source_port is None
    assert normalized.destination_ip == "2001:db8::1"
    assert normalized.destination_port is None
    assert normalized.normalization_warnings == [
        "invalid @timestamp; used source record timestamp",
        "invalid source.ip; omitted",
        "invalid source.port; omitted",
        "invalid destination.port; omitted",
    ]


def test_normalizer_warns_when_timestamp_is_missing() -> None:
    """A missing @timestamp falls back to the adapter timestamp with a warning."""
    record = SourceRecord(
        provider="elastic",
        source_name="elastic-test",
        source_index="logs-minimal",
        record_id="minimal-1",
        timestamp=BASE_TIME,
        payload={"message": "minimal record"},
    )

    normalized = EcsEventNormalizer().normalize(record)

    assert normalized.timestamp == BASE_TIME
    assert normalized.message == "minimal record"
    assert normalized.normalization_warnings == [
        "missing @timestamp; used source record timestamp"
    ]


def _request(start: str, end: str):
    from backend.ingestion import IngestionFetchRequest

    return IngestionFetchRequest(
        start_time=datetime.fromisoformat(start),
        end_time=datetime.fromisoformat(end),
        limit=10,
    )
