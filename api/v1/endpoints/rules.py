"""Purpose: Expose CRUD endpoints for detection rule metadata."""

from __future__ import annotations

import math
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.schemas.detection_rule import (
    DetectionRuleCreate,
    DetectionRuleRead,
    DetectionRuleUpdate,
    PaginatedDetectionRules,
)
from db.models.detection_rule import DetectionRule, DetectionRuleVersion
from db.models.enums import SeverityEnum
from db.session import get_db

router = APIRouter(prefix="/rules", tags=["rules"])


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
    page: int = Query(default=1, ge=1),
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


@router.post("", response_model=DetectionRuleRead, status_code=201)
def create_rule(payload: DetectionRuleCreate, db: Session = Depends(get_db)) -> DetectionRule:
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
            status_code=409, detail=f"Detection rule name already exists: {payload.name!r}"
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
    db.commit()
    db.refresh(rule)
    return rule


@router.get("/{rule_id}", response_model=DetectionRuleRead)
def get_rule(rule_id: int, db: Session = Depends(get_db)) -> DetectionRule:
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


@router.patch("/{rule_id}", response_model=DetectionRuleRead)
def update_rule(
    rule_id: int, payload: DetectionRuleUpdate, db: Session = Depends(get_db)
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

    updates = payload.model_dump(exclude_unset=True)

    if "name" in updates and updates["name"] != rule.name:
        if _find_by_name(db, updates["name"], exclude_id=rule_id) is not None:
            raise HTTPException(
                status_code=409, detail=f"Detection rule name already exists: {updates['name']!r}"
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

    db.commit()
    db.refresh(rule)
    return rule
