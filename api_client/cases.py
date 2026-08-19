"""Purpose: Provide typed client functions for case management endpoints."""

from __future__ import annotations

import httpx

from api.schemas.case import CaseDetail, PaginatedCases
from api.schemas.case_activity import CaseActivityRead, PaginatedCaseActivities
from api_client.http import _request, clean_params, get_default_client
from db.models.enums import CasePriorityEnum, CaseStatusEnum


def list_cases(
    *,
    status: CaseStatusEnum | None = None,
    priority: CasePriorityEnum | None = None,
    assignee: str | None = None,
    page: int = 1,
    page_size: int = 20,
    client: httpx.Client | None = None,
) -> PaginatedCases:
    """List investigation cases, filtered and paginated, sorted by most recently created first.

    Args:
        status: Filter cases by exact workflow status.
        priority: Filter cases by exact priority.
        assignee: Filter cases by exact assignee, case-insensitive.
        page: The 1-indexed page number to return.
        page_size: The number of cases per page.
        client: The httpx client to issue the request with; defaults to the
            shared client built from application settings.

    Returns:
        A page of investigation cases along with pagination metadata.
    """
    params = clean_params(
        status=status.value if status is not None else None,
        priority=priority.value if priority is not None else None,
        assignee=assignee,
        page=page,
        page_size=page_size,
    )
    response = _request(client or get_default_client(), "GET", "/cases", params=params)
    return PaginatedCases.model_validate(response.json())


def create_case(
    *,
    title: str,
    description: str | None = None,
    priority: CasePriorityEnum = CasePriorityEnum.MEDIUM,
    status: CaseStatusEnum = CaseStatusEnum.OPEN,
    assignee: str | None = None,
    alert_ids: list[int] | None = None,
    client: httpx.Client | None = None,
) -> CaseDetail:
    """Create an investigation case, optionally linking it to existing alerts.

    Args:
        title: The case title.
        description: A human-readable description of the case.
        priority: The case priority.
        status: The initial workflow status.
        assignee: The case assignee, if already known.
        alert_ids: The ids of existing alerts to link to the new case.
        client: The httpx client to issue the request with; defaults to the
            shared client built from application settings.

    Returns:
        The newly created case, with its linked alerts and activity timeline.
    """
    payload = {
        "title": title,
        "description": description,
        "priority": priority.value,
        "status": status.value,
        "assignee": assignee,
        "alert_ids": alert_ids or [],
    }
    response = _request(client or get_default_client(), "POST", "/cases", json=payload)
    return CaseDetail.model_validate(response.json())


def get_case(case_id: int, *, client: httpx.Client | None = None) -> CaseDetail:
    """Retrieve a single investigation case by its primary key.

    Args:
        case_id: The integer primary key of the case.
        client: The httpx client to issue the request with; defaults to the
            shared client built from application settings.

    Returns:
        The matching case, with its linked alerts and activity timeline.
    """
    response = _request(client or get_default_client(), "GET", f"/cases/{case_id}")
    return CaseDetail.model_validate(response.json())


def update_case(
    case_id: int,
    *,
    title: str | None = None,
    description: str | None = None,
    status: CaseStatusEnum | None = None,
    priority: CasePriorityEnum | None = None,
    assignee: str | None = None,
    client: httpx.Client | None = None,
) -> CaseDetail:
    """Apply a partial update to an investigation case.

    Args:
        case_id: The integer primary key of the case.
        title: The new title, if changing it.
        description: The new description, if changing it.
        status: The new workflow status, if changing it.
        priority: The new priority, if changing it.
        assignee: The new assignee, if changing it.
        client: The httpx client to issue the request with; defaults to the
            shared client built from application settings.

    Returns:
        The updated case, with its linked alerts and activity timeline.
    """
    payload = clean_params(
        title=title,
        description=description,
        status=status.value if status is not None else None,
        priority=priority.value if priority is not None else None,
        assignee=assignee,
    )
    response = _request(
        client or get_default_client(), "PATCH", f"/cases/{case_id}", json=payload
    )
    return CaseDetail.model_validate(response.json())


def add_case_alerts(
    case_id: int, alert_ids: list[int], *, client: httpx.Client | None = None
) -> CaseDetail:
    """Link one or more alerts to an investigation case, skipping already-linked alerts.

    Args:
        case_id: The integer primary key of the case.
        alert_ids: The ids of the alerts to link to the case.
        client: The httpx client to issue the request with; defaults to the
            shared client built from application settings.

    Returns:
        The updated case, with its linked alerts and activity timeline.
    """
    response = _request(
        client or get_default_client(),
        "POST",
        f"/cases/{case_id}/alerts",
        json={"alert_ids": alert_ids},
    )
    return CaseDetail.model_validate(response.json())


def remove_case_alert(
    case_id: int, alert_id: int, *, client: httpx.Client | None = None
) -> CaseDetail:
    """Unlink an alert from an investigation case.

    Args:
        case_id: The integer primary key of the case.
        alert_id: The integer primary key of the alert to unlink.
        client: The httpx client to issue the request with; defaults to the
            shared client built from application settings.

    Returns:
        The updated case, with its linked alerts and activity timeline.
    """
    response = _request(
        client or get_default_client(), "DELETE", f"/cases/{case_id}/alerts/{alert_id}"
    )
    return CaseDetail.model_validate(response.json())


def list_case_activities(
    case_id: int, *, client: httpx.Client | None = None
) -> PaginatedCaseActivities:
    """List the activity timeline entries for a case, oldest first.

    Args:
        case_id: The integer primary key of the case.
        client: The httpx client to issue the request with; defaults to the
            shared client built from application settings.

    Returns:
        The activity entries for the case, chronologically ascending.
    """
    response = _request(client or get_default_client(), "GET", f"/cases/{case_id}/activities")
    return PaginatedCaseActivities.model_validate(response.json())


def create_case_activity(
    case_id: int,
    *,
    message: str,
    activity_type: str = "note",
    author: str | None = None,
    client: httpx.Client | None = None,
) -> CaseActivityRead:
    """Append a new activity timeline entry to a case.

    Args:
        case_id: The integer primary key of the case.
        message: The activity message text.
        activity_type: The category of activity being recorded.
        author: The name of the person recording the activity, if known.
        client: The httpx client to issue the request with; defaults to the
            shared client built from application settings.

    Returns:
        The newly created activity entry.
    """
    payload = {"activity_type": activity_type, "message": message, "author": author}
    response = _request(
        client or get_default_client(), "POST", f"/cases/{case_id}/activities", json=payload
    )
    return CaseActivityRead.model_validate(response.json())
