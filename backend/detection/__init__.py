"""Typed, safe detection-rule primitives."""

from backend.detection.dsl import (
    Condition,
    DetectionLogic,
    SequenceStage,
    parse_logic,
)
from backend.detection.matcher import MatchExplanation, MatchResult, match_event

__all__ = ["Condition", "DetectionLogic", "SequenceStage", "parse_logic", "MatchExplanation", "MatchResult", "match_event"]
