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

from api.schemas.alert import AlertRead, PaginatedAlerts
from api.schemas.case import CaseDetail
from api.schemas.dashboard import DashboardSummary
from api.schemas.detection_rule import PaginatedDetectionRules
from api.schemas.event import PaginatedEvents
from api_client.alerts import get_alert, list_alerts
from api_client.cases import create_case, get_case
from api_client.dashboard import get_dashboard_summary
from api_client.events import list_events
from api_client.http import ApiClientError
from api_client.rules import list_rules
from db.models.alert import Alert
from db.models.enums import AlertStatusEnum, CasePriorityEnum, CaseStatusEnum, SeverityEnum
from db.seed import BASE_TIME, TARGET_HOST, TARGET_USER

NONEXISTENT_ID = 99999

# BASE_TIME is the moment the earliest seeded alert's created_at is measured from,
# matching the known-totals convention used in tests/test_dashboard_api.py.
NULL_GUARD_AS_OF = BASE_TIME


def _alert_id(db_session: Session, external_id: str) -> int:
    return db_session.query(Alert).filter_by(external_id=external_id).one().id


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
