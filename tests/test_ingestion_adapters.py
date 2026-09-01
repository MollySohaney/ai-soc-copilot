"""Purpose: Verify provider-neutral ingestion adapter DTOs and fixture behavior."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from backend.ingestion import (
    FixtureIngestionAdapter,
    IngestionAdapter,
    IngestionCheckpointState,
    IngestionFetchRequest,
    IngestionPage,
    SourceRecord,
)


BASE_TIME = datetime(2026, 8, 15, 2, 0, tzinfo=timezone.utc)


def _record(record_id: str, offset_minutes: int) -> SourceRecord:
    timestamp = BASE_TIME + timedelta(minutes=offset_minutes)
    return SourceRecord(
        provider="fixture",
        source_name="fixture-test",
        record_id=record_id,
        timestamp=timestamp,
        source_index="fixture-index",
        cursor=[timestamp.isoformat(), record_id],
        payload={"@timestamp": timestamp.isoformat(), "message": record_id},
    )


def test_fixture_adapter_satisfies_protocol() -> None:
    """FixtureIngestionAdapter exposes the provider-neutral adapter contract."""
    adapter: IngestionAdapter = FixtureIngestionAdapter(records=[])

    assert adapter.provider == "fixture"
    assert adapter.source_name == "fixture-default"


def test_source_record_dedup_key_is_stable() -> None:
    """SourceRecord derives deduplication from provider/source/index/record identity."""
    record = _record("rec-1", 0)

    assert record.dedup_key == "fixture:fixture-test:fixture-index:rec-1"


def test_fetch_request_requires_forward_time_window() -> None:
    """Fetch requests reject empty or backward time ranges."""
    with pytest.raises(ValidationError, match="end_time must be after start_time"):
        IngestionFetchRequest(start_time=BASE_TIME, end_time=BASE_TIME)


def test_ingestion_page_requires_deterministic_record_order() -> None:
    """Adapter pages must be ordered by timestamp and record id."""
    with pytest.raises(ValidationError, match="records must be sorted"):
        IngestionPage(records=[_record("rec-2", 2), _record("rec-1", 1)])


def test_fixture_connection_test_is_sanitized_success() -> None:
    """Fixture adapter reports a successful connection without secret-bearing details."""
    health = FixtureIngestionAdapter(records=[]).test_connection()

    assert health.ok is True
    assert health.provider == "fixture"
    assert health.source_name == "fixture-default"
    assert health.details == {}


def test_fixture_adapter_filters_by_time_window() -> None:
    """Fixture fetches only records inside the requested bounded time window."""
    adapter = FixtureIngestionAdapter(
        records=[_record("before", -1), _record("inside", 1), _record("after", 3)],
        source_name="fixture-test",
    )
    page = adapter.fetch_records(
        IngestionFetchRequest(
            start_time=BASE_TIME,
            end_time=BASE_TIME + timedelta(minutes=2),
            limit=10,
        )
    )

    assert [record.record_id for record in page.records] == ["inside"]
    assert page.has_more is False
    assert page.next_checkpoint is not None
    assert page.next_checkpoint.values == {"offset": 1}


def test_fixture_adapter_paginates_with_checkpoint() -> None:
    """Fixture checkpoints advance pages deterministically with offset state."""
    adapter = FixtureIngestionAdapter(
        records=[_record("rec-1", 1), _record("rec-2", 2), _record("rec-3", 3)],
        source_name="fixture-test",
    )
    request = IngestionFetchRequest(
        start_time=BASE_TIME,
        end_time=BASE_TIME + timedelta(minutes=5),
        limit=2,
    )

    first_page = adapter.fetch_records(request)
    second_page = adapter.fetch_records(request.model_copy(update={"checkpoint": first_page.next_checkpoint}))

    assert [record.record_id for record in first_page.records] == ["rec-1", "rec-2"]
    assert first_page.has_more is True
    assert first_page.next_checkpoint is not None
    assert first_page.next_checkpoint.values == {"offset": 2}
    assert [record.record_id for record in second_page.records] == ["rec-3"]
    assert second_page.has_more is False
    assert second_page.next_checkpoint is not None
    assert second_page.next_checkpoint.values == {"offset": 3}


def test_fixture_adapter_ignores_invalid_checkpoint_offset() -> None:
    """Invalid fixture checkpoint offsets restart at the beginning."""
    adapter = FixtureIngestionAdapter(records=[_record("rec-1", 1)], source_name="fixture-test")
    page = adapter.fetch_records(
        IngestionFetchRequest(
            start_time=BASE_TIME,
            end_time=BASE_TIME + timedelta(minutes=2),
            limit=10,
            checkpoint=IngestionCheckpointState(
                provider="fixture",
                source_name="fixture-test",
                values={"offset": -1},
            ),
        )
    )

    assert [record.record_id for record in page.records] == ["rec-1"]
