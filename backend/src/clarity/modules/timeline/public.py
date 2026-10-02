"""Public facade for the timeline module."""

from __future__ import annotations

from typing import Any

from clarity.kernel.common import Completeness, EventSource, utc_now

_SOURCES: tuple[str, ...] = tuple(s.value for s in EventSource)


def _completeness_for(events: list[Any] | None, *, present: bool) -> str:
    if not present:
        return Completeness.MISSING.value
    if events is None:
        return Completeness.MISSING.value
    if len(events) == 0:
        # Queried successfully but nothing in window — still complete.
        return Completeness.COMPLETE.value
    return Completeness.COMPLETE.value


def build_timeline(
    subscriber_ref: str,
    ports: dict[str, Any] | None = None,
    *,
    world: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an 8-source timeline structure from a world snapshot.

    ``ports`` / ``world`` are accepted as a dict snapshot for lite. Each of the
    eight EventSource keys is normalised into ``{events, completeness, note}``.
    """
    if not subscriber_ref or not subscriber_ref.strip():
        raise ValueError("subscriber_ref is required")

    snapshot = ports if ports is not None else world
    snapshot = snapshot or {}

    # Allow nested shapes: {payments: [...]} or {payments: {events: [...]}}.
    sources: dict[str, Any] = {}
    for name in _SOURCES:
        raw = snapshot.get(name)
        present = name in snapshot
        if isinstance(raw, dict) and "events" in raw:
            events = list(raw.get("events") or [])
            completeness = str(raw.get("completeness") or _completeness_for(events, present=True))
            note = raw.get("note")
        elif isinstance(raw, list):
            events = list(raw)
            completeness = _completeness_for(events, present=True)
            note = None
        elif raw is None and not present:
            events = []
            completeness = Completeness.MISSING.value
            note = "source not in snapshot"
        elif raw is None:
            events = []
            completeness = Completeness.COMPLETE.value
            note = None
        else:
            events = [raw]
            completeness = Completeness.PARTIAL.value
            note = "non-list source payload"

        sources[name] = {
            "events": events,
            "completeness": completeness,
            "note": note,
            "count": len(events),
        }

    complete = sum(1 for s in sources.values() if s["completeness"] == Completeness.COMPLETE.value)
    return {
        "subscriber_ref": subscriber_ref.strip(),
        "built_at": utc_now().isoformat(),
        "sources": sources,
        # Flat aliases for callers that expect the 8 keys at top level.
        **{name: sources[name] for name in _SOURCES},
        "completeness": {
            "complete_sources": complete,
            "total_sources": len(_SOURCES),
            "ratio": round(complete / len(_SOURCES), 3),
            "overall": (
                Completeness.COMPLETE.value
                if complete == len(_SOURCES)
                else Completeness.PARTIAL.value
                if complete > 0
                else Completeness.MISSING.value
            ),
        },
    }


__all__ = ["build_timeline"]
