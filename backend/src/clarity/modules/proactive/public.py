"""Public facade for the proactive module."""

from __future__ import annotations

from typing import Any

from clarity.modules.proactive.domain.detectors import ProactiveAction, run_detectors

_history: list[dict[str, Any]] = []


def reset_proactive() -> None:
    _history.clear()


def evaluate_event(event: dict[str, Any]) -> list[dict[str, Any]]:
    """Run zero-contact detectors; return proactive actions as dicts."""
    if not isinstance(event, dict):
        raise ValueError("event must be a dict")
    actions = run_detectors(event)
    as_dicts = [a.to_dict() for a in actions]
    for item in as_dicts:
        _history.append({"event_type": event.get("type"), "action": item})
    return as_dicts


def list_actions(*, limit: int = 100) -> list[dict[str, Any]]:
    return list(_history[-limit:])


__all__ = [
    "ProactiveAction",
    "evaluate_event",
    "list_actions",
    "reset_proactive",
    "run_detectors",
]
