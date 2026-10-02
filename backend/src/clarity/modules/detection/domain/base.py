"""Detector protocol for rule_id@version plugins."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from clarity.modules.detection.domain.models import Detection


@runtime_checkable
class Detector(Protocol):
    rule_id: str
    version: str

    def evaluate(self, timeline: dict[str, Any]) -> Detection | None: ...
