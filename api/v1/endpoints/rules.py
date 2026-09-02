"""Purpose: Expose CRUD endpoints for detection rule metadata."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.dependencies.auth import require_permission
from api.dependencies.limits import require_abuse_control
from backend.audit import AuditService
from api.schemas.detection_rule import (
    DetectionRuleCreate,
    DetectionRuleRead,
    DetectionRuleUpdate,
    DetectionExecutionResponse,
    DetectionRunRead,
    PaginatedDetectionRuns,
    PaginatedDetectionRules,
    RuleExecutionRequest,
    RuleValidationResponse,
    ValidateRuleRequest,
)
from api.validation import PositiveId
from backend.detection.dsl import parse_logic
from backend.detection.service import execute_rule
from backend.security.auth import AuthenticatedPrincipal
from backend.security.rbac import Permission
from db.models.detection_rule import DetectionRule, DetectionRuleVersion
from db.models.detection_run import DetectionRun
from db.models.enums import SeverityEnum
from db.session import get_db

router = APIRouter(prefix="/rules", tags=["rules"])


def _execution_window(rule: DetectionRule, request: RuleExecutionRequest) -> tuple[datetime, datetime]:
    end = (request.window_end or datetime.now(timezone.utc)).astimezone(timezone.utc)
    start = (request.window_start or end - timedelta(seconds=rule.lookback_window_seconds)).astimezone(timezone.utc)
    return start, end


@router.post(
    "/validate",
    response_model=RuleValidationResponse,
    dependencies=[Depends(require_abuse_control("detection"))],
)
def validate_rule(
    payload: ValidateRuleRequest,
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.MANAGE_DETECTIONS)
    ),
    db: Session = Depends(get_db),
) -> RuleValidationResponse:
    """Validate structured rule logic without saving or executing it."""
    try:
        logic = parse_logic(payload.logic)
    except ValueError as error:
        AuditService(db).record(
            action="rule.validate",
            outcome="failed",
            actor=principal.user,
            target_type="detection_rule_logic",
            details={"error_type": type(error).__name__},
        )
        db.commit()
        raise HTTPException(status_code=422, detail=str(error)) from error
    AuditService(db).record(
        action="rule.validate",
        outcome="succeeded",
        actor=principal.user,
        target_type="detection_rule_logic",
        details={"rule_type": logic.rule_type, "dsl_version": logic.dsl_version},
    )
    db.commit()
    return RuleValidationResponse(valid=True, dsl_version=logic.dsl_version, rule_type=logic.rule_type)


def _run_rule(
    payload: RuleExecutionRequest,
    db: Session,
    principal: AuthenticatedPrincipal,
    *,
    dry_run: bool,
) -> DetectionExecutionResponse:
    rule = db.get(DetectionRule, payload.rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Detection rule not found")
    start, end = _execution_window(rule, payload)
    action = "rule.test" if dry_run else "rule.execute"

    def _record_completed(run: DetectionRun, alert_ids: tuple[int, ...]) -> None:
        AuditService(db).record(
            action=action,
            outcome="succeeded",
            actor=principal.user,
            target_type="detection_rule",
            target_id=rule.id,
            details={
                "run_id": run.id,
                "rule_version": rule.version,
                "alerts_created": list(alert_ids),
            },
        )

    try:
        result = execute_rule(
            db,
            rule,
            window_start=start,
            window_end=end,
            dry_run=dry_run,
            before_commit=None if dry_run else _record_completed,
        )
    except ValueError as error:
        AuditService(db).record(
            action=action,
            outcome="failed",
            actor=principal.user,
            target_type="detection_rule",
            target_id=rule.id,
            details={"error_type": type(error).__name__},
        )
        db.commit()
        raise HTTPException(status_code=422, detail=str(error)) from error
    if dry_run or result.run_id is None:
        AuditService(db).record(
            action=action,
            outcome="succeeded",
            actor=principal.user,
            target_type="detection_rule",
            target_id=rule.id,
            details={
                "run_id": result.run_id,
                "rule_version": rule.version,
                "alerts_created": list(result.alerts_created),
            },
        )
        db.commit()
    return DetectionExecutionResponse(
        status=result.status, run_id=result.run_id, events_scanned=result.events_scanned,
        alerts_created=list(result.alerts_created), would_fire=list(result.would_fire),
        truncated=result.truncated, error_detail=result.error_detail,
    )


@router.post(
    "/test",
    response_model=DetectionExecutionResponse,
    dependencies=[Depends(require_abuse_control("detection"))],
)
def test_rule(
    payload: RuleExecutionRequest,
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.MANAGE_DETECTIONS)
    ),
    db: Session = Depends(get_db),
) -> DetectionExecutionResponse:
    """Dry-run a rule without creating alerts or a persisted detection run."""
    return _run_rule(payload, db, principal, dry_run=True)


@router.post(
    "/execute",
    response_model=DetectionExecutionResponse,
    dependencies=[Depends(require_abuse_control("detection"))],
)
def execute_rule_now(
    payload: RuleExecutionRequest,
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.MANAGE_DETECTIONS)
    ),
    db: Session = Depends(get_db),
) -> DetectionExecutionResponse:
    """Execute a rule over an explicit or configured lookback window."""
    return _run_rule(payload, db, principal, dry_run=False)


@router.get("/{rule_id}/runs", response_model=PaginatedDetectionRuns)
def list_detection_runs(
    rule_id: PositiveId, page: int = Query(default=1, ge=1, le=10_000), page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PaginatedDetectionRuns:
    """List bounded execution history for one rule."""
    if db.get(DetectionRule, rule_id) is None:
        raise HTTPException(status_code=404, detail="Detection rule not found")
    filters = [DetectionRun.detection_rule_id == rule_id]
    total = db.scalar(select(func.count()).select_from(DetectionRun).where(*filters)) or 0
    items = db.scalars(
        select(DetectionRun).where(*filters).order_by(DetectionRun.started_at.desc(), DetectionRun.id.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    return PaginatedDetectionRuns(
        items=items, total=total, page=page, page_size=page_size,
        total_pages=math.ceil(total / page_size) if total else 0,
    )


@router.get("/{rule_id}/runs/{run_id}", response_model=DetectionRunRead)
def get_detection_run(
    rule_id: PositiveId, run_id: PositiveId, db: Session = Depends(get_db)
) -> DetectionRun:
    """Retrieve one execution record belonging to a rule."""
    run = db.get(DetectionRun, run_id)
    if run is None or run.detection_rule_id != rule_id:
        raise HTTPException(status_code=404, detail="Detection run not found")
    return run


def _find_by_name(db: Session, name: str, *, exclude_id: int | None = None) -> DetectionRule | None:
    """Look up a detection rule by name, optionally excluding a given id.

    Args:
        db: The database session dependency.
        name: The rule name to look up.
        exclude_id: If given, exclude the rule with this primary key from the match.

    Returns:
        The matching detection rule, or None if no other rule has that name.
    """
    stmt = select(DetectionRule).where(DetectionRule.name == name)
    if exclude_id is not None:
        stmt = stmt.where(DetectionRule.id != exclude_id)
    return db.scalar(stmt)


@router.get("", response_model=PaginatedDetectionRules)
def list_rules(
    enabled: bool | None = None,
    severity: SeverityEnum | None = None,
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PaginatedDetectionRules:
    """List detection rules, filtered and paginated, sorted by most recently created first.

    Args:
        enabled: Filter rules by exact enabled state.
        severity: Filter rules by exact severity.
        page: The 1-indexed page number to return.
        page_size: The number of rules per page.
        db: The database session dependency.

    Returns:
        A page of detection rules along with pagination metadata.
    """
    filters = []
    if enabled is not None:
        filters.append(DetectionRule.enabled == enabled)
    if severity is not None:
        filters.append(DetectionRule.severity == severity)

    count_stmt = select(func.count()).select_from(DetectionRule).where(*filters)
    total = db.scalar(count_stmt) or 0

    stmt = (
        select(DetectionRule)
        .where(*filters)
        .order_by(DetectionRule.created_at.desc(), DetectionRule.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = db.scalars(stmt).all()

    total_pages = math.ceil(total / page_size) if total else 0

    return PaginatedDetectionRules(
        items=[DetectionRuleRead.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post(
    "",
    response_model=DetectionRuleRead,
    status_code=201,
)
def create_rule(
    payload: DetectionRuleCreate,
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.MANAGE_DETECTIONS)
    ),
    db: Session = Depends(get_db),
) -> DetectionRule:
    """Create a detection rule.

    Args:
        payload: The fields for the new detection rule.
        db: The database session dependency.

    Returns:
        The newly created detection rule.

    Raises:
        HTTPException: If a rule with the same name already exists.
    """
    if _find_by_name(db, payload.name) is not None:
        raise HTTPException(
            status_code=409, detail="Detection rule name already exists."
        )

    rule = DetectionRule(**payload.model_dump())
    db.add(rule)
    db.flush()
    db.add(
        DetectionRuleVersion(
            detection_rule_id=rule.id,
            version=rule.version,
            rule_type=rule.rule_type,
            structured_logic=rule.structured_logic,
            legacy_query=rule.query,
        )
    )
    AuditService(db).record(
        action="rule.create",
        outcome="succeeded",
        actor=principal.user,
        target_type="detection_rule",
        target_id=rule.id,
        after_state={
            "name": rule.name,
            "version": rule.version,
            "enabled": rule.enabled,
            "enabled_for_execution": rule.enabled_for_execution,
        },
    )
    db.commit()
    db.refresh(rule)
    return rule


@router.get("/{rule_id}", response_model=DetectionRuleRead)
def get_rule(rule_id: PositiveId, db: Session = Depends(get_db)) -> DetectionRule:
    """Retrieve a single detection rule by its primary key.

    Args:
        rule_id: The integer primary key of the detection rule.
        db: The database session dependency.

    Returns:
        The matching detection rule.

    Raises:
        HTTPException: If no detection rule with the given id exists.
    """
    rule = db.get(DetectionRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Detection rule not found")
    return rule


@router.patch(
    "/{rule_id}",
    response_model=DetectionRuleRead,
)
def update_rule(
    rule_id: PositiveId,
    payload: DetectionRuleUpdate,
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.MANAGE_DETECTIONS)
    ),
    db: Session = Depends(get_db),
) -> DetectionRule:
    """Apply a partial update to a detection rule.

    Args:
        rule_id: The integer primary key of the detection rule.
        payload: The fields to update; unset fields are left unchanged.
        db: The database session dependency.

    Returns:
        The updated detection rule.

    Raises:
        HTTPException: If no detection rule with the given id exists, or the new
            name collides with another existing rule.
    """
    rule = db.get(DetectionRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Detection rule not found")

    before_state = {
        "name": rule.name,
        "version": rule.version,
        "enabled": rule.enabled,
        "enabled_for_execution": rule.enabled_for_execution,
    }
    updates = payload.model_dump(exclude_unset=True)

    if "name" in updates and updates["name"] != rule.name:
        if _find_by_name(db, updates["name"], exclude_id=rule_id) is not None:
            raise HTTPException(
                status_code=409, detail="Detection rule name already exists."
            )

    logic_changed = any(
        field in updates for field in ("query", "structured_logic", "rule_type")
    )
    previous_version = rule.version
    previous_snapshot = {
        "rule_type": rule.rule_type,
        "structured_logic": rule.structured_logic,
        "legacy_query": rule.query,
    }
    for field, value in updates.items():
        setattr(rule, field, value)
    if logic_changed:
        if not db.scalar(
            select(DetectionRuleVersion).where(
                DetectionRuleVersion.detection_rule_id == rule.id,
                DetectionRuleVersion.version == rule.version,
            )
        ):
            db.add(
                DetectionRuleVersion(
                    detection_rule_id=rule.id,
                    version=previous_version,
                    **previous_snapshot,
                )
            )
        rule.version += 1
        db.add(
            DetectionRuleVersion(
                detection_rule_id=rule.id,
                version=rule.version,
                rule_type=rule.rule_type,
                structured_logic=rule.structured_logic,
                legacy_query=rule.query,
            )
        )
    if updates:
        rule.updated_at = datetime.now(timezone.utc)

    AuditService(db).record(
        action="rule.update",
        outcome="succeeded",
        actor=principal.user,
        target_type="detection_rule",
        target_id=rule.id,
        before_state=before_state,
        after_state={
            "name": rule.name,
            "version": rule.version,
            "enabled": rule.enabled,
            "enabled_for_execution": rule.enabled_for_execution,
        },
    )

    db.commit()
    db.refresh(rule)
    return rule
