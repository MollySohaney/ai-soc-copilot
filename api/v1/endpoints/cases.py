"""Purpose: Expose CRUD and workflow endpoints for investigation cases."""

from __future__ import annotations

import math
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.schemas.alert import AlertRead
from api.schemas.case import (
    CaseAlertsAddRequest,
    CaseCreateRequest,
    CaseDetail,
    CaseRead,
    CaseUpdate,
    PaginatedCases,
)
from api.schemas.case_activity import (
    CaseActivityCreateRequest,
    CaseActivityRead,
    PaginatedCaseActivities,
)
from db.models.alert import Alert
from db.models.case import Case
from db.models.case_activity import CaseActivity
from db.models.case_alert import CaseAlert
from db.models.enums import CasePriorityEnum, CaseStatusEnum
from db.session import get_db

router = APIRouter(prefix="/cases", tags=["cases"])


def _to_case_detail(case: Case) -> CaseDetail:
    """Build a CaseDetail response from a Case with its relationships loaded.

    Args:
        case: The case ORM instance, with case_alerts and activities loaded.

    Returns:
        A CaseDetail schema populated from the case and its related records.
    """
    return CaseDetail(
        **CaseRead.model_validate(case).model_dump(),
        alerts=[AlertRead.model_validate(link.alert) for link in case.case_alerts],
        activities=[CaseActivityRead.model_validate(activity) for activity in case.activities],
    )


def _generate_case_number(db: Session) -> str:
    """Generate the next sequential case number for the current UTC year.

    Args:
        db: The database session dependency.

    Returns:
        A case number of the form CASE-{year}-{seq:04d}.
    """
    year = datetime.now(timezone.utc).year
    prefix = f"CASE-{year}-"
    stmt = (
        select(Case.case_number)
        .where(Case.case_number.like(f"{prefix}%"))
        .order_by(Case.case_number.desc())
        .limit(1)
    )
    last_number = db.scalar(stmt)
    next_seq = 1
    if last_number is not None:
        suffix = last_number[len(prefix) :]
        if suffix.isdigit():
            next_seq = int(suffix) + 1
    return f"{prefix}{next_seq:04d}"


