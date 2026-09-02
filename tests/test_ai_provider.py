"""Purpose: Verify the provider boundary and deterministic fake behavior."""

import pytest

from backend.ai.provider import (
    AIRequest,
    AIResponseError,
    AIUsage,
    FakeAIProvider,
    UnavailableAIProvider,
    build_ai_provider,
)
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
