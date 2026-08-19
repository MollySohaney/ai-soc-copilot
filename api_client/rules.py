"""Purpose: Provide typed client functions for the detection rule endpoints."""

from __future__ import annotations

import httpx

from api.schemas.detection_rule import (
    DetectionRuleLanguage,
    DetectionRuleRead,
    PaginatedDetectionRules,
)
from api_client.http import _request, clean_params, get_default_client
from db.models.enums import SeverityEnum


def list_rules(
    *,
    enabled: bool | None = None,
    severity: SeverityEnum | None = None,
    page: int = 1,
    page_size: int = 20,
    client: httpx.Client | None = None,
) -> PaginatedDetectionRules:
    """List detection rules, filtered and paginated, sorted by most recently created first.

    Args:
        enabled: Filter rules by exact enabled state.
        severity: Filter rules by exact severity.
        page: The 1-indexed page number to return.
        page_size: The number of rules per page.
        client: The httpx client to issue the request with; defaults to the
            shared client built from application settings.

    Returns:
        A page of detection rules along with pagination metadata.
    """
    params = clean_params(
        enabled=enabled,
        severity=severity.value if severity is not None else None,
        page=page,
        page_size=page_size,
    )
    response = _request(client or get_default_client(), "GET", "/rules", params=params)
    return PaginatedDetectionRules.model_validate(response.json())


def create_rule(
    *,
    name: str,
    query: str,
    severity: SeverityEnum,
    language: DetectionRuleLanguage,
    description: str | None = None,
    source: str | None = None,
    risk_score: int | None = None,
    enabled: bool = True,
    mitre_tactic: str | None = None,
    mitre_technique_id: str | None = None,
    mitre_technique_name: str | None = None,
    client: httpx.Client | None = None,
) -> DetectionRuleRead:
    """Create a detection rule.

    Args:
        name: The rule name; must be unique.
        query: The detection query text.
        severity: The severity level raised by matches.
        language: The query language the rule is written in.
        description: A human-readable description of the rule.
        source: The origin or authoring source of the rule.
        risk_score: The risk score associated with matches, 0-100.
        enabled: Whether the rule is active.
        mitre_tactic: The associated MITRE ATT&CK tactic name.
        mitre_technique_id: The associated MITRE ATT&CK technique id.
        mitre_technique_name: The associated MITRE ATT&CK technique name.
        client: The httpx client to issue the request with; defaults to the
            shared client built from application settings.

    Returns:
        The newly created detection rule.
    """
    payload = {
        "name": name,
        "query": query,
        "severity": severity.value,
        "language": language,
        "description": description,
        "source": source,
        "risk_score": risk_score,
        "enabled": enabled,
        "mitre_tactic": mitre_tactic,
        "mitre_technique_id": mitre_technique_id,
        "mitre_technique_name": mitre_technique_name,
    }
    response = _request(client or get_default_client(), "POST", "/rules", json=payload)
    return DetectionRuleRead.model_validate(response.json())


def get_rule(rule_id: int, *, client: httpx.Client | None = None) -> DetectionRuleRead:
    """Retrieve a single detection rule by its primary key.

    Args:
        rule_id: The integer primary key of the detection rule.
        client: The httpx client to issue the request with; defaults to the
            shared client built from application settings.

    Returns:
        The matching detection rule.
    """
    response = _request(client or get_default_client(), "GET", f"/rules/{rule_id}")
    return DetectionRuleRead.model_validate(response.json())


def update_rule(
    rule_id: int,
    *,
    name: str | None = None,
    description: str | None = None,
    source: str | None = None,
    language: DetectionRuleLanguage | None = None,
    query: str | None = None,
    severity: SeverityEnum | None = None,
    risk_score: int | None = None,
    enabled: bool | None = None,
    mitre_tactic: str | None = None,
    mitre_technique_id: str | None = None,
    mitre_technique_name: str | None = None,
    client: httpx.Client | None = None,
) -> DetectionRuleRead:
    """Apply a partial update to a detection rule.

    Args:
        rule_id: The integer primary key of the detection rule.
        name: The new rule name, if changing it.
        description: The new description, if changing it.
        source: The new origin/authoring source, if changing it.
        language: The new query language, if changing it.
        query: The new query text, if changing it.
        severity: The new severity level, if changing it.
        risk_score: The new risk score, if changing it.
        enabled: The new enabled state, if changing it.
        mitre_tactic: The new MITRE ATT&CK tactic name, if changing it.
        mitre_technique_id: The new MITRE ATT&CK technique id, if changing it.
        mitre_technique_name: The new MITRE ATT&CK technique name, if changing it.
        client: The httpx client to issue the request with; defaults to the
            shared client built from application settings.

    Returns:
        The updated detection rule.
    """
    payload = clean_params(
        name=name,
        description=description,
        source=source,
        language=language,
        query=query,
        severity=severity.value if severity is not None else None,
        risk_score=risk_score,
        enabled=enabled,
        mitre_tactic=mitre_tactic,
        mitre_technique_id=mitre_technique_id,
        mitre_technique_name=mitre_technique_name,
    )
    response = _request(
        client or get_default_client(), "PATCH", f"/rules/{rule_id}", json=payload
    )
    return DetectionRuleRead.model_validate(response.json())
