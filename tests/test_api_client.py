"""Purpose: Verify api_client/ resource functions against the seeded demo dataset.

Exercises the typed client functions with an injected httpx.Client (built on
ASGITransport against the real FastAPI app) to confirm they return correctly
typed Pydantic models matching known seeded values, and that API errors
propagate as ApiClientError rather than being swallowed.
"""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy.orm import Session

from api.schemas.alert import AlertEventsRead, AlertRead, PaginatedAlerts
from api.schemas.case import CaseDetail
from api.schemas.case_activity import CaseActivityRead, PaginatedCaseActivities
from api.schemas.dashboard import DashboardSummary
from api.schemas.detection_rule import DetectionRuleRead, PaginatedDetectionRules
from api.schemas.event import PaginatedEvents
from api.schemas.ingestion import (
    IngestionConnectionTestResponse,
    IngestionRunHistory,
    IngestionStatusResponse,
    IngestionSyncResponse,
)
from api_client.alerts import get_alert, get_alert_events, list_alerts, update_alert
from api_client.cases import (
    add_case_alerts,
    create_case,
    create_case_activity,
    get_case,
    list_case_activities,
    remove_case_alert,
    update_case,
)
from api_client.dashboard import get_dashboard_summary
from api_client.events import list_events
from api_client.http import ApiClientError
from api_client.ingestion import (
    get_status as get_ingestion_status,
    list_runs as list_ingestion_runs,
    sync_provider,
    test_connection as check_ingestion_connection,
)
from api_client.rules import create_rule, list_rules, update_rule
from db.models.alert import Alert
from db.models.case import Case
from db.models.enums import AlertStatusEnum, CasePriorityEnum, CaseStatusEnum, SeverityEnum
from db.seed import BASE_TIME, TARGET_HOST, TARGET_USER

NONEXISTENT_ID = 99999

# BASE_TIME is the moment the earliest seeded alert's created_at is measured from,
# matching the known-totals convention used in tests/test_dashboard_api.py.
NULL_GUARD_AS_OF = BASE_TIME


def _alert_id(db_session: Session, external_id: str) -> int:
    return db_session.query(Alert).filter_by(external_id=external_id).one().id


def _case_id(db_session: Session, case_number: str) -> int:
    return db_session.query(Case).filter_by(case_number=case_number).one().id


def test_list_alerts_returns_paginated_alerts(
    api_client_transport: httpx.Client, db_session: Session
) -> None:
    """list_alerts() returns a PaginatedAlerts with every seeded alert on one page."""
    result = list_alerts(page_size=20, client=api_client_transport)

    assert isinstance(result, PaginatedAlerts)
    assert result.total == 13
    assert result.page == 1
    assert len(result.items) == 13
    assert all(isinstance(item, AlertRead) for item in result.items)


def test_get_alert_returns_brute_force_chain_alert(
    api_client_transport: httpx.Client, db_session: Session
) -> None:
    """get_alert() returns the seeded SSH brute-force alert with its known fields."""
    alert_id = _alert_id(db_session, "ALERT-0001")

    result = get_alert(alert_id, client=api_client_transport)

    assert isinstance(result, AlertRead)
    assert result.external_id == "ALERT-0001"
    assert result.title == "Multiple Failed SSH Authentication Attempts"
    assert result.severity == SeverityEnum.MEDIUM
    assert result.status == AlertStatusEnum.CLOSED
    assert result.hostname == TARGET_HOST
    assert result.username == TARGET_USER


def test_get_alert_nonexistent_id_raises_api_client_error(
    api_client_transport: httpx.Client,
) -> None:
    """get_alert() with a nonexistent id raises ApiClientError with status_code 404.

    Proves API errors surface to the caller rather than being silently
    swallowed into mock data.
    """
    with pytest.raises(ApiClientError) as exc_info:
        get_alert(NONEXISTENT_ID, client=api_client_transport)

    assert exc_info.value.status_code == 404


