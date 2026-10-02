"""Event-driven counter projections for insights dashboards."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from clarity.kernel.common import utc_now


@dataclass
class InsightProjections:
    event_counts: Counter[str] = field(default_factory=Counter)
    outcomes: Counter[str] = field(default_factory=Counter)
    causes: Counter[str] = field(default_factory=Counter)
    handoffs: int = 0
    auto_fixes: int = 0
    by_channel: Counter[str] = field(default_factory=Counter)
    ai_stops: Counter[str] = field(default_factory=Counter)
    updated_at: str | None = None

    def ingest(self, event: dict[str, Any]) -> None:
        et = str(event.get("type") or event.get("event_type") or "unknown")
        self.event_counts[et] += 1
        data = event.get("data") if isinstance(event.get("data"), dict) else event
        outcome = data.get("outcome")
        if outcome:
            self.outcomes[str(outcome).upper()] += 1
            if str(outcome).upper() in {"HANDOFF", "STAFF_APPROVAL", "FOUR_EYES"}:
                self.handoffs += 1
            if str(outcome).upper() in {"AUTO_FIX", "ONE_TAP_FIX"}:
                self.auto_fixes += 1
        cause = data.get("cause") or data.get("top_cause")
        if cause:
            self.causes[str(cause)] += 1
        channel = data.get("channel")
        if channel:
            self.by_channel[str(channel)] += 1
        stop = data.get("ai_stop_reason")
        if stop:
            self.ai_stops[str(stop)] += 1
        self.updated_at = utc_now().isoformat()

    def dashboard(self) -> dict[str, Any]:
        top_causes = self.causes.most_common(10)
        top_outcomes = self.outcomes.most_common(10)
        return {
            "updated_at": self.updated_at,
            "event_counts": dict(self.event_counts),
            "outcomes": dict(top_outcomes),
            "top_causes": [{"cause": c, "count": n} for c, n in top_causes],
            "handoffs": self.handoffs,
            "auto_fixes": self.auto_fixes,
            "by_channel": dict(self.by_channel),
            "where_ai_stops": dict(self.ai_stops.most_common(10)),
            "funnel": {
                "events": sum(self.event_counts.values()),
                "decisions": sum(self.outcomes.values()),
                "auto_fixes": self.auto_fixes,
                "handoffs": self.handoffs,
            },
        }

    def clear(self) -> None:
        self.event_counts.clear()
        self.outcomes.clear()
        self.causes.clear()
        self.by_channel.clear()
        self.ai_stops.clear()
        self.handoffs = 0
        self.auto_fixes = 0
        self.updated_at = None
