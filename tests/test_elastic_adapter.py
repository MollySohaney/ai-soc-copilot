"""Purpose: Verify Elastic ingestion adapter behavior without a live cluster."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from elastic_transport import ApiResponseMeta, ConnectionTimeout, NodeConfig
from elasticsearch import AuthenticationException

from backend.ingestion import IngestionCheckpointState, IngestionFetchRequest
from backend.ingestion.adapters.elastic import ElasticIngestionAdapter
from backend.ingestion.errors import (
    IngestionAuthenticationError,
    IngestionConfigurationError,
    IngestionTimeoutError,
)
from config.settings import AppConfig


BASE_TIME = datetime(2026, 8, 15, 2, 0, tzinfo=timezone.utc)


class FakeElasticClient:
    """Capture Elastic client calls and return queued responses or errors."""

    def __init__(self, *, info_response: dict[str, Any] | Exception | None = None) -> None:
        self.info_response = info_response or {"cluster_name": "test-cluster"}
        self.search_responses: list[dict[str, Any] | Exception] = []
        self.search_calls: list[dict[str, Any]] = []

    def info(self) -> dict[str, Any]:
        if isinstance(self.info_response, Exception):
            raise self.info_response
        return self.info_response

    def search(self, **kwargs: Any) -> dict[str, Any]:
        self.search_calls.append(kwargs)
        response = self.search_responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _config() -> AppConfig:
    return AppConfig(
        elastic_url="https://elastic.example.test:9200",
        elastic_index_pattern="logs-security-*",
        elastic_source_name="elastic-test",
        elastic_api_key="secret-api-key",
        elastic_request_timeout_seconds=7,
    )


def _request(
    *,
    limit: int = 2,
    checkpoint: IngestionCheckpointState | None = None,
) -> IngestionFetchRequest:
    return IngestionFetchRequest(
        start_time=BASE_TIME,
        end_time=BASE_TIME + timedelta(hours=1),
        limit=limit,
        checkpoint=checkpoint,
    )


def _hit(record_id: str, minute: int) -> dict[str, Any]:
    timestamp = BASE_TIME + timedelta(minutes=minute)
    timestamp_text = timestamp.isoformat().replace("+00:00", "Z")
    return {
        "_index": "logs-security-2026.08.15",
        "_id": record_id,
        "_score": None,
        "_source": {
            "@timestamp": timestamp_text,
            "event": {"category": "authentication"},
            "message": f"record {record_id}",
        },
        "sort": [timestamp_text, minute],
    }


def _auth_error() -> AuthenticationException:
    node = NodeConfig(scheme="https", host="elastic.example.test", port=9200)
    meta = ApiResponseMeta(status=401, http_version="1.1", headers={}, duration=0.01, node=node)
    return AuthenticationException("unauthorized", meta=meta, body={"error": "unauthorized"})


def test_elastic_adapter_requires_url_without_injected_client() -> None:
    """Elastic config must include a non-secret URL when constructing a real client."""
    with pytest.raises(IngestionConfigurationError, match="ELASTIC_URL"):
        ElasticIngestionAdapter(AppConfig(elastic_url=None))


def test_elastic_connection_success_is_sanitized() -> None:
    """Connection test returns useful metadata without exposing credentials."""
    health = ElasticIngestionAdapter(_config(), client=FakeElasticClient()).test_connection()

    assert health.ok is True
    assert health.provider == "elastic"
    assert health.source_name == "elastic-test"
    assert health.details == {"cluster_name": "test-cluster"}
    assert "secret" not in health.model_dump_json()


def test_elastic_connection_auth_failure_is_sanitized() -> None:
    """Authentication errors become sanitized health failures."""
    health = ElasticIngestionAdapter(
        _config(), client=FakeElasticClient(info_response=_auth_error())
    ).test_connection()

    assert health.ok is False
    assert health.message == "Elastic authentication or authorization failed."
    assert "unauthorized" not in health.model_dump_json()


def test_elastic_fetch_success_maps_hits_to_source_records() -> None:
    """Successful searches produce provider-neutral source records and checkpoints."""
    client = FakeElasticClient()
    client.search_responses.append({"hits": {"hits": [_hit("rec-1", 1), _hit("rec-2", 2)]}})
    page = ElasticIngestionAdapter(_config(), client=client).fetch_records(_request(limit=2))

    assert [record.record_id for record in page.records] == ["rec-1", "rec-2"]
    assert page.records[0].provider == "elastic"
    assert page.records[0].source_name == "elastic-test"
    assert page.records[0].source_index == "logs-security-2026.08.15"
    assert page.records[0].payload["message"] == "record rec-1"
    assert page.next_checkpoint is not None
    assert page.next_checkpoint.values == {"search_after": ["2026-08-15T02:02:00Z", 2]}
    assert page.has_more is True

    call = client.search_calls[0]
    assert call["index"] == "logs-security-*"
    assert call["size"] == 2
    assert call["track_total_hits"] is False
    assert call["timeout"] == "7s"
    assert call["search_after"] is None
    assert call["query"]["range"]["@timestamp"] == {
        "gte": BASE_TIME.isoformat(),
        "lt": (BASE_TIME + timedelta(hours=1)).isoformat(),
    }


def test_elastic_fetch_empty_data_returns_empty_page() -> None:
    """Empty searches return no records and no checkpoint advancement."""
    client = FakeElasticClient()
    client.search_responses.append({"hits": {"hits": []}})
    page = ElasticIngestionAdapter(_config(), client=client).fetch_records(_request(limit=10))

    assert page.records == []
    assert page.next_checkpoint is None
    assert page.has_more is False


def test_elastic_fetch_uses_checkpoint_search_after() -> None:
    """Checkpoint values are passed through as Elastic search_after values."""
    checkpoint = IngestionCheckpointState(
        provider="elastic",
        source_name="elastic-test",
        values={"search_after": ["2026-08-15T02:02:00Z", 2]},
    )
    client = FakeElasticClient()
    client.search_responses.append({"hits": {"hits": [_hit("rec-3", 3)]}})

    ElasticIngestionAdapter(_config(), client=client).fetch_records(
        _request(limit=2, checkpoint=checkpoint)
    )

    assert client.search_calls[0]["search_after"] == ["2026-08-15T02:02:00Z", 2]


def test_elastic_fetch_auth_failure_raises_mapped_error() -> None:
    """Search auth failures become provider-neutral auth errors."""
    client = FakeElasticClient()
    client.search_responses.append(_auth_error())

    with pytest.raises(IngestionAuthenticationError, match="authentication"):
        ElasticIngestionAdapter(_config(), client=client).fetch_records(_request())


def test_elastic_fetch_timeout_raises_mapped_error() -> None:
    """Search timeouts become provider-neutral timeout errors."""
    client = FakeElasticClient()
    client.search_responses.append(ConnectionTimeout("timed out"))

    with pytest.raises(IngestionTimeoutError, match="timed out"):
        ElasticIngestionAdapter(_config(), client=client).fetch_records(_request())
