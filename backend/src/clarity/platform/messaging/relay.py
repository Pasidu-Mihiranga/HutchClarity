"""The outbox relay (B04, ADR-0014; plan 21 section 11.4).

Reads committed outbox rows, publishes them to the bus, and records that it
did. Those last two cannot be one atomic act: the bus and the database are
different systems. The relay therefore publishes **first** and records
**second**, so the failure it can have is a duplicate rather than a loss:

- dies before publishing  -> the row is still pending, publish next run
- dies after publishing, before recording -> the row is still pending, so it is
  published again and the consumer deduplicates it
- dies after recording -> nothing to do

The other order would lose events, which on ``action.completed`` means money
moved and no receipt was ever issued. One duplicate is recoverable; one loss is
not, so the relay always chooses the duplicate.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from clarity.kernel.common import utc_now
from clarity.platform.messaging.bus import EventBus
from clarity.platform.messaging.envelope import Event
from clarity.platform.messaging.outbox import OutboxRow, outbox_in
from clarity.platform.persistence import ConcurrentUpdate, UnitOfWork, UnitOfWorkFactory


@dataclass(frozen=True)
class RelayReport:
    """What one relay run did."""

    published: int = 0
    failed: int = 0
    errors: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_clear(self) -> bool:
        return self.failed == 0


class Relay:
    """Moves committed outbox rows onto the bus."""

    def __init__(
        self,
        *,
        open_unit: UnitOfWorkFactory,
        bus: EventBus,
        now: Callable[[], datetime] = utc_now,
    ) -> None:
        self._open_unit = open_unit
        self._bus = bus
        self._now = now

    def run_once(self) -> RelayReport:
        """Publish every pending row. Safe to call again after any failure."""
        published = 0
        errors: list[str] = []

        for row in self._pending():
            try:
                self._bus.publish(row.event)
            except Exception as error:
                errors.append(f"{row.event_id}: {error}")
                self._record_failure(row.event_id, str(error))
                continue
            # A crash here leaves the row pending, so the event is published
            # again on the next run. That is the duplicate the design accepts.
            self._mark_sent(row.event_id)
            published += 1

        return RelayReport(published=published, failed=len(errors), errors=tuple(errors))

    # -- reading and writing, each in its own unit of work ----------------- #

    def _pending(self) -> list[OutboxRow]:
        with self._open_unit() as unit:
            return outbox_in(unit).pending()

    def _mark_sent(self, event_id: str) -> None:
        with self._open_unit() as unit:
            outbox_in(unit).mark_sent(event_id, now=self._now())
            self._commit_unless_another_relay_won(unit)

    def _record_failure(self, event_id: str, error: str) -> None:
        with self._open_unit() as unit:
            outbox_in(unit).record_failure(event_id, error)
            self._commit_unless_another_relay_won(unit)

    @staticmethod
    def _commit_unless_another_relay_won(unit: UnitOfWork) -> None:
        """Commit, treating a conflict as "another relay already did this".

        Two relays may pick up the same pending row, because nothing claims a
        row before publishing. That is deliberate: claiming would leave a row
        stranded mid-claim when a relay dies, and the design would rather have a
        duplicate publish, which consumers deduplicate, than a stranded event
        that is never published at all.

        So a conflict here is not a fault. It means the other relay published the
        same event and recorded it first, and the outcome is exactly what this
        call wanted.
        """
        try:
            unit.commit()
        except ConcurrentUpdate:
            return

    def published_events(self) -> list[Event]:
        """Every event this relay has recorded as sent, in append order."""
        with self._open_unit() as unit:
            return [row.event for row in outbox_in(unit).all_rows() if not row.is_pending]


__all__ = ["Relay", "RelayReport"]
