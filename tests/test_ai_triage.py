"""Purpose: Verify safe parsing and evidence citation validation for triage."""

import json

import pytest

from backend.ai.provider import FakeAIProvider, AIRequest
from backend.ai.triage import TriageValidationError, validate_triage_output


VALID_IDS = {"alert-1", "event-1", "rule-snapshot-1"}


def valid_payload() -> dict:
    return {
        "schema_version": "v1",
        "summary": "Suspicious authentication activity was observed.",
        "observed_facts": [{"claim": "A login event was recorded.", "evidence_ids": ["event-1"]}],
        "assessment": "The activity may indicate account compromise.",
        "confidence": 0.8,
        "missing_information": ["Confirm whether the source IP is authorized."],
        "next_steps": ["Review the linked authentication events."],
        "evidence_refs": ["alert-1", "event-1"],
    }


def test_validate_triage_output_accepts_valid_citations() -> None:
    """Valid structured output and all supplied evidence IDs are accepted."""
    result = validate_triage_output(valid_payload(), VALID_IDS)

    assert result.observed_facts[0].evidence_ids == ["event-1"]
    assert result.confidence == 0.8


@pytest.mark.parametrize("raw", ["not-json", "[]", '{"summary":"missing fields"}'])
def test_validate_triage_output_rejects_malformed_schema(raw: str) -> None:
    """Malformed JSON and schema violations produce one safe validation error."""
    with pytest.raises(TriageValidationError, match="triage schema"):
        validate_triage_output(raw, VALID_IDS)


def test_validate_triage_output_rejects_hallucinated_evidence_id() -> None:
    """A citation not present in the current context cannot be accepted."""
    payload = valid_payload()
    payload["evidence_refs"] = ["event-does-not-exist"]

    with pytest.raises(TriageValidationError, match="outside the supplied context"):
        validate_triage_output(payload, VALID_IDS)


def test_validate_triage_output_rejects_duplicate_citations() -> None:
    """Duplicate citations are surfaced as malformed output."""
    payload = valid_payload()
    payload["evidence_refs"] = ["event-1", "event-1"]

    with pytest.raises(TriageValidationError, match="duplicates"):
        validate_triage_output(payload, VALID_IDS)


def test_fake_provider_malformed_output_is_rejected() -> None:
    """Fake provider fixtures exercise parser behavior without a real API."""
    provider = FakeAIProvider(content=json.dumps(valid_payload()).replace("event-1", "event-hallucinated"))
    request = AIRequest("advisory", "evidence", "fake-model", 100, 1)

    with pytest.raises(TriageValidationError):
        validate_triage_output(provider.complete(request).content, VALID_IDS)
