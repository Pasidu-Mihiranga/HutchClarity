"""Public facade for the detection module."""

from __future__ import annotations

from typing import Any

from clarity.modules.detection.domain.models import Detection
from clarity.modules.detection.domain.registry import DETECTORS, run_all


def detect(timeline: dict[str, Any]) -> list[Detection]:
    """Run all cause detectors against a timeline dict."""
    return run_all(timeline)


def detections_to_dicts(detections: list[Detection]) -> list[dict[str, Any]]:
    return [d.to_dict() for d in detections]


__all__ = ["DETECTORS", "Detection", "detect", "detections_to_dicts", "run_all"]
