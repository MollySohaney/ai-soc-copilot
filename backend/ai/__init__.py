"""Purpose: Provide safe, provider-neutral AI assistance primitives."""

from backend.ai.provider import (
    AIProvider,
    AIProviderError,
    AIRequest,
    AIResponse,
    AIUsage,
    FakeAIProvider,
    UnavailableAIProvider,
    build_ai_provider,
)
from backend.ai.triage import AlertTriageOutput, CopilotOutput, ObservedFact, TriageValidationError, validate_copilot_output, validate_triage_output
from backend.ai.prompts import TRIAGE_SYSTEM_INSTRUCTION, build_triage_request

__all__ = [
    "AIProvider",
    "AIProviderError",
    "AIRequest",
    "AIResponse",
    "AIUsage",
    "FakeAIProvider",
    "UnavailableAIProvider",
    "build_ai_provider",
    "AlertTriageOutput",
    "CopilotOutput",
    "ObservedFact",
    "TriageValidationError",
    "validate_triage_output",
    "validate_copilot_output",
    "TRIAGE_SYSTEM_INSTRUCTION",
    "build_triage_request",
]