@router.get("", response_model=PaginatedCases)
def list_cases(
    status: CaseStatusEnum | None = None,
    priority: CasePriorityEnum | None = None,
    assignee: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PaginatedCases:
    """List investigation cases, filtered and paginated, sorted by most recently created first.

    Args:
        status: Filter cases by exact workflow status.
        priority: Filter cases by exact priority.
        assignee: Filter cases by exact assignee, case-insensitive.
        page: The 1-indexed page number to return.
        page_size: The number of cases per page.
        db: The database session dependency.

    Returns:
        A page of investigation cases along with pagination metadata.
    """
    filters = []
    if status is not None:
        filters.append(Case.status == status)
    if priority is not None:
        filters.append(Case.priority == priority)
    if assignee is not None:
        filters.append(func.lower(Case.assignee) == assignee.lower())

    count_stmt = select(func.count()).select_from(Case).where(*filters)
    total = db.scalar(count_stmt) or 0

    stmt = (
        select(Case)
        .where(*filters)
        .order_by(Case.created_at.desc(), Case.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = db.scalars(stmt).all()

    total_pages = math.ceil(total / page_size) if total else 0

    return PaginatedCases(
        items=[CaseRead.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post("", response_model=CaseDetail, status_code=201)
def create_case(payload: CaseCreateRequest, db: Session = Depends(get_db)) -> CaseDetail:
    """Create an investigation case, optionally linking it to existing alerts.

    Args:
        payload: The fields for the new case, including alert ids to link.
        db: The database session dependency.

    Returns:
        The newly created case, with its linked alerts and activity timeline.

    Raises:
        HTTPException: If any of the given alert ids do not exist.
    """
    alert_ids = list(dict.fromkeys(payload.alert_ids))
    if alert_ids:
        found_ids = set(db.scalars(select(Alert.id).where(Alert.id.in_(alert_ids))).all())
        missing_ids = [alert_id for alert_id in alert_ids if alert_id not in found_ids]
        if missing_ids:
            raise HTTPException(status_code=404, detail=f"Alerts not found: {missing_ids}")

    case = Case(
        case_number=_generate_case_number(db),
        title=payload.title,
        description=payload.description,
        priority=payload.priority,
        status=payload.status,
        assignee=payload.assignee,
    )
    db.add(case)
    db.flush()

    for alert_id in alert_ids:
        db.add(CaseAlert(case_id=case.id, alert_id=alert_id))

    db.add(
        CaseActivity(
            case_id=case.id,
            activity_type="case_created",
            message=f"Case {case.case_number} created",
            author=None,
        )
    )

    db.commit()
    db.refresh(case)
    return _to_case_detail(case)


@router.get("/{case_id}", response_model=CaseDetail)
def get_case(case_id: int, db: Session = Depends(get_db)) -> CaseDetail:
    """Retrieve a single investigation case by its primary key.

    Args:
        case_id: The integer primary key of the case.
        db: The database session dependency.

    Returns:
        The matching case, with its linked alerts and activity timeline.

    Raises:
        HTTPException: If no case with the given id exists.
    """
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return _to_case_detail(case)


@router.patch("/{case_id}", response_model=CaseDetail)
def update_case(case_id: int, payload: CaseUpdate, db: Session = Depends(get_db)) -> CaseDetail:
    """Apply a partial update to an investigation case.

    Args:
        case_id: The integer primary key of the case.
        payload: The fields to update; unset fields are left unchanged.
        db: The database session dependency.

    Returns:
        The updated case, with its linked alerts and activity timeline.

    Raises:
        HTTPException: If no case with the given id exists.
    """
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")

    updates = payload.model_dump(exclude_unset=True)

    if "status" in updates and updates["status"] != case.status:
        old_status, new_status = case.status, updates["status"]
        if new_status == CaseStatusEnum.CLOSED:
            case.closed_at = datetime.now(timezone.utc)
        elif old_status == CaseStatusEnum.CLOSED:
            case.closed_at = None
        db.add(
            CaseActivity(
                case_id=case.id,
                activity_type="status_change",
                message=f"Status changed from {old_status.value} to {new_status.value}",
                author=None,
            )
        )

    if "priority" in updates and updates["priority"] != case.priority:
        old_priority, new_priority = case.priority, updates["priority"]
        db.add(
            CaseActivity(
                case_id=case.id,
                activity_type="priority_change",
                message=f"Priority changed from {old_priority.value} to {new_priority.value}",
                author=None,
            )
        )

    for field, value in updates.items():
        setattr(case, field, value)
    if updates:
        case.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(case)
    return _to_case_detail(case)


@router.post("/{case_id}/alerts", response_model=CaseDetail)
def add_case_alerts(
    case_id: int, payload: CaseAlertsAddRequest, db: Session = Depends(get_db)
) -> CaseDetail:
    """Link one or more alerts to an investigation case, skipping already-linked alerts.

    Args:
        case_id: The integer primary key of the case.
        payload: The alert ids to link to the case.
        db: The database session dependency.

    Returns:
        The updated case, with its linked alerts and activity timeline.

    Raises:
        HTTPException: If the case does not exist, or any given alert id does not exist.
    """
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")

    alert_ids = list(dict.fromkeys(payload.alert_ids))
    found_ids = set(db.scalars(select(Alert.id).where(Alert.id.in_(alert_ids))).all())
    missing_ids = [alert_id for alert_id in alert_ids if alert_id not in found_ids]
    if missing_ids:
        raise HTTPException(status_code=404, detail=f"Alerts not found: {missing_ids}")

    existing_ids = set(
        db.scalars(
            select(CaseAlert.alert_id).where(
                CaseAlert.case_id == case_id, CaseAlert.alert_id.in_(alert_ids)
            )
        ).all()
    )
    new_ids = [alert_id for alert_id in alert_ids if alert_id not in existing_ids]

    for alert_id in new_ids:
        db.add(CaseAlert(case_id=case_id, alert_id=alert_id))

    if new_ids:
        db.add(
            CaseActivity(
                case_id=case_id,
                activity_type="alerts_added",
                message=f"Linked alerts: {new_ids}",
                author=None,
            )
        )

    db.commit()
    db.refresh(case)
    return _to_case_detail(case)


@router.delete("/{case_id}/alerts/{alert_id}", response_model=CaseDetail)
def remove_case_alert(case_id: int, alert_id: int, db: Session = Depends(get_db)) -> CaseDetail:
    """Unlink an alert from an investigation case.

    Args:
        case_id: The integer primary key of the case.
        alert_id: The integer primary key of the alert to unlink.
        db: The database session dependency.

    Returns:
        The updated case, with its linked alerts and activity timeline.

    Raises:
        HTTPException: If the case does not exist, or the alert is not linked to the case.
    """
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")

    link = db.scalar(
        select(CaseAlert).where(CaseAlert.case_id == case_id, CaseAlert.alert_id == alert_id)
    )
    if link is None:
        raise HTTPException(status_code=404, detail="Alert not linked to case")

    db.delete(link)
    db.add(
        CaseActivity(
            case_id=case_id,
            activity_type="alert_removed",
            message=f"Unlinked alert {alert_id}",
            author=None,
        )
    )

    db.commit()
    db.refresh(case)
    return _to_case_detail(case)


@router.get("/{case_id}/activities", response_model=PaginatedCaseActivities)
def list_case_activities(case_id: int, db: Session = Depends(get_db)) -> PaginatedCaseActivities:
    """List the activity timeline entries for a case, oldest first.

    Args:
        case_id: The integer primary key of the case.
        db: The database session dependency.

    Returns:
        The activity entries for the case, chronologically ascending.

    Raises:
        HTTPException: If no case with the given id exists.
    """
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")

    stmt = (
        select(CaseActivity)
        .where(CaseActivity.case_id == case_id)
        .order_by(CaseActivity.created_at.asc(), CaseActivity.id.asc())
    )
    activities = db.scalars(stmt).all()

    return PaginatedCaseActivities(
        items=[CaseActivityRead.model_validate(activity) for activity in activities],
        total=len(activities),
    )


@router.post("/{case_id}/activities", response_model=CaseActivityRead, status_code=201)
def create_case_activity(
    case_id: int, payload: CaseActivityCreateRequest, db: Session = Depends(get_db)
) -> CaseActivity:
    """Append a new activity timeline entry to a case.

    Args:
        case_id: The integer primary key of the case.
        payload: The activity fields to record.
        db: The database session dependency.

    Returns:
        The newly created activity entry.

    Raises:
        HTTPException: If no case with the given id exists.
    """
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")

    activity = CaseActivity(
        case_id=case_id,
        activity_type=payload.activity_type,
        message=payload.message,
        author=payload.author,
        created_at=datetime.now(timezone.utc),
    )
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return activity
