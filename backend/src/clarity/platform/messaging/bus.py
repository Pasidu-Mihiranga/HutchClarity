"""The event bus port (B03, ADR-0014, ADR-0027; plan 21 section 11.4).

Modules do not publish to a broker and do not know which broker there is. They
hand an event to this port and the composition root decides whether it lands in
a process-local queue (``demo``) or in Kafka (``full``).

Three guarantees the port makes, and every driver is held to them by
``tests/contract/test_bus_parity.py``:

**Order per subject.** ``Event.subject`` is the ``subscriber_ref`` and the
partition key, so everything about one customer is delivered in the order it
was published. Across subjects there is no order, which is what lets the bus
scale out "by phone number" (deck S14).

**At least once.** A handler that raises leaves the event undelivered for that
consumer group, and the next drain offers it again. A consumer is therefore
idempotent, which is what makes a redelivered ``action.completed`` issue one
receipt rather than two. The ``processed_event`` record that enforces it, the
backoff and the dead-letter store are B04's work, not the bus's.

**Order survives failure.** A failed event blocks its own subject for its own
group and nothing else: later events for that subject wait behind it, other
subjects keep flowing, and other groups are unaffected. Skipping the failure
would deliver a ``receipt.issued`` whose ``action.completed`` never arrived.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from clarity.platform.messaging.envelope import Event, EventType

#: A consumer. Raising means "not processed": the bus will offer the event again.
Handler = Callable[[Event], None]


@dataclass(frozen=True)
class DeliveryReport:
    """What one drain did. Returned so a relay can log and a test can assert."""

    delivered: int = 0
    """Events taken by a group, counted once per event per group.

    Not handler calls: a group with two handlers for one type runs both and
    counts one, because the unit a group either takes or retries is the event.
    Two groups taking the same event is two.
    """

    failed: int = 0
    """Subjects left blocked by a raising handler, counted once per group.

    One event that fails for two groups is two; several events waiting behind
    one failure are still one, because one retry is what they are waiting for.
    """

    stalled: dict[str, int] = field(default_factory=dict)
    """group -> number of subjects blocked behind a failure."""

    @property
    def is_clear(self) -> bool:
        """Nothing failed and nothing is waiting behind a failure."""
        return self.failed == 0 and not self.stalled


class EventBus(Protocol):
    """Publish events, and subscribe consumer groups to them."""

    def publish(self, event: Event) -> None:
        """Hand an event to the bus.

        Called by the outbox relay after the unit of work committed, never
        inside it: an event for a state change that rolled back is a lie.
        """
        ...

    def subscribe(self, event_type: EventType, *, group: str, handler: Handler) -> None:
        """Register a consumer group's handler for one event type.

        Each group gets its own copy of every matching event and its own
        progress, so a slow or failing group cannot affect another.
        """
        ...

    def drain(self) -> DeliveryReport:
        """Offer what has arrived to the subscribed handlers.

        Returns once this driver has nothing more in hand: either it was taken,
        or it is blocked behind a failure that a later drain will retry.

        **How much has arrived is not part of the contract.** An in-process
        driver holds its queue in memory, so one drain after a publish delivers
        it. A networked driver fetches, and a fetch is a round trip: an event
        already published and durable may not be in hand yet, and that drain
        honestly reports nothing. The guarantee is that a later drain offers it
        (at-least-once, above), not that the first one does.

        A relay therefore drains on a schedule and never reads one quiet drain
        as "the backlog is empty". A test that needs everything delivered
        drains until quiet; ``tests/contract/test_bus_parity.py`` has the
        helper. The stronger in-process promise is asserted of that driver
        alone, in ``tests/unit/test_in_process_bus.py``.
        """
        ...

    def close(self) -> None:
        """Release the driver's resources. Draining afterwards is an error."""
        ...


__all__ = ["DeliveryReport", "EventBus", "Handler"]
