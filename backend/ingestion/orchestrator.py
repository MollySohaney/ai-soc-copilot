"""Purpose: Coordinate checkpointed telemetry ingestion into the database."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.ingestion.adapters import IngestionAdapter
from backend.ingestion.dto import (
    IngestionCheckpointState,
    IngestionFetchRequest,
    IngestionRunResult,
)
from backend.ingestion.normalizers import EcsEventNormalizer, NormalizedEvent
from db.models import Event, IngestionCheckpoint, IngestionRun


class EventNormalizer(Protocol):
    """Represent a source-record normalizer."""

    def normalize(self, record):  # noqa: ANN001, ANN201
        """Normalize one source record."""


class IngestionOrchestrator:
    """Fetch, normalize, deduplicate, persist, and checkpoint telemetry events."""

    def __init__(
        self,
        session: Session,
        adapter: IngestionAdapter,
        normalizer: EventNormalizer | None = None,
    ) -> None:
        """Initialize the orchestrator with explicit dependencies."""
        self._session = session
        self._adapter = adapter
        self._normalizer = normalizer or EcsEventNormalizer()

    def run(self, request: IngestionFetchRequest, *, dry_run: bool = False) -> IngestionRunResult:
        """Run one bounded ingestion page and advance checkpoint after persistence."""
        checkpoint = request.checkpoint or self._load_checkpoint()
        effective_request = request.model_copy(update={"checkpoint": checkpoint})
        run = IngestionRun(
            provider=self._adapter.provider,
            source_name=self._adapter.source_name,
            status="running",
            requested_start=request.start_time,
            requested_end=request.end_time,
            checkpoint_before=checkpoint.values if checkpoint else None,
        )
        self._session.add(run)
        self._session.flush()

        errors: list[str] = []
        checkpoint_advanced = False
        try:
            page = self._adapter.fetch_records(effective_request)
            run.fetched_count = len(page.records)
            normalized_events = self._normalize_records(page.records, run, errors)
            duplicate_keys = self._existing_dedup_keys(normalized_events)

            if dry_run:
                seen_keys = set(duplicate_keys)
                for normalized_event in normalized_events:
                    if normalized_event.dedup_key in seen_keys:
                        run.duplicate_count += 1
                    seen_keys.add(normalized_event.dedup_key)
                run.status = "dry_run"
            else:
                for normalized_event in normalized_events:
                    if normalized_event.dedup_key in duplicate_keys:
                        run.duplicate_count += 1
                        continue
                    self._session.add(
                        Event(
                            **normalized_event.to_event_kwargs(),
                            ingestion_run=run,
                        )
                    )
                    duplicate_keys.add(normalized_event.dedup_key)
                    run.persisted_count += 1

                if page.next_checkpoint is not None:
                    self._save_checkpoint(page.next_checkpoint, run)
                    checkpoint_advanced = True
                run.status = "partial" if run.failed_count else "succeeded"

            run.checkpoint_after = (
                page.next_checkpoint.values if page.next_checkpoint is not None else None
            )
            run.completed_at = datetime.now(timezone.utc)
            self._session.commit()
        except Exception as error:  # noqa: BLE001
            self._session.rollback()
            self._record_failed_run(run, request, checkpoint, error)
            raise

        return IngestionRunResult(
            run_id=run.id,
            provider=run.provider,
            source_name=run.source_name,
            status=run.status,
            dry_run=dry_run,
            fetched_count=run.fetched_count,
            normalized_count=run.normalized_count,
            persisted_count=run.persisted_count,
            duplicate_count=run.duplicate_count,
            failed_count=run.failed_count,
            warning_count=run.warning_count,
            checkpoint_advanced=checkpoint_advanced,
            errors=errors,
        )

    def _load_checkpoint(self) -> IngestionCheckpointState | None:
        checkpoint = self._session.scalar(
            select(IngestionCheckpoint).where(
                IngestionCheckpoint.provider == self._adapter.provider,
                IngestionCheckpoint.source_name == self._adapter.source_name,
            )
        )
        if checkpoint is None:
            return None
        return IngestionCheckpointState(
            provider=checkpoint.provider,
            source_name=checkpoint.source_name,
            values=checkpoint.checkpoint or {},
        )

    def _normalize_records(
        self, records: list, run: IngestionRun, errors: list[str]  # noqa: ANN001
    ) -> list[NormalizedEvent]:
        normalized_events: list[NormalizedEvent] = []
        for record in records:
            try:
                normalized_event = self._normalizer.normalize(record)
            except Exception as error:  # noqa: BLE001
                run.failed_count += 1
                errors.append(f"{record.record_id}: {error}")
                continue

            run.normalized_count += 1
            run.warning_count += len(normalized_event.normalization_warnings)
            normalized_events.append(normalized_event)
        return normalized_events

    def _existing_dedup_keys(self, normalized_events: list[NormalizedEvent]) -> set[str]:
        dedup_keys = [event.dedup_key for event in normalized_events]
        if not dedup_keys:
            return set()
        return set(
            self._session.scalars(
                select(Event.dedup_key).where(Event.dedup_key.in_(dedup_keys))
            ).all()
        )

    def _save_checkpoint(self, checkpoint: IngestionCheckpointState, run: IngestionRun) -> None:
        stored_checkpoint = self._session.scalar(
            select(IngestionCheckpoint).where(
                IngestionCheckpoint.provider == self._adapter.provider,
                IngestionCheckpoint.source_name == self._adapter.source_name,
            )
        )
        if stored_checkpoint is None:
            stored_checkpoint = IngestionCheckpoint(
                provider=self._adapter.provider,
                source_name=self._adapter.source_name,
            )
            self._session.add(stored_checkpoint)

        stored_checkpoint.checkpoint = checkpoint.values
        stored_checkpoint.updated_at = datetime.now(timezone.utc)
        stored_checkpoint.last_run = run

    def _record_failed_run(
        self,
        run: IngestionRun,
        request: IngestionFetchRequest,
        checkpoint: IngestionCheckpointState | None,
        error: Exception,
    ) -> None:
        failed_run = IngestionRun(
            provider=self._adapter.provider,
            source_name=self._adapter.source_name,
            status="failed",
            requested_start=request.start_time,
            requested_end=request.end_time,
            checkpoint_before=checkpoint.values if checkpoint else None,
            completed_at=datetime.now(timezone.utc),
            error_message=str(error),
        )
        self._session.add(failed_run)
        try:
            self._session.commit()
        except SQLAlchemyError:
            self._session.rollback()
