"""Purpose: Verify restartable ingestion orchestration and checkpoint safety."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.ingestion import (
    FixtureIngestionAdapter,
    IngestionCheckpointState,
    IngestionFetchRequest,
    IngestionOrchestrator,
)
from backend.ingestion.dto import SourceRecord
from backend.ingestion.normalizers import EcsEventNormalizer
from db.base import Base
from db.models import Event, IngestionCheckpoint, IngestionRun


BASE_TIME = datetime(2026, 8, 15, 2, 0, tzinfo=timezone.utc)


@pytest.fixture()
def session() -> Iterator[Session]:
    """Provide a Session backed by a fresh in-memory SQLite database."""
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, connection_record) -> None:  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    with Session(engine) as db_session:
        yield db_session
    engine.dispose()


class FailingNormalizer(EcsEventNormalizer):
    """Fail normalization for selected record IDs."""

    def __init__(self, failing_record_ids: set[str]) -> None:
        self._failing_record_ids = failing_record_ids

    def normalize(self, record: SourceRecord):
        if record.record_id in self._failing_record_ids:
            raise ValueError("fixture normalization failed")
        return super().normalize(record)


def test_orchestrator_persists_events_and_advances_checkpoint(session: Session) -> None:
    """A successful run persists normalized events and records checkpoint state."""
    adapter = FixtureIngestionAdapter(source_name="fixture-test")
    result = IngestionOrchestrator(session, adapter).run(_request(limit=2))

    events = session.scalars(select(Event).order_by(Event.timestamp, Event.event_id)).all()
    checkpoint = session.scalar(select(IngestionCheckpoint))
    run = session.get(IngestionRun, result.run_id)

    assert result.status == "succeeded"
    assert result.fetched_count == 2
    assert result.normalized_count == 2
    assert result.persisted_count == 2
    assert result.checkpoint_advanced is True
    assert [event.source_provider for event in events] == ["fixture", "fixture"]
    assert checkpoint is not None
    assert checkpoint.checkpoint == {"offset": 2}
    assert checkpoint.last_run_id == result.run_id
    assert run is not None
    assert run.checkpoint_after == {"offset": 2}


def test_orchestrator_uses_checkpoint_on_retry_restart(session: Session) -> None:
    """A later run resumes from the stored checkpoint instead of refetching old records."""
    adapter = FixtureIngestionAdapter(source_name="fixture-test")
    orchestrator = IngestionOrchestrator(session, adapter)

    first = orchestrator.run(_request(limit=2))
    second = orchestrator.run(_request(limit=2))

    event_ids = session.scalars(select(Event.event_id).order_by(Event.timestamp)).all()
    checkpoint = session.scalar(select(IngestionCheckpoint))

    assert first.persisted_count == 2
    assert second.persisted_count == 1
    assert second.duplicate_count == 0
    assert len(event_ids) == 3
    assert event_ids[-1] == "fixture:fixture-test:fixture-network-1"
    assert checkpoint is not None
    assert checkpoint.checkpoint == {"offset": 3}


def test_orchestrator_deduplicates_same_batch_twice(session: Session) -> None:
    """Re-ingesting the same source records does not create duplicates."""
    adapter = FixtureIngestionAdapter(source_name="fixture-test")
    orchestrator = IngestionOrchestrator(session, adapter)
    reset_checkpoint = IngestionCheckpointState(
        provider="fixture",
        source_name="fixture-test",
        values={"offset": 0},
    )
    request = _request(limit=3, checkpoint=reset_checkpoint)

    first = orchestrator.run(request)
    second = orchestrator.run(request)

    total_events = session.scalar(select(func.count()).select_from(Event))

    assert first.persisted_count == 3
    assert second.persisted_count == 0
    assert second.duplicate_count == 3
    assert total_events == 3


def test_orchestrator_handles_partial_malformed_records(session: Session) -> None:
    """Bad records are counted as failed while valid records persist."""
    adapter = FixtureIngestionAdapter(source_name="fixture-test")
    result = IngestionOrchestrator(
        session,
        adapter,
        normalizer=FailingNormalizer({"fixture-process-1"}),
    ).run(_request(limit=3))

    total_events = session.scalar(select(func.count()).select_from(Event))
    checkpoint = session.scalar(select(IngestionCheckpoint))

    assert result.status == "partial"
    assert result.fetched_count == 3
    assert result.normalized_count == 2
    assert result.failed_count == 1
    assert result.persisted_count == 2
    assert result.errors == ["fixture-process-1: fixture normalization failed"]
    assert total_events == 2
    assert checkpoint is not None
    assert checkpoint.checkpoint == {"offset": 3}


def test_orchestrator_dry_run_writes_no_events_or_checkpoint(session: Session) -> None:
    """Dry-run reports counts without writing events or advancing checkpoints."""
    adapter = FixtureIngestionAdapter(source_name="fixture-test")
    result = IngestionOrchestrator(session, adapter).run(_request(limit=3), dry_run=True)

    total_events = session.scalar(select(func.count()).select_from(Event))
    total_checkpoints = session.scalar(select(func.count()).select_from(IngestionCheckpoint))
    total_runs = session.scalar(select(func.count()).select_from(IngestionRun))

    assert result.status == "dry_run"
    assert result.dry_run is True
    assert result.fetched_count == 3
    assert result.normalized_count == 3
    assert result.persisted_count == 0
    assert result.checkpoint_advanced is False
    assert total_events == 0
    assert total_checkpoints == 0
    assert total_runs == 1


def test_orchestrator_does_not_advance_checkpoint_on_transaction_failure(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A commit failure rolls back events and checkpoint movement."""
    adapter = FixtureIngestionAdapter(source_name="fixture-test")

    def fail_commit() -> None:
        raise SQLAlchemyError("forced commit failure")

    monkeypatch.setattr(session, "commit", fail_commit)

    with pytest.raises(SQLAlchemyError, match="forced commit failure"):
        IngestionOrchestrator(session, adapter).run(_request(limit=2))

    assert session.scalar(select(func.count()).select_from(Event)) == 0
    assert session.scalar(select(func.count()).select_from(IngestionCheckpoint)) == 0


def _request(
    *,
    limit: int,
    checkpoint: IngestionCheckpointState | None = None,
) -> IngestionFetchRequest:
    return IngestionFetchRequest(
        start_time=BASE_TIME,
        end_time=BASE_TIME + timedelta(hours=2),
        limit=limit,
        checkpoint=checkpoint,
    )
