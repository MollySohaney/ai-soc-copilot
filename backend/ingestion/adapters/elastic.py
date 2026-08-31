"""Purpose: Ingest bounded telemetry pages from Elasticsearch."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from elastic_transport import ApiError, ConnectionError, ConnectionTimeout
from elasticsearch import AuthenticationException, AuthorizationException, Elasticsearch

from backend.ingestion.dto import (
    AdapterHealth,
    IngestionCheckpointState,
    IngestionFetchRequest,
    IngestionPage,
    SourceRecord,
)
from backend.ingestion.errors import (
    IngestionAdapterError,
    IngestionAuthenticationError,
    IngestionConfigurationError,
    IngestionConnectionError,
    IngestionTimeoutError,
)
from config.settings import AppConfig


class ElasticIngestionAdapter:
    """Fetch bounded, checkpointed telemetry pages from Elasticsearch."""

    def __init__(self, config: AppConfig, client: Any | None = None) -> None:
        """Initialize the adapter from environment-driven application config."""
        self._config = config
        self._client = client or self._build_client(config)

    @property
    def provider(self) -> str:
        """Return the Elastic provider identifier."""
        return "elastic"

    @property
    def source_name(self) -> str:
        """Return the configured Elastic source name."""
        return self._config.elastic_source_name

    def test_connection(self) -> AdapterHealth:
        """Check cluster connectivity and return a sanitized result."""
        try:
            info = self._client.info()
        except IngestionAdapterError as error:
            raise error
        except Exception as error:  # noqa: BLE001
            mapped = _map_elastic_error(error)
            return AdapterHealth(
                provider=self.provider,
                source_name=self.source_name,
                ok=False,
                message=str(mapped),
            )

        cluster_name = _response_value(info, "cluster_name")
        return AdapterHealth(
            provider=self.provider,
            source_name=self.source_name,
            ok=True,
            message="Elastic connection succeeded.",
            details={"cluster_name": cluster_name} if cluster_name else {},
        )

    def fetch_records(self, request: IngestionFetchRequest) -> IngestionPage:
        """Fetch one deterministic Elastic result page for a bounded time window."""
        search_after = None
        if request.checkpoint is not None:
            search_after = request.checkpoint.values.get("search_after")

        try:
            response = self._client.search(
                index=self._config.elastic_index_pattern,
                query={
                    "range": {
                        "@timestamp": {
                            "gte": request.start_time.isoformat(),
                            "lt": request.end_time.isoformat(),
                        }
                    }
                },
                size=request.limit,
                sort=[
                    {"@timestamp": {"order": "asc"}},
                    {"_shard_doc": {"order": "asc"}},
                ],
                search_after=search_after,
                track_total_hits=False,
                timeout=f"{self._config.elastic_request_timeout_seconds}s",
            )
        except Exception as error:  # noqa: BLE001
            raise _map_elastic_error(error) from error

        hits = list(_response_value(response, "hits", "hits", default=[]))
        records = [self._source_record_from_hit(hit) for hit in hits]
        next_checkpoint = None
        if hits:
            next_checkpoint = IngestionCheckpointState(
                provider=self.provider,
                source_name=self.source_name,
                values={"search_after": hits[-1].get("sort")},
            )

        return IngestionPage(
            records=records,
            next_checkpoint=next_checkpoint,
            has_more=len(records) == request.limit,
        )

    def _source_record_from_hit(self, hit: dict[str, Any]) -> SourceRecord:
        payload = hit.get("_source") or {}
        timestamp = _parse_timestamp(payload.get("@timestamp") or _first_sort_value(hit))
        record_id = str(hit.get("_id") or "")
        if not record_id:
            raise IngestionAdapterError("Elastic hit is missing _id.")

        return SourceRecord(
            provider=self.provider,
            source_name=self.source_name,
            record_id=record_id,
            timestamp=timestamp,
            payload=payload,
            source_index=hit.get("_index"),
            cursor=hit.get("sort"),
            metadata={"elastic_score": hit.get("_score")},
        )

    def _build_client(self, config: AppConfig) -> Elasticsearch:
        if not config.elastic_url:
            raise IngestionConfigurationError("ELASTIC_URL is required for Elastic ingestion.")

        kwargs: dict[str, Any] = {
            "hosts": [config.elastic_url],
            "request_timeout": config.elastic_request_timeout_seconds,
            "verify_certs": config.elastic_verify_certs,
        }
        if config.elastic_api_key:
            kwargs["api_key"] = config.elastic_api_key
        elif config.elastic_username and config.elastic_password:
            kwargs["basic_auth"] = (config.elastic_username, config.elastic_password)

        return Elasticsearch(**kwargs)


def _map_elastic_error(error: Exception) -> IngestionAdapterError:
    if isinstance(error, (AuthenticationException, AuthorizationException)):
        return IngestionAuthenticationError("Elastic authentication or authorization failed.")
    if isinstance(error, ConnectionTimeout):
        return IngestionTimeoutError("Elastic request timed out.")
    if isinstance(error, ConnectionError):
        return IngestionConnectionError("Elastic connection failed.")
    if isinstance(error, ApiError):
        if getattr(error, "status_code", None) in {401, 403}:
            return IngestionAuthenticationError("Elastic authentication or authorization failed.")
        return IngestionAdapterError(f"Elastic API request failed with status {error.status_code}.")
    return IngestionAdapterError("Elastic request failed.")


def _response_value(response: Any, *keys: str, default: Any = None) -> Any:
    value = response
    for key in keys:
        if isinstance(value, dict):
            value = value.get(key, default)
            continue
        value = getattr(value, key, default)
    return value


def _first_sort_value(hit: dict[str, Any]) -> Any:
    sort_values = hit.get("sort") or []
    return sort_values[0] if sort_values else None


def _parse_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    raise IngestionAdapterError("Elastic hit is missing @timestamp.")
