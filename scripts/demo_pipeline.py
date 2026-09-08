"""Purpose: Drive fixture ingestion and detection execution over the demo API.

Ingestion and detection execution are authenticated HTTP routes with no command-line
equivalent, so a reproducible demo needs a client that logs in and calls them. This
module does exactly that and nothing else: it adds no capability the API does not
already expose.

Both routes are privileged. Fixture sync requires `operate_integrations` and rule
execution requires `manage_detections`, so this runs as an Admin account. Passwords are
read from the process environment only.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx

# The deterministic seed and the fixture adapter share an anchor of
# 2026-08-15 02:00 UTC (`db/seed.py` BASE_TIME and
# `backend/ingestion/adapters/fixture.py`).
DEMO_ANCHOR = datetime(2026, 8, 15, tzinfo=timezone.utc)

# Ingestion is bounded only by API_MAX_QUERY_WINDOW_DAYS, so one day around the
# anchor collects every fixture record.
DEMO_INGEST_START = DEMO_ANCHOR
DEMO_INGEST_END = DEMO_ANCHOR + timedelta(days=1)

# Detection is bounded by each rule's own lookback_window_seconds, and every
# seeded rule uses 3600. The attack chain runs from 02:00 to 02:09, so this
# one-hour window is the widest that covers it without being rejected.
DEMO_DETECT_START = DEMO_ANCHOR + timedelta(hours=2)
DEMO_DETECT_END = DEMO_ANCHOR + timedelta(hours=3)


@dataclass(frozen=True)
class StepResult:
    """Record the outcome of one demo pipeline step."""

    name: str
    ok: bool
    detail: str


class DemoPipelineError(RuntimeError):
    """Raised when the pipeline cannot continue."""


def login(client: httpx.Client, *, username: str, password: str) -> str:
    """Authenticate and return an opaque bearer token.

    Args:
        client: HTTP client pointed at the API base URL.
        username: Demo account username.
        password: Demo account password from the environment.

    Returns:
        The opaque session token.

    Raises:
        DemoPipelineError: If authentication fails.
    """
    response = client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )
    if response.status_code != 200:
        raise DemoPipelineError(
            f"Login for '{username}' returned HTTP {response.status_code}. "
            "Bootstrap an admin account and set DEMO_PASSWORD."
        )
    token = response.json().get("access_token")
    if not token:
        raise DemoPipelineError("Login succeeded but returned no access token.")
    return token


def ingest_fixture_telemetry(
    client: httpx.Client,
    *,
    token: str,
    start: datetime = DEMO_INGEST_START,
    end: datetime = DEMO_INGEST_END,
) -> StepResult:
    """Run one bounded fixture ingestion sync.

    Args:
        client: HTTP client pointed at the API base URL.
        token: Bearer token for an account holding `operate_integrations`.
        start: Inclusive window start.
        end: Exclusive window end.

    Returns:
        The step outcome, including how many records were written.
    """
    response = client.post(
        "/api/v1/ingestion/fixture/sync",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
            "limit": 100,
            "dry_run": False,
        },
    )
    if response.status_code == 403:
        return StepResult(
            "fixture_ingestion",
            False,
            "Denied. Fixture sync requires the operate_integrations permission (Admin).",
        )
    if response.status_code != 200:
        return StepResult(
            "fixture_ingestion", False, f"Returned HTTP {response.status_code}."
        )
    body = response.json()
    return StepResult(
        "fixture_ingestion",
        body.get("status") != "failed",
        f"status={body.get('status')} fetched={body.get('fetched_count', 0)} "
        f"persisted={body.get('persisted_count', 0)} duplicate={body.get('duplicate_count', 0)}. "
        "Ingestion is restartable: the checkpoint advances, so a second run fetches 0.",
    )


def list_rules(client: httpx.Client, *, token: str) -> list[dict]:
    """Return the detection rules visible to the account.

    Args:
        client: HTTP client pointed at the API base URL.
        token: Bearer token.

    Returns:
        Rule records as returned by the API.

    Raises:
        DemoPipelineError: If the rule listing fails.
    """
    response = client.get(
        "/api/v1/rules",
        headers={"Authorization": f"Bearer {token}"},
        params={"page_size": 100},
    )
    if response.status_code != 200:
        raise DemoPipelineError(f"Listing rules returned HTTP {response.status_code}.")
    return response.json().get("items", [])


def execute_rules(
    client: httpx.Client,
    *,
    token: str,
    rules: Sequence[dict],
    start: datetime = DEMO_DETECT_START,
    end: datetime = DEMO_DETECT_END,
) -> list[StepResult]:
    """Execute every enabled rule over the demo window.

    Args:
        client: HTTP client pointed at the API base URL.
        token: Bearer token for an account holding `manage_detections`.
        rules: Rule records to execute.
        start: Inclusive window start.
        end: Exclusive window end.

    Returns:
        One result per enabled rule.
    """
    results: list[StepResult] = []
    for rule in rules:
        name = rule.get("name", f"rule-{rule.get('id')}")
        if not rule.get("enabled_for_execution"):
            results.append(StepResult(name, True, "Skipped; not enabled for execution."))
            continue
        response = client.post(
            "/api/v1/rules/execute",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "rule_id": rule["id"],
                "window_start": start.isoformat(),
                "window_end": end.isoformat(),
            },
        )
        if response.status_code == 403:
            results.append(
                StepResult(
                    name,
                    False,
                    "Denied. Rule execution requires manage_detections (Detection Engineer or Admin).",
                )
            )
            continue
        if response.status_code != 200:
            results.append(StepResult(name, False, f"Returned HTTP {response.status_code}."))
            continue
        body = response.json()
        created = body.get("alerts_created") or []
        scanned = body.get("events_scanned", 0)
        results.append(
            StepResult(
                name,
                body.get("status") != "failed",
                f"Scanned {scanned} events, created {len(created)} alerts."
                if created
                else f"Scanned {scanned} events, created no new alerts "
                "(these alert fingerprints already exist).",
            )
        )
    return results


def run_pipeline(client: httpx.Client, *, username: str, password: str) -> list[StepResult]:
    """Log in, ingest fixture telemetry, and execute every enabled rule.

    Args:
        client: HTTP client pointed at the API base URL.
        username: Admin account username.
        password: Admin account password from the environment.

    Returns:
        One result per pipeline step.
    """
    token = login(client, username=username, password=password)
    results = [ingest_fixture_telemetry(client, token=token)]
    results.extend(execute_rules(client, token=token, rules=list_rules(client, token=token)))
    return results


def format_report(results: Sequence[StepResult]) -> str:
    """Render pipeline results as aligned terminal output."""
    width = max((len(result.name) for result in results), default=0)
    lines = [
        f"{'OK  ' if result.ok else 'FAIL'}  {result.name.ljust(width)}  {result.detail}"
        for result in results
    ]
    failed = [result for result in results if not result.ok]
    lines.append("")
    lines.append(
        "Demo pipeline complete."
        if not failed
        else f"{len(failed)} of {len(results)} steps failed."
    )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the fixture ingestion and detection execution demo pipeline."""
    import argparse

    from config.settings import load_config

    parser = argparse.ArgumentParser(
        description="Run fixture ingestion and detection execution against the local API."
    )
    parser.add_argument(
        "--username",
        default=os.getenv("DEMO_USERNAME", "demo-admin"),
        help="Admin account to authenticate as (or set DEMO_USERNAME).",
    )
    args = parser.parse_args(argv)

    password = os.getenv("DEMO_PASSWORD")
    if not password:
        print("DEMO_PASSWORD is not set in the environment.", file=sys.stderr)
        return 1

    config = load_config()
    try:
        with httpx.Client(base_url=config.api_base_url, timeout=30.0) as client:
            results = run_pipeline(client, username=args.username, password=password)
    except (DemoPipelineError, httpx.HTTPError) as error:
        print(f"Demo pipeline failed: {error}", file=sys.stderr)
        return 1

    print(format_report(results))
    return 0 if all(result.ok for result in results) else 1


if __name__ == "__main__":
    sys.exit(main())
