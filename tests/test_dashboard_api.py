"""Purpose: Verify the /dashboard API endpoints against the seeded demo dataset."""

from __future__ import annotations

from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from db.models.alert import Alert
from db.models.enums import AlertStatusEnum, SeverityEnum
from db.seed import BASE_TIME

# BASE_TIME is the moment the earliest seeded alert's created_at is measured from;
# every seeded alert's created_at falls strictly after BASE_TIME (earliest is
# BASE_TIME + 1 minute), so a 1-day period ending exactly at BASE_TIME has zero
# alerts in both the current and previous windows.
NULL_GUARD_AS_OF = BASE_TIME.isoformat()


def test_summary_counts_match_seeded_data(client: TestClient) -> None:
    """The summary reflects the known seeded totals across alerts and cases."""
    response = client.get(
        "/api/v1/dashboard/summary",
        params={"as_of": NULL_GUARD_AS_OF, "period_days": 1},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total_alerts"] == 13
    assert body["new_alerts"] == 4
    assert body["critical_alerts"] == 2
    assert body["in_progress_alerts"] == 4
    assert body["open_cases"] == 2


def test_summary_mean_time_to_acknowledge_is_always_null(client: TestClient) -> None:
    """mean_time_to_acknowledge_minutes is always null since alerts have no ack field."""
    response = client.get("/api/v1/dashboard/summary")

    assert response.status_code == 200
    assert response.json()["mean_time_to_acknowledge_minutes"] is None


def test_summary_alert_change_pct_is_null_when_previous_period_empty(
    client: TestClient,
) -> None:
    """alert_change_pct is null when the previous comparison period has zero alerts."""
    response = client.get(
        "/api/v1/dashboard/summary",
        params={"as_of": NULL_GUARD_AS_OF, "period_days": 1},
    )

    assert response.status_code == 200
    assert response.json()["alert_change_pct"] is None


def test_summary_alert_change_pct_computes_percentage(
    client: TestClient, db_session: Session
) -> None:
    """alert_change_pct reflects a real period-over-period change when both periods have data."""
    reference = BASE_TIME + timedelta(days=10)
    current_start = reference - timedelta(days=1)
    previous_start = current_start - timedelta(days=1)

    # 2 alerts land in the current period, 4 in the previous period.
    for i in range(2):
        db_session.add(
            Alert(
                title=f"Current period alert {i}",
                severity=SeverityEnum.LOW,
                status=AlertStatusEnum.NEW,
                created_at=current_start + timedelta(hours=i + 1),
            )
        )
    for i in range(4):
        db_session.add(
            Alert(
                title=f"Previous period alert {i}",
                severity=SeverityEnum.LOW,
                status=AlertStatusEnum.NEW,
                created_at=previous_start + timedelta(hours=i + 1),
            )
        )
    db_session.commit()

    response = client.get(
        "/api/v1/dashboard/summary",
        params={"as_of": reference.isoformat(), "period_days": 1},
    )

    assert response.status_code == 200
    assert response.json()["alert_change_pct"] == -50.0


def test_alert_trends_daily_counts_sum_to_total(client: TestClient) -> None:
    """Per-day trend counts over a range covering all seeded alerts sum to the seeded total."""
    as_of = (BASE_TIME + timedelta(days=1)).isoformat()

    response = client.get(
        "/api/v1/dashboard/alert-trends", params={"as_of": as_of, "days": 2}
    )

    assert response.status_code == 200
    body = response.json()
    items = body["items"]
    assert len(items) == 2
    assert items[0]["date"] == "2026-08-15"
    assert items[0]["count"] == 13
    assert items[1]["date"] == "2026-08-16"
    assert items[1]["count"] == 0
    assert sum(item["count"] for item in items) == 13


def test_severity_distribution_matches_seeded_counts(client: TestClient) -> None:
    """The severity breakdown matches the known seeded counts, including a zero-count severity."""
    response = client.get("/api/v1/dashboard/severity-distribution")

    assert response.status_code == 200
    body = response.json()
    counts = {item["severity"]: item["count"] for item in body["items"]}
    assert counts == {"low": 4, "medium": 4, "high": 3, "critical": 2}
    # All 4 severities appear even though none of them are zero here.
    assert set(counts.keys()) == {"low", "medium", "high", "critical"}


def test_recent_alerts_default_limit_and_ordering(client: TestClient) -> None:
    """Recent alerts default to 5 results ordered most-recently-created first."""
    response = client.get("/api/v1/dashboard/recent-alerts")

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 5
    assert [item["external_id"] for item in items] == [
        "ALERT-1007",
        "ALERT-1006",
        "ALERT-1005",
        "ALERT-1004",
        "ALERT-1003",
    ]


def test_recent_alerts_limit_is_respected(client: TestClient) -> None:
    """A smaller limit returns fewer, still-correctly-ordered results."""
    response = client.get("/api/v1/dashboard/recent-alerts", params={"limit": 3})

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 3
    assert [item["external_id"] for item in items] == [
        "ALERT-1007",
        "ALERT-1006",
        "ALERT-1005",
    ]
