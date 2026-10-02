"""Public facade for the insights module."""

from __future__ import annotations

from typing import Any

from clarity.modules.insights.domain.projections import InsightProjections

_projections = InsightProjections()


def reset_insights() -> None:
    _projections.clear()


def ingest_event(event: dict[str, Any]) -> None:
    _projections.ingest(event)


def dashboard() -> dict[str, Any]:
    return _projections.dashboard()


__all__ = ["dashboard", "ingest_event", "reset_insights"]