def test_create_and_get_case_round_trip(api_client_transport: httpx.Client) -> None:
    """create_case() followed by get_case() returns a matching CaseDetail."""
    created = create_case(
        title="Investigate suspicious SSH activity",
        description="Follow up on repeated failed login attempts.",
        priority=CasePriorityEnum.HIGH,
        status=CaseStatusEnum.OPEN,
        assignee="analyst1",
        client=api_client_transport,
    )

    assert isinstance(created, CaseDetail)
    assert created.title == "Investigate suspicious SSH activity"
    assert created.priority == CasePriorityEnum.HIGH
    assert created.status == CaseStatusEnum.OPEN
    assert created.assignee == "analyst1"

    fetched = get_case(created.id, client=api_client_transport)

    assert isinstance(fetched, CaseDetail)
    assert fetched.id == created.id
    assert fetched.title == created.title
    assert fetched.description == created.description
    assert fetched.priority == created.priority
    assert fetched.status == created.status
    assert fetched.assignee == created.assignee


def test_get_dashboard_summary_matches_seeded_totals(
    api_client_transport: httpx.Client,
) -> None:
    """get_dashboard_summary() returns the known seeded counts."""
    result = get_dashboard_summary(
        as_of=NULL_GUARD_AS_OF, period_days=1, client=api_client_transport
    )

    assert isinstance(result, DashboardSummary)
    assert result.total_alerts == 13
    assert result.new_alerts == 4
    assert result.critical_alerts == 2
    assert result.in_progress_alerts == 4
    assert result.open_cases == 2


def test_list_rules_returns_paginated_detection_rules(
    api_client_transport: httpx.Client,
) -> None:
    """list_rules() returns a PaginatedDetectionRules covering the seeded rules."""
    result = list_rules(client=api_client_transport)

    assert isinstance(result, PaginatedDetectionRules)
    assert result.total == 5
    assert len(result.items) == 5


def test_list_events_returns_paginated_events(api_client_transport: httpx.Client) -> None:
    """list_events() returns a PaginatedEvents object with the expected page shape."""
    result = list_events(client=api_client_transport)

    assert isinstance(result, PaginatedEvents)
    assert result.page == 1
    assert result.page_size == 20
    assert 50 <= result.total <= 100
    assert len(result.items) == 20


def test_update_alert_persists_status(
    api_client_transport: httpx.Client, db_session: Session
) -> None:
    """update_alert() PATCHes the alert and returns the updated AlertRead."""
    alert_id = _alert_id(db_session, "ALERT-1003")

    result = update_alert(alert_id, status=AlertStatusEnum.CLOSED, client=api_client_transport)

    assert isinstance(result, AlertRead)
    assert result.status == AlertStatusEnum.CLOSED


def test_get_alert_events_returns_linked_events(
    api_client_transport: httpx.Client, db_session: Session
) -> None:
    """get_alert_events() returns the brute-force alert's seven linked events."""
    alert_id = _alert_id(db_session, "ALERT-0001")

    result = get_alert_events(alert_id, client=api_client_transport)

    assert isinstance(result, AlertEventsRead)
    assert result.total == 7
    assert len(result.items) == 7


def test_update_case_persists_fields(
    api_client_transport: httpx.Client, db_session: Session
) -> None:
    """update_case() PATCHes the case and returns the updated CaseDetail."""
    case_id = _case_id(db_session, "CASE-2026-0003")

    result = update_case(case_id, priority=CasePriorityEnum.HIGH, client=api_client_transport)

    assert isinstance(result, CaseDetail)
    assert result.priority == CasePriorityEnum.HIGH


def test_add_case_alerts_links_alert(
    api_client_transport: httpx.Client, db_session: Session
) -> None:
    """add_case_alerts() links the given alert ids to the case."""
    case_id = _case_id(db_session, "CASE-2026-0003")
    alert_id = _alert_id(db_session, "ALERT-1006")

    result = add_case_alerts(case_id, [alert_id], client=api_client_transport)

    assert isinstance(result, CaseDetail)
    assert alert_id in {alert.id for alert in result.alerts}


def test_remove_case_alert_unlinks_alert(
    api_client_transport: httpx.Client, db_session: Session
) -> None:
    """remove_case_alert() unlinks the given alert from the case."""
    case_id = _case_id(db_session, "CASE-2026-0001")
    alert_id = _alert_id(db_session, "ALERT-0001")

    result = remove_case_alert(case_id, alert_id, client=api_client_transport)

    assert isinstance(result, CaseDetail)
    assert alert_id not in {alert.id for alert in result.alerts}


