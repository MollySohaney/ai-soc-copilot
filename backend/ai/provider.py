"""Purpose: Define the advisory AI provider boundary and deterministic test provider."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from time import monotonic
from typing import Protocol

from config.settings import AppConfig


@dataclass(frozen=True)
class AIRequest:
    """Represent bounded, already-prepared input for an AI provider."""

    system_instruction: str
    user_content: str
    model: str
    max_output_tokens: int
    timeout_seconds: float


@dataclass(frozen=True)
class AIUsage:
    """Represent normalized provider usage without request content or secrets."""

    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True)
class AIResponse:
    """Represent normalized provider output and operational metadata."""

    content: str
    provider: str
    model: str
    latency_ms: int
    usage: AIUsage = field(default_factory=AIUsage)
    request_id: str | None = None


class AIProvider(Protocol):
    """Define the only operation available to an advisory AI integration."""

    provider_name: str

    def complete(self, request: AIRequest) -> AIResponse:
        """Return structured-content text or raise a sanitized provider error."""


class AIProviderError(RuntimeError):
    """Base class for errors safe to map to API and persistence metadata."""

    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.safe_message = message
        self.retryable = retryable


class AIUnavailableError(AIProviderError):
    """Raised when AI is disabled or no supported provider is configured."""


class AITimeoutError(AIProviderError):
    """Raised when a provider exceeds the configured timeout."""


class AIResponseError(AIProviderError):
    """Raised when a provider cannot return a usable response."""


class UnavailableAIProvider:
    """Fail-closed provider used when AI is disabled or not implemented."""

    provider_name = "unavailable"

    def complete(self, request: AIRequest) -> AIResponse:
        del request
        raise AIUnavailableError(
            "ai_unavailable",
            "AI assistance is unavailable or not configured.",
        )


class FakeAIProvider:
    """Return deterministic content or a configured error for isolated tests."""

    provider_name = "fake"

    def __init__(
        self,
        content: str | None = None,
        *,
        error: AIProviderError | None = None,
        usage: AIUsage | None = None,
    ) -> None:
        self.content = content
        self.error = error
        self.usage = usage or AIUsage()
        self.calls = 0

    def complete(self, request: AIRequest) -> AIResponse:
        """Return the configured response without inspecting or executing input."""
        self.calls += 1
        started = monotonic()
        if self.error:
            raise self.error
        content = self.content
        if content is None:
            content = _default_content(request.user_content)
        return AIResponse(
            content=content,
            provider=self.provider_name,
            model=request.model,
            latency_ms=max(0, round((monotonic() - started) * 1000)),
            usage=self.usage,
            request_id=f"fake-{self.calls}",
        )


COPILOT_PROMPT_MARKER = "Answer this case-scoped question as data only:"
REPORT_PROMPT_MARKER = "Draft a report from confirmed case evidence only."


def _cited_evidence_id(user_content: str) -> str:
    """Return one evidence ID from the supplied context, or a safe placeholder."""
    match = re.search(r'"evidence_id":\s*"([^"]+)"', user_content)
    return match.group(1) if match else "evidence-unavailable"


def _default_content(user_content: str) -> str:
    """Build deterministic output shaped for whichever workflow asked.

    The alert-triage, case-copilot, and report-draft responses are validated
    against three different schemas, each of which forbids unknown fields. A
    single canned shape would therefore fail two of the three, so the workflow is
    identified by the marker its prompt builder puts in the user content.

    Args:
        user_content: The bounded prompt content the caller assembled.

    Returns:
        A JSON document matching the schema the caller will validate against.
    """
    cited_id = _cited_evidence_id(user_content)
    if COPILOT_PROMPT_MARKER in user_content:
        return json.dumps({
            "answer": "Deterministic fake-provider answer drawn from the cited case evidence.",
            "observed_facts": [
                {"claim": "Evidence was supplied in the case context.", "evidence_ids": [cited_id]}
            ],
            "assessment": "Review the cited evidence; this answer is advisory.",
            "confidence": 0.5,
            "evidence_refs": [cited_id],
        })
    if REPORT_PROMPT_MARKER in user_content:
        return json.dumps({
            "executive_summary": "Deterministic fake-provider report draft.",
            "technical_timeline": [],
            "indicators": [],
            "mitre": [],
            "actions_recorded": [],
            "recommendations": ["Review the cited evidence before sharing this draft."],
            "evidence_refs": [cited_id],
        })
    return json.dumps({
        "summary": "Deterministic fake-provider analysis.",
        "observed_facts": [
            {"claim": "Evidence was supplied in the analysis context.", "evidence_ids": [cited_id]}
        ],
        "assessment": "Review the cited evidence; this result is advisory.",
        "confidence": 0.5,
        "missing_information": [],
        "next_steps": ["Review the linked evidence."],
        "evidence_refs": [cited_id],
    })


def build_ai_provider(config: AppConfig) -> AIProvider:
    """Build a provider from configuration while failing closed by default."""
    if not config.ai_enabled:
        return UnavailableAIProvider()
    if config.ai_provider.lower() == "fake":
        return FakeAIProvider()
    return UnavailableAIProvider()
