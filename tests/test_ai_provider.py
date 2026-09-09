"""Purpose: Verify the provider boundary and deterministic fake behavior."""

import json

import pytest

from api.schemas.report import ReportDraftOutput
from backend.ai.provider import (
    COPILOT_PROMPT_MARKER,
    REPORT_PROMPT_MARKER,
    AIRequest,
    AIResponseError,
    AIUsage,
    FakeAIProvider,
    UnavailableAIProvider,
    build_ai_provider,
)
from backend.ai.triage import validate_copilot_output, validate_triage_output
from config.settings import AppConfig


def request() -> AIRequest:
    return AIRequest(
        system_instruction="You are an advisory analyst.",
        user_content="Evidence: event-1",
        model="test-model",
        max_output_tokens=100,
        timeout_seconds=2,
    )


def test_fake_provider_is_deterministic_and_normalizes_usage() -> None:
    """The fake provider returns repeatable content and metadata for tests."""
    provider = FakeAIProvider(
        content='{"summary":"deterministic"}',
        usage=AIUsage(input_tokens=10, output_tokens=4, total_tokens=14),
    )

    first = provider.complete(request())
    second = provider.complete(request())

    assert first.content == second.content == '{"summary":"deterministic"}'
    assert first.provider == "fake"
    assert first.model == "test-model"
    assert first.usage.total_tokens == 14
    assert provider.calls == 2


def test_fake_provider_can_return_malformed_content() -> None:
    """Malformed output is available as data for downstream validation tests."""
    response = FakeAIProvider(content="not-json").complete(request())

    assert response.content == "not-json"


def test_fake_provider_propagates_normalized_errors() -> None:
    """Configured provider failures retain safe classification and retryability."""
    error = AIResponseError("invalid_response", "Provider returned invalid content.", retryable=False)
    provider = FakeAIProvider(error=error)

    with pytest.raises(AIResponseError) as raised:
        provider.complete(request())

    assert raised.value.code == "invalid_response"
    assert raised.value.safe_message == "Provider returned invalid content."
    assert raised.value.retryable is False


def test_unavailable_provider_fails_closed() -> None:
    """Disabled AI does not silently produce an analysis or mutate application data."""
    provider = UnavailableAIProvider()

    with pytest.raises(Exception) as raised:
        provider.complete(request())

    assert getattr(raised.value, "code") == "ai_unavailable"


def test_provider_factory_is_disabled_by_default_and_supports_fake() -> None:
    """Configuration chooses the fake provider only when explicitly enabled."""
    assert isinstance(build_ai_provider(AppConfig()), UnavailableAIProvider)
    assert isinstance(build_ai_provider(AppConfig(ai_enabled=True, ai_provider="fake")), FakeAIProvider)
    assert isinstance(build_ai_provider(AppConfig(ai_enabled=True, ai_provider="unknown")), UnavailableAIProvider)


def _content(user_content: str) -> dict:
    """Complete a request with the given prompt and return the parsed output."""
    provider = FakeAIProvider()
    response = provider.complete(
        AIRequest(
            system_instruction="You are an advisory analyst.",
            user_content=user_content,
            model="test-model",
            max_output_tokens=100,
            timeout_seconds=2,
        )
    )
    return json.loads(response.content)


def test_fake_provider_returns_triage_shape_by_default() -> None:
    """An unmarked prompt still validates as alert triage."""
    output = _content('Evidence: {"evidence_id": "alert-5"}')
    assert validate_triage_output(output, {"alert-5"}).summary


def test_fake_provider_returns_copilot_shape_for_case_questions() -> None:
    """The case Q&A schema forbids triage fields, so the fake must answer in its own shape."""
    output = _content(f'{COPILOT_PROMPT_MARKER} What happened?\n{{"evidence_id": "case-4"}}')
    assert validate_copilot_output(output, {"case-4"}).answer
    assert "summary" not in output


def test_fake_provider_returns_report_shape_for_report_drafts() -> None:
    """The report schema forbids triage fields, so the fake must draft in its own shape."""
    output = _content(f'{REPORT_PROMPT_MARKER} Recommendations are advisory.\n{{"evidence_id": "case-4"}}')
    draft = ReportDraftOutput.model_validate(output)
    assert draft.executive_summary
    assert draft.evidence_refs == ["case-4"]


def test_fake_provider_cites_only_evidence_from_the_prompt() -> None:
    """Every shape cites an ID taken from the supplied context, never an invented one."""
    for prompt in (
        'Evidence: {"evidence_id": "event-9"}',
        f'{COPILOT_PROMPT_MARKER} Why?\n{{"evidence_id": "event-9"}}',
        f'{REPORT_PROMPT_MARKER}\n{{"evidence_id": "event-9"}}',
    ):
        assert _content(prompt)["evidence_refs"] == ["event-9"]


def test_fake_provider_placeholder_when_no_evidence_is_supplied() -> None:
    """A context with no evidence IDs yields a placeholder rather than a fabricated one."""
    assert _content("no evidence here")["evidence_refs"] == ["evidence-unavailable"]


def test_explicit_content_overrides_every_shape() -> None:
    """Tests that pin provider output are unaffected by prompt-shape detection."""
    provider = FakeAIProvider(content='{"pinned": true}')
    response = provider.complete(
        AIRequest(
            system_instruction="",
            user_content=f"{COPILOT_PROMPT_MARKER} anything",
            model="m",
            max_output_tokens=10,
            timeout_seconds=1,
        )
    )
    assert response.content == '{"pinned": true}'
