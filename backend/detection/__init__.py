"""Typed, safe detection-rule primitives."""

from backend.detection.dsl import (
    Condition,
    DetectionLogic,
    SequenceStage,
    parse_logic,
)
from backend.detection.matcher import MatchExplanation, MatchResult, match_event
from backend.detection.threshold import ThresholdMatch, evaluate_threshold
from backend.detection.sequence import SequenceMatch, evaluate_sequence

__all__ = ["Condition", "DetectionLogic", "SequenceStage", "parse_logic", "MatchExplanation", "MatchResult", "match_event", "ThresholdMatch", "evaluate_threshold", "SequenceMatch", "evaluate_sequence"]