def test_create_case_activity_returns_typed_entry(
    api_client_transport: httpx.Client, db_session: Session
) -> None:
    """create_case_activity() posts a new activity and returns it typed."""
    case_id = _case_id(db_session, "CASE-2026-0003")

    result = create_case_activity(
        case_id,
        message="Confirmed benign.",
        activity_type="note",
        author="analyst.lee",
        client=api_client_transport,
    )

    assert isinstance(result, CaseActivityRead)
    assert result.message == "Confirmed benign."
    assert result.author == "analyst.lee"


def test_list_case_activities_returns_chronological_timeline(
    api_client_transport: httpx.Client, db_session: Session
) -> None:
    """list_case_activities() returns the chain case's 5-entry activity timeline."""
    case_id = _case_id(db_session, "CASE-2026-0001")

    result = list_case_activities(case_id, client=api_client_transport)

    assert isinstance(result, PaginatedCaseActivities)
    assert result.total == 5
    assert len(result.items) == 5
    assert all(isinstance(item, CaseActivityRead) for item in result.items)


def test_create_rule_returns_typed_rule(api_client_transport: httpx.Client) -> None:
    """create_rule() posts a new detection rule and returns it typed."""
    result = create_rule(
        name="API client created rule",
        query="event_category:test",
        severity=SeverityEnum.MEDIUM,
        language="sigma",
        client=api_client_transport,
    )

    assert isinstance(result, DetectionRuleRead)
    assert result.name == "API client created rule"
    assert result.severity == SeverityEnum.MEDIUM
    assert result.enabled is True


def test_update_rule_persists_fields(api_client_transport: httpx.Client) -> None:
    """update_rule() PATCHes a detection rule and returns the updated DetectionRuleRead."""
    created = create_rule(
        name="Rule to update",
        query="event_category:test",
        severity=SeverityEnum.LOW,
        language="sigma",
        client=api_client_transport,
    )

    result = update_rule(created.id, enabled=False, client=api_client_transport)

    assert isinstance(result, DetectionRuleRead)
    assert result.enabled is False
    assert result.name == "Rule to update"


def test_ingestion_connection_client_returns_typed_response(
    api_client_transport: httpx.Client,
) -> None:
    """test_connection() returns a typed ingestion connection result."""
    result = check_ingestion_connection(
        "fixture",
        source_name="fixture-client",
        client=api_client_transport,
    )

    assert isinstance(result, IngestionConnectionTestResponse)
    assert result.provider == "fixture"
    assert result.source_name == "fixture-client"
    assert result.ok is True


def test_sync_provider_client_returns_typed_response(
    api_client_transport: httpx.Client,
) -> None:
    """sync_provider() returns a typed ingestion sync result."""
    result = sync_provider(
        "fixture",
        source_name="fixture-client",
        start_time=BASE_TIME,
        end_time=BASE_TIME.replace(hour=4),
        limit=3,
        client=api_client_transport,
    )

    assert isinstance(result, IngestionSyncResponse)
    assert result.provider == "fixture"
    assert result.status == "succeeded"
    assert result.persisted_count == 3


def test_get_ingestion_status_client_returns_typed_response(
    api_client_transport: httpx.Client,
) -> None:
    """get_status() returns typed ingestion status."""
    sync_provider(
        "fixture",
        source_name="fixture-status-client",
        start_time=BASE_TIME,
        end_time=BASE_TIME.replace(hour=4),
        limit=3,
        client=api_client_transport,
    )

    result = get_ingestion_status(client=api_client_transport)

    assert isinstance(result, IngestionStatusResponse)
    assert result.latest_run is not None
    assert result.latest_run.provider == "fixture"
    assert result.checkpoints


def test_list_ingestion_runs_client_returns_typed_response(
    api_client_transport: httpx.Client,
) -> None:
    """list_runs() returns typed ingestion run history."""
    sync_provider(
        "fixture",
        source_name="fixture-runs-client",
        start_time=BASE_TIME,
        end_time=BASE_TIME.replace(hour=4),
        limit=3,
        client=api_client_transport,
    )

    result = list_ingestion_runs(page_size=5, client=api_client_transport)

    assert isinstance(result, IngestionRunHistory)
    assert result.total >= 1
    assert all(item.provider for item in result.items)


def test_ingestion_client_errors_surface_api_client_error(
    api_client_transport: httpx.Client,
) -> None:
    """Ingestion endpoint errors propagate through ApiClientError."""
    with pytest.raises(ApiClientError) as exc_info:
        check_ingestion_connection("unknown", client=api_client_transport)

    assert exc_info.value.status_code == 404
