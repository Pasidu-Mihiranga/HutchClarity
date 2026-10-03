"""Insights as a running read model (I01, #30).

Consumes the events the dashboards are built from, keeps the projection, and
can rebuild it from the log. The projection logic is all in `projections.py`
and is pure; this is the part that has a repository and a consumer group.

**Why the read model is stored rather than held in the process.** The context
this issue starts from is "dashboards read live objects", which means they read
whatever is in one process: a restart loses the numbers, a second replica
disagrees with the first, and nobody can ask what the figures were last week.
A stored projection fixes the first two. The third needs the log, which is what
`rebuild_from` is for.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from clarity.modules.insights.projections import Insights, apply, rebuild
from clarity.platform.messaging.envelope import Event
from clarity.platform.persistence import (
    MemoryStore,
    MemoryUnitOfWork,
    Repository,
    UnitOfWork,
    UnitOfWorkFactory,
)

#: One collection, one row. A read model is one value, not a table of them.
PROJECTIONS = "insights.projections"

#: The key the single projection row lives under.
CURRENT = "current"


class InsightsService:
    """Folds events into the stored read model, and serves the dashboards."""

    def __init__(self, *, open_unit: UnitOfWorkFactory | None = None) -> None:
        if open_unit is None:
            store = MemoryStore()

            def open_memory_unit() -> MemoryUnitOfWork:
                return MemoryUnitOfWork(store)

            open_unit = open_memory_unit
        self._open_unit = open_unit

    @staticmethod
    def _rows(unit: UnitOfWork) -> Repository[str, Insights]:
        return unit.repository(PROJECTIONS)

    def on_event(self, event: Event) -> None:
        """Consume one event. Registered for every type the dashboards use.

        Reads the projection, folds, writes it back, in one unit of work. The
        fold is idempotent by event id, so a redelivery is a no-op and the
        write is harmless (I7).
        """
        with self._open_unit() as unit:
            rows = self._rows(unit)
            state = rows.get(CURRENT) or Insights()
            apply(state, event)
            rows.put(CURRENT, state)
            unit.commit()

    def current(self) -> Insights:
        """The read model as it stands. Empty before the first event."""
        with self._open_unit() as unit:
            return self._rows(unit).get(CURRENT) or Insights()

    def rebuild_from(self, events: Sequence[Event]) -> Insights:
        """Rebuild the projection from a log and store the result.

        What acceptance 1 exercises, and what an operator runs after changing a
        projection: a read model is a cache of the log, so the log is the
        authority and this is how the cache is made to agree with it again.
        """
        state = rebuild(list(events))
        with self._open_unit() as unit:
            self._rows(unit).put(CURRENT, state)
            unit.commit()
        return state

    def dashboards(self) -> dict[str, Any]:
        return self.current().to_dict()


__all__ = ["CURRENT", "PROJECTIONS", "InsightsService"]
