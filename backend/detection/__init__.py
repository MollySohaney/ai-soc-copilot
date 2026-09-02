"""Typed, safe detection-rule primitives."""

from backend.detection.dsl import (
    Condition,
    DetectionLogic,
    SequenceStage,
    parse_logic,
)

__all__ = ["Condition", "DetectionLogic", "SequenceStage", "parse_logic"]
