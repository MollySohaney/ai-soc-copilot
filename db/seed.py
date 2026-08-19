"""Purpose: Seed a deterministic SOC demo dataset for local/dev use.

Seeds a full SSH brute-force -> valid-login -> sudo-privesc -> SSH-key
persistence attack chain (192.168.64.2 attacking 192.168.64.8, user
mollysohaney) plus benign noise events, alerts, detection rules, and
cases. Safe to re-run: every row is looked up by a natural key before
insert, so repeated runs produce the same records instead of duplicates.

All timestamps are derived from a single fixed constant so that two
clean runs, on any backend, produce byte-identical data. Nothing in
this file may call datetime.now().
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from db.models import (
    Alert,
    AlertStatusEnum,
    Case,
    CaseActivity,
    CaseAlert,
    CasePriorityEnum,
    CaseStatusEnum,
    DetectionRule,
    Event,
    SeverityEnum,
)
from db.models.alert import alert_event

BASE_TIME = datetime(2026, 8, 15, 2, 0, tzinfo=timezone.utc)

ATTACKER_IP = "192.168.64.2"
TARGET_IP = "192.168.64.8"
TARGET_HOST = "ubuntu-target-01"
TARGET_USER = "mollysohaney"


def at(**offset: int) -> datetime:
    """Return BASE_TIME shifted by the given timedelta offset."""
    return BASE_TIME + timedelta(**offset)


def get_or_create(
    session: Session,
    model: type,
    defaults: dict[str, Any] | None = None,
    **lookup_kwargs: Any,
) -> tuple[Any, bool]:
    """Fetch a row by its natural key, inserting it only if not found.

    Args:
        session: Active SQLAlchemy session.
        model: ORM model class to query/insert.
        defaults: Extra column values to apply only on insert.
        lookup_kwargs: Natural-key columns used to find an existing row.

    Returns:
        A (instance, created) tuple.
    """
    instance = session.query(model).filter_by(**lookup_kwargs).one_or_none()
    if instance is not None:
        return instance, False

    params = {**lookup_kwargs, **(defaults or {})}
    instance = model(**params)
    session.add(instance)
    return instance, True


def get_or_create_case_activity(
    session: Session,
    case_id: int,
    message: str,
    **fields: Any,
) -> tuple[CaseActivity, bool]:
    """Fetch a CaseActivity by (case_id, message), inserting only if absent."""
    instance = (
        session.query(CaseActivity)
        .filter_by(case_id=case_id, message=message)
        .one_or_none()
    )
    if instance is not None:
        return instance, False

    instance = CaseActivity(case_id=case_id, message=message, **fields)
    session.add(instance)
    return instance, True


def _seed_detection_rules(session: Session) -> dict[str, DetectionRule]:
    rules_spec = [
        dict(
            name="SSH Brute Force Detection",
            description="Flags repeated failed SSH authentication attempts from a single source against a single account.",
            source="custom",
            language="sigma",
            query="event_category:authentication AND event_action:ssh_login AND event_outcome:failure | count() by source_ip, username > 5",
            severity=SeverityEnum.MEDIUM,
            risk_score=55,
            enabled=True,
            mitre_tactic="Credential Access",
            mitre_technique_id="T1110",
            mitre_technique_name="Brute Force",
        ),
        dict(
            name="Valid Account Login Following Failed Attempts",
            description="Flags a successful SSH login for an account that had multiple recent failed authentication attempts.",
            source="custom",
            language="sigma",
            query="event_category:authentication AND event_action:ssh_login AND event_outcome:success | preceded_by(event_outcome:failure, window=10m)",
            severity=SeverityEnum.HIGH,
            risk_score=70,
            enabled=True,
            mitre_tactic="Initial Access",
            mitre_technique_id="T1078",
            mitre_technique_name="Valid Accounts",
        ),
        dict(
            name="Sudo Privilege Escalation",
            description="Flags sudo/root-shell activity shortly after an SSH login for the same session.",
            source="custom",
            language="sigma",
            query="event_category:process AND process_name:sudo",
            severity=SeverityEnum.HIGH,
            risk_score=75,
            enabled=True,
            mitre_tactic="Privilege Escalation",
            mitre_technique_id="T1548.003",
            mitre_technique_name="Sudo and Sudo Caching",
        ),
        dict(
            name="SSH Authorized Keys Modification",
            description="Flags writes to a user's ~/.ssh/authorized_keys file, a common SSH persistence mechanism.",
            source="custom",
            language="sigma",
            query="event_category:file AND file_path:'*.ssh/authorized_keys'",
            severity=SeverityEnum.CRITICAL,
            risk_score=85,
            enabled=False,
            mitre_tactic="Persistence",
            mitre_technique_id="T1098.004",
            mitre_technique_name="Account Manipulation: SSH Authorized Keys",
        ),
        dict(
            name="Unusual Outbound Network Connection Volume",
            description="Flags hosts making a high volume of outbound connections in a short window.",
            source="custom",
            language="sigma",
            query="event_category:network AND event_action:connection_opened | count() by hostname > 200",
            severity=SeverityEnum.LOW,
            risk_score=25,
            enabled=True,
            mitre_tactic=None,
            mitre_technique_id=None,
            mitre_technique_name=None,
        ),
    ]

    rules: dict[str, DetectionRule] = {}
    for index, spec in enumerate(rules_spec):
        name = spec.pop("name")
        rule, _ = get_or_create(
            session,
            DetectionRule,
            name=name,
            defaults={
                **spec,
                "created_at": at(minutes=-60, seconds=index),
                "updated_at": at(minutes=-60, seconds=index),
            },
        )
        rules[name] = rule
    session.flush()
    return rules


def _make_signal_event(
    event_id: str,
    offset: dict[str, int],
    **fields: Any,
) -> dict[str, Any]:
    timestamp = at(**offset)
    return {
        "event_id": event_id,
        "timestamp": timestamp,
        "ingested_at": timestamp,
        "source_ip": ATTACKER_IP,
        "destination_ip": TARGET_IP,
        "destination_port": 22,
        "hostname": TARGET_HOST,
        "username": TARGET_USER,
        **fields,
    }


def _seed_events(session: Session) -> dict[str, list[Event]]:
    failed_attempts = []
    for i in range(7):
        spec = _make_signal_event(
            f"evt-signal-brute-{i + 1:02d}",
            {"seconds": i * 30},
            source="edr",
            dataset="auth",
            event_category="authentication",
            event_action="ssh_login",
            event_outcome="failure",
            severity="medium",
            source_port=51000 + i,
            process_name="sshd",
            message=f"Failed password for {TARGET_USER} from {ATTACKER_IP} port {51000 + i} ssh2",
        )
        event, _ = get_or_create(session, Event, event_id=spec.pop("event_id"), defaults=spec)
        failed_attempts.append(event)

    success_spec = _make_signal_event(
        "evt-signal-success-login",
        {"minutes": 5},
        source="edr",
        dataset="auth",
        event_category="authentication",
        event_action="ssh_login",
        event_outcome="success",
        severity="high",
        source_port=51007,
        process_name="sshd",
        message=f"Accepted password for {TARGET_USER} from {ATTACKER_IP} port 51007 ssh2",
    )
    success_login, _ = get_or_create(
        session, Event, event_id=success_spec.pop("event_id"), defaults=success_spec
    )

    privesc_specs = [
        (
            "evt-signal-privesc-01",
            {"minutes": 6},
            "sudo -i",
            "session opened for user root by mollysohaney(uid=1000)",
        ),
        (
            "evt-signal-privesc-02",
            {"minutes": 6, "seconds": 20},
            "sudo cat /etc/shadow",
            "COMMAND=/usr/bin/cat /etc/shadow run as root by mollysohaney",
        ),
        (
            "evt-signal-privesc-03",
            {"minutes": 6, "seconds": 40},
            "sudo useradd -m svc-backup2",
            "COMMAND=/usr/sbin/useradd -m svc-backup2 run as root by mollysohaney",
        ),
    ]
    privesc_events = []
    for event_id, offset, cmdline, message in privesc_specs:
        spec = _make_signal_event(
            event_id,
            offset,
            source="edr",
            dataset="process",
            event_category="process",
            event_action="sudo_exec",
            event_outcome="success",
            severity="high",
            process_name="sudo",
            process_command_line=cmdline,
            message=message,
        )
        event, _ = get_or_create(session, Event, event_id=spec.pop("event_id"), defaults=spec)
        privesc_events.append(event)

    persistence_specs = [
        (
            "evt-signal-persist-01",
            {"minutes": 8},
            "/home/mollysohaney/.ssh/authorized_keys",
            "New SSH public key appended to authorized_keys for user mollysohaney",
        ),
        (
            "evt-signal-persist-02",
            {"minutes": 8, "seconds": 15},
            "/home/mollysohaney/.ssh/authorized_keys",
            "Permissions changed on authorized_keys (chmod 600) for user mollysohaney",
        ),
        (
            "evt-signal-persist-03",
            {"minutes": 8, "seconds": 30},
            "/etc/cron.d/system-health",
            "New cron entry written to /etc/cron.d/system-health by mollysohaney",
        ),
    ]
    persistence_events = []
    for event_id, offset, file_path, message in persistence_specs:
        spec = _make_signal_event(
            event_id,
            offset,
            source="edr",
            dataset="file",
            event_category="file",
            event_action="file_modified",
            event_outcome="success",
            severity="critical",
            file_path=file_path,
            message=message,
        )
        event, _ = get_or_create(session, Event, event_id=spec.pop("event_id"), defaults=spec)
        persistence_events.append(event)

    noise_hosts = ["web-prod-02", "db-prod-01", "app-prod-03", "mail-prod-01", "vpn-gateway-01"]
    noise_users = ["asmith", "bjones", "cwhite", "dgarcia", "svc-backup"]
    noise_ips = ["10.0.1.15", "10.0.1.22", "10.0.2.9", "10.0.3.44", "10.0.4.7"]
    noise_templates = [
        dict(
            event_category="authentication",
            event_action="ssh_login",
            event_outcome="success",
            severity="low",
            process_name="sshd",
            message_fmt="Successful login for {user} from {ip}",
        ),
        dict(
            event_category="process",
            event_action="process_start",
            event_outcome="success",
            severity="low",
            process_name="bash",
            process_command_line="/usr/bin/bash --login",
            message_fmt="Process started for {user} on {host}",
        ),
        dict(
            event_category="network",
            event_action="connection_opened",
            event_outcome="success",
            severity="low",
            destination_port=443,
            message_fmt="Outbound connection from {host} to 93.184.216.34:443",
        ),
        dict(
            event_category="file",
            event_action="file_read",
            event_outcome="success",
            severity="low",
            file_path="/var/log/syslog",
            message_fmt="File read: /var/log/syslog by {user}",
        ),
    ]

    noise_events = []
    noise_count = 46
    for i in range(noise_count):
        host = noise_hosts[i % len(noise_hosts)]
        user = noise_users[i % len(noise_users)]
        ip = noise_ips[i % len(noise_ips)]
        template = dict(noise_templates[i % len(noise_templates)])
        message_fmt = template.pop("message_fmt")
        timestamp = at(hours=1, seconds=i * 90)
        spec = {
            "source": "edr",
            "dataset": "noise",
            "hostname": host,
            "username": user,
            "source_ip": ip,
            "timestamp": timestamp,
            "ingested_at": timestamp,
            "message": message_fmt.format(user=user, host=host, ip=ip),
            **template,
        }
        event_id = f"evt-noise-{i + 1:03d}"
        event, _ = get_or_create(session, Event, event_id=event_id, defaults=spec)
        noise_events.append(event)

    session.flush()

    return {
        "failed_attempts": failed_attempts,
        "success_login": [success_login],
        "privesc": privesc_events,
        "persistence": persistence_events,
        "noise": noise_events,
    }


def _link_alert_events(session: Session, alert: Alert, events: list[Event]) -> None:
    """Idempotently link an alert to events via the alert_event association table."""
    for event in events:
        exists = session.execute(
            alert_event.select().where(
                alert_event.c.alert_id == alert.id,
                alert_event.c.event_id == event.id,
            )
        ).first()
        if exists is None:
            session.execute(alert_event.insert().values(alert_id=alert.id, event_id=event.id))


def _seed_alerts(
    session: Session,
    events: dict[str, list[Event]],
    rules: dict[str, DetectionRule],
) -> dict[str, Alert]:
    alerts: dict[str, Alert] = {}

    brute_rule = rules["SSH Brute Force Detection"]
    brute_alert, _ = get_or_create(
        session,
        Alert,
        external_id="ALERT-0001",
        defaults=dict(
            title="Multiple Failed SSH Authentication Attempts",
            description=(
                f"7 failed SSH authentication attempts for user {TARGET_USER} on "
                f"{TARGET_HOST} from {ATTACKER_IP} within a 3-minute window."
            ),
            severity=SeverityEnum.MEDIUM,
            risk_score=55,
            status=AlertStatusEnum.CLOSED,
            source="edr",
            rule_id=brute_rule.name,
            hostname=TARGET_HOST,
            username=TARGET_USER,
            source_ip=ATTACKER_IP,
            destination_ip=TARGET_IP,
            mitre_tactic="Credential Access",
            mitre_technique_id="T1110",
            mitre_technique_name="Brute Force",
            first_seen=at(seconds=0),
            last_seen=at(seconds=180),
            created_at=at(minutes=1),
            updated_at=at(minutes=1),
        ),
    )
    session.flush()
    _link_alert_events(session, brute_alert, events["failed_attempts"])
    alerts["brute_force"] = brute_alert

    login_rule = rules["Valid Account Login Following Failed Attempts"]
    login_alert, _ = get_or_create(
        session,
        Alert,
        external_id="ALERT-0002",
        defaults=dict(
            title="Successful SSH Login Following Failed Attempts",
            description=(
                f"Successful SSH login for user {TARGET_USER} on {TARGET_HOST} from "
                f"{ATTACKER_IP}, immediately following the failed attempts in ALERT-0001."
            ),
            severity=SeverityEnum.HIGH,
            risk_score=70,
            status=AlertStatusEnum.IN_PROGRESS,
            source="edr",
            rule_id=login_rule.name,
            hostname=TARGET_HOST,
            username=TARGET_USER,
            source_ip=ATTACKER_IP,
            destination_ip=TARGET_IP,
            mitre_tactic="Initial Access",
            mitre_technique_id="T1078",
            mitre_technique_name="Valid Accounts",
            first_seen=at(minutes=5),
            last_seen=at(minutes=5),
            created_at=at(minutes=6),
            updated_at=at(minutes=6),
        ),
    )
    session.flush()
    _link_alert_events(session, login_alert, events["success_login"])
    alerts["valid_accounts"] = login_alert

    privesc_rule = rules["Sudo Privilege Escalation"]
    root_shell_alert, _ = get_or_create(
        session,
        Alert,
        external_id="ALERT-0003",
        defaults=dict(
            title="Root Shell Obtained via Sudo",
            description=(
                f"User {TARGET_USER} obtained an interactive root shell via `sudo -i` "
                f"on {TARGET_HOST} shortly after the login in ALERT-0002."
            ),
            severity=SeverityEnum.HIGH,
            risk_score=75,
            status=AlertStatusEnum.IN_PROGRESS,
            source="edr",
            rule_id=privesc_rule.name,
            hostname=TARGET_HOST,
            username=TARGET_USER,
            source_ip=ATTACKER_IP,
            destination_ip=TARGET_IP,
            mitre_tactic="Privilege Escalation",
            mitre_technique_id="T1548.003",
            mitre_technique_name="Sudo and Sudo Caching",
            first_seen=at(minutes=6),
            last_seen=at(minutes=6),
            created_at=at(minutes=7),
            updated_at=at(minutes=7),
        ),
    )
    session.flush()
    _link_alert_events(session, root_shell_alert, events["privesc"][:1])
    alerts["root_shell"] = root_shell_alert

    sensitive_cmd_alert, _ = get_or_create(
        session,
        Alert,
        external_id="ALERT-0004",
        defaults=dict(
            title="Sensitive Commands Executed via Sudo",
            description=(
                f"User {TARGET_USER} used sudo to read /etc/shadow and create a new "
                f"local account (svc-backup2) on {TARGET_HOST}."
            ),
            severity=SeverityEnum.HIGH,
            risk_score=80,
            status=AlertStatusEnum.IN_PROGRESS,
            source="edr",
            rule_id=privesc_rule.name,
            hostname=TARGET_HOST,
            username=TARGET_USER,
            source_ip=ATTACKER_IP,
            destination_ip=TARGET_IP,
            mitre_tactic="Privilege Escalation",
            mitre_technique_id="T1548.003",
            mitre_technique_name="Sudo and Sudo Caching",
            first_seen=at(minutes=6, seconds=20),
            last_seen=at(minutes=6, seconds=40),
            created_at=at(minutes=7, seconds=30),
            updated_at=at(minutes=7, seconds=30),
        ),
    )
    session.flush()
    _link_alert_events(session, sensitive_cmd_alert, events["privesc"][1:])
    alerts["sensitive_commands"] = sensitive_cmd_alert

    persist_rule = rules["SSH Authorized Keys Modification"]
    persistence_alert, _ = get_or_create(
        session,
        Alert,
        external_id="ALERT-0005",
        defaults=dict(
            title="SSH Authorized Keys Modified for mollysohaney",
            description=(
                f"~/.ssh/authorized_keys was modified for user {TARGET_USER} on "
                f"{TARGET_HOST}, and a new cron entry was written, establishing persistence "
                f"after the privilege escalation in ALERT-0003 and ALERT-0004."
            ),
            severity=SeverityEnum.CRITICAL,
            risk_score=90,
            status=AlertStatusEnum.NEW,
            source="edr",
            rule_id=persist_rule.name,
            hostname=TARGET_HOST,
            username=TARGET_USER,
            source_ip=ATTACKER_IP,
            destination_ip=TARGET_IP,
            mitre_tactic="Persistence",
            mitre_technique_id="T1098.004",
            mitre_technique_name="Account Manipulation: SSH Authorized Keys",
            first_seen=at(minutes=8),
            last_seen=at(minutes=8, seconds=30),
            created_at=at(minutes=9),
            updated_at=at(minutes=9),
        ),
    )
    session.flush()
    _link_alert_events(session, persistence_alert, events["persistence"])
    alerts["persistence"] = persistence_alert

    chain_alert, _ = get_or_create(
        session,
        Alert,
        external_id="ALERT-0006",
        defaults=dict(
            title="Correlated Attack Chain: SSH Brute Force to Persistence",
            description=(
                f"Full attack chain correlated for {TARGET_USER}@{TARGET_HOST} "
                f"originating from {ATTACKER_IP}: 7 failed SSH logins (ALERT-0001, "
                f"events evt-signal-brute-01..07) at {at(seconds=0).isoformat()}, followed "
                f"by a successful SSH login (ALERT-0002, event evt-signal-success-login) at "
                f"{at(minutes=5).isoformat()}, a root shell obtained via sudo (ALERT-0003, "
                f"event evt-signal-privesc-01) and sensitive sudo commands "
                f"(ALERT-0004, events evt-signal-privesc-02/03) at "
                f"{at(minutes=6).isoformat()}, and finally persistence established via "
                f"authorized_keys and cron modification (ALERT-0005, events "
                f"evt-signal-persist-01/02/03) at {at(minutes=8).isoformat()}."
            ),
            severity=SeverityEnum.CRITICAL,
            risk_score=95,
            status=AlertStatusEnum.NEW,
            source="correlation-engine",
            rule_id=None,
            hostname=TARGET_HOST,
            username=TARGET_USER,
            source_ip=ATTACKER_IP,
            destination_ip=TARGET_IP,
            mitre_tactic="Persistence",
            mitre_technique_id="T1098.004",
            mitre_technique_name="Account Manipulation: SSH Authorized Keys",
            first_seen=at(seconds=0),
            last_seen=at(minutes=8, seconds=30),
            created_at=at(minutes=9, seconds=30),
            updated_at=at(minutes=9, seconds=30),
        ),
    )
    session.flush()
    alerts["chain"] = chain_alert

    filler_rule = rules["Unusual Outbound Network Connection Volume"]
    filler_specs = [
        (
            "ALERT-1001",
            "Unusual Outbound Connection Volume from web-prod-02",
            SeverityEnum.LOW,
            20,
            AlertStatusEnum.FALSE_POSITIVE,
            "web-prod-02",
            "asmith",
            "10.0.1.15",
        ),
        (
            "ALERT-1002",
            "Unusual Outbound Connection Volume from db-prod-01",
            SeverityEnum.LOW,
            22,
            AlertStatusEnum.CLOSED,
            "db-prod-01",
            "bjones",
            "10.0.1.22",
        ),
        (
            "ALERT-1003",
            "Repeated File Reads of /var/log/syslog on app-prod-03",
            SeverityEnum.LOW,
            18,
            AlertStatusEnum.NEW,
            "app-prod-03",
            "cwhite",
            "10.0.2.9",
        ),
        (
            "ALERT-1004",
            "New Process Started on mail-prod-01",
            SeverityEnum.MEDIUM,
            35,
            AlertStatusEnum.IN_PROGRESS,
            "mail-prod-01",
            "dgarcia",
            "10.0.3.44",
        ),
        (
            "ALERT-1005",
            "Elevated Login Volume on vpn-gateway-01",
            SeverityEnum.MEDIUM,
            40,
            AlertStatusEnum.NEW,
            "vpn-gateway-01",
            "svc-backup",
            "10.0.4.7",
        ),
        (
            "ALERT-1006",
            "Outbound Connection Volume Review Closed",
            SeverityEnum.LOW,
            15,
            AlertStatusEnum.FALSE_POSITIVE,
            "web-prod-02",
            "asmith",
            "10.0.1.15",
        ),
        (
            "ALERT-1007",
            "Scheduled Maintenance Login Burst on db-prod-01",
            SeverityEnum.MEDIUM,
            30,
            AlertStatusEnum.CLOSED,
            "db-prod-01",
            "svc-backup",
            "10.0.1.22",
        ),
    ]
    for index, (external_id, title, severity, risk_score, status, host, user, ip) in enumerate(
        filler_specs
    ):
        filler_alert, _ = get_or_create(
            session,
            Alert,
            external_id=external_id,
            defaults=dict(
                title=title,
                description=f"Low-signal alert generated by {filler_rule.name} for {host}.",
                severity=severity,
                risk_score=risk_score,
                status=status,
                source="edr",
                rule_id=filler_rule.name,
                hostname=host,
                username=user,
                source_ip=ip,
                destination_ip=None,
                mitre_tactic=None,
                mitre_technique_id=None,
                mitre_technique_name=None,
                first_seen=at(hours=1, minutes=index),
                last_seen=at(hours=1, minutes=index),
                created_at=at(hours=1, minutes=index, seconds=30),
                updated_at=at(hours=1, minutes=index, seconds=30),
            ),
        )
        alerts[f"filler_{index + 1}"] = filler_alert

    session.flush()
    return alerts


def _seed_cases(session: Session, alerts: dict[str, Alert]) -> None:
    chain_case, _ = get_or_create(
        session,
        Case,
        case_number="CASE-2026-0001",
        defaults=dict(
            title="SSH Brute Force to Persistence",
            description=(
                f"Investigation into a full attack chain against {TARGET_HOST} "
                f"originating from {ATTACKER_IP}, spanning brute-force credential "
                f"access, a valid-account login, sudo privilege escalation, and "
                f"SSH-key/cron persistence for user {TARGET_USER}."
            ),
            status=CaseStatusEnum.IN_PROGRESS,
            priority=CasePriorityEnum.CRITICAL,
            assignee="analyst.rivera",
            created_at=at(minutes=10),
            updated_at=at(minutes=40),
        ),
    )
    session.flush()

    chain_alert_keys = [
        "brute_force",
        "valid_accounts",
        "root_shell",
        "sensitive_commands",
        "persistence",
        "chain",
    ]
    for offset, key in enumerate(chain_alert_keys):
        alert = alerts[key]
        get_or_create(
            session,
            CaseAlert,
            case_id=chain_case.id,
            alert_id=alert.id,
            defaults={"added_at": at(minutes=10, seconds=offset * 5)},
        )

    activities = [
        ("triage", "Case opened after correlated attack-chain alert ALERT-0006 fired.", "analyst.rivera", at(minutes=10)),
        ("note", "Confirmed 7 failed SSH logins from 192.168.64.2 preceded a successful login as mollysohaney (ALERT-0001, ALERT-0002).", "analyst.rivera", at(minutes=15)),
        ("note", "Root shell and sensitive sudo commands confirmed on ubuntu-target-01 (ALERT-0003, ALERT-0004); host isolated from network.", "analyst.rivera", at(minutes=22)),
        ("note", "Identified unauthorized SSH key in ~/.ssh/authorized_keys and a new cron entry; both removed (ALERT-0005).", "analyst.rivera", at(minutes=30)),
        ("status_change", "Escalated to critical priority pending confirmation that 192.168.64.2 is blocked at the firewall.", "analyst.rivera", at(minutes=40)),
    ]
    for activity_type, message, author, created_at in activities:
        get_or_create_case_activity(
            session,
            case_id=chain_case.id,
            message=message,
            activity_type=activity_type,
            author=author,
            created_at=created_at,
        )

    review_case, _ = get_or_create(
        session,
        Case,
        case_number="CASE-2026-0002",
        defaults=dict(
            title="Outbound Connection Volume Review",
            description="Review of low-signal outbound connection volume alerts across several production hosts.",
            status=CaseStatusEnum.RESOLVED,
            priority=CasePriorityEnum.MEDIUM,
            assignee="analyst.chen",
            created_at=at(hours=1, minutes=30),
            updated_at=at(hours=1, minutes=50),
            closed_at=at(hours=1, minutes=50),
        ),
    )
    session.flush()
    for offset, key in enumerate(["filler_1", "filler_2"]):
        get_or_create(
            session,
            CaseAlert,
            case_id=review_case.id,
            alert_id=alerts[key].id,
            defaults={"added_at": at(hours=1, minutes=31 + offset)},
        )
    for activity_type, message, author, created_at in [
        ("triage", "Reviewed outbound connection alerts for web-prod-02 and db-prod-01.", "analyst.chen", at(hours=1, minutes=31)),
        ("status_change", "Both alerts confirmed as scheduled backup jobs; marked false positive and resolved case.", "analyst.chen", at(hours=1, minutes=50)),
    ]:
        get_or_create_case_activity(
            session,
            case_id=review_case.id,
            message=message,
            activity_type=activity_type,
            author=author,
            created_at=created_at,
        )

    login_case, _ = get_or_create(
        session,
        Case,
        case_number="CASE-2026-0003",
        defaults=dict(
            title="Elevated Login Volume Follow-up",
            description="Follow-up on elevated login volume flagged on vpn-gateway-01.",
            status=CaseStatusEnum.OPEN,
            priority=CasePriorityEnum.LOW,
            assignee=None,
            created_at=at(hours=1, minutes=5),
            updated_at=at(hours=1, minutes=5),
        ),
    )
    session.flush()
    get_or_create(
        session,
        CaseAlert,
        case_id=login_case.id,
        alert_id=alerts["filler_5"].id,
        defaults={"added_at": at(hours=1, minutes=6)},
    )
    get_or_create_case_activity(
        session,
        case_id=login_case.id,
        message="Case opened for triage; awaiting assignment.",
        activity_type="triage",
        author=None,
        created_at=at(hours=1, minutes=6),
    )

    session.flush()


def seed(session: Session) -> None:
    """Seed the deterministic SOC demo dataset into the given session.

    Idempotent: safe to call repeatedly against the same database, since
    every row is looked up by a natural key before insert.
    """
    rules = _seed_detection_rules(session)
    events = _seed_events(session)
    alerts = _seed_alerts(session, events, rules)
    _seed_cases(session, alerts)


if __name__ == "__main__":
    from db.session import SessionLocal

    db_session = SessionLocal()
    try:
        seed(db_session)
        db_session.commit()
    finally:
        db_session.close()
