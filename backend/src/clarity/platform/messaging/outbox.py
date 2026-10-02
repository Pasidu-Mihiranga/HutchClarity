"""Transactional outbox (B04, ADR-0014; plan 21 section 11.4).

The rule this enforces: **never write to the database and publish to a broker
as two separate acts.** If the publish fails after the write, the world and the
event stream disagree; if the write fails after the publish, consumers act on
something that did not happen.

So an event is appended to the outbox *inside the unit of work that makes the
state change* (B02). Commit stores both or neither. A relay
(``clarity.platform.messaging.relay``) picks the committed rows up afterwards
and publishes them to the bus, retrying until they land.

A row therefore has one honest failure mode: the relay can publish and die
before recording that it did, so the row is published twice. That is why
delivery is at-least-once and consumers are idempotent
(``clarity.platform.messaging.consumers``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from clarity.kernel.common import utc_now
from clarity.platform.messaging.envelope import Event
from clarity.platform.persistence import Repository, UnitOfWork

#: Collection the outbox rows live in. One collection is one table in B05.
OUTBOX = "platform.outbox"


class OutboxStatus(StrEnum):
    PENDING = "pending"
    """Committed with its state change, not yet published."""

    SENT = "sent"
    """The bus accepted it. Kept, not deleted, so a relay restart is auditable."""


@dataclass
class OutboxRow:
    """One event waiting to be published, and what the relay has tried."""

    event: Event
    status: OutboxStatus = OutboxStatus.PENDING
    attempts: int = 0
    last_error: str | None = None
    appended_at: datetime = field(default_factory=utc_now)
    sent_at: datetime | None = None

    @property
    def event_id(self) -> str:
        return self.event.id

    @property
    def is_pending(self) -> bool:
        return self.status is OutboxStatus.PENDING


class Outbox:
    """Appends events to the unit of work that is making the state change."""

    def __init__(self, rows: Repository[str, OutboxRow]) -> None:
        self._rows = rows

    def append(self, event: Event) -> Event:
        """Record an event. It is published only if this unit of work commits.

        The payload is checked against its registered schema first
        (``clarity.contracts.events``), so a malformed event fails at the
        producer, inside its own transaction, never at a consumer.
        """
        event.payload()
        self._rows.put(event.id, OutboxRow(event=event))
        return event

    def pending(self) -> list[OutboxRow]:
        """Committed rows the relay has not published yet, in append order."""
        return [row for row in self._rows.values() if row.is_pending]

    def all_rows(self) -> list[OutboxRow]:
        return self._rows.values()

    def get(self, event_id: str) -> OutboxRow | None:
        return self._rows.get(event_id)

    def mark_sent(self, event_id: str, *, now: datetime | None = None) -> None:
        """Record that the bus accepted this event."""
        row = self._rows.get(event_id)
        if row is None:
            return
        row.status = OutboxStatus.SENT
        row.sent_at = now or utc_now()
        self._rows.put(event_id, row)

    def trace(self, correlation_id: str) -> list[Event]:
        """Every event from one request, in append order.

        Answers "what did this request actually cause", which is the question
        asked when a customer disputes an outcome.
        """
        return [
            row.event
            for row in self._rows.values()
            if row.event.correlation_id == correlation_id or row.event.id == correlation_id
        ]

    def record_failure(self, event_id: str, error: str) -> None:
        """Count a failed publish. The row stays pending, so it is retried."""
        row = self._rows.get(event_id)
        if row is None:
            return
        row.attempts += 1
        row.last_error = error
        self._rows.put(event_id, row)


def outbox_in(unit: UnitOfWork) -> Outbox:
    """The outbox for one unit of work.

    This is the whole seam: a module appends through the same unit of work it is
    writing its state with, so there is no way to publish an event for a change
    that rolled back.
    """
    return Outbox(unit.repository(OUTBOX))


__all__ = ["OUTBOX", "Outbox", "OutboxRow", "OutboxStatus", "outbox_in"]
