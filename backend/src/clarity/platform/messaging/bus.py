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
    """Handler calls that returned without raising."""

    failed: int = 0
    """Handler calls that raised. Each one will be offered again."""

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
        """Offer what is available to the subscribed handlers.

        Returns once there is nothing deliverable left: either everything was
        taken, or what remains is blocked behind a failure that a later drain
        will retry.
        """
        ...

    def close(self) -> None:
        """Release the driver's resources. Draining afterwards is an error."""
        ...


__all__ = ["DeliveryReport", "EventBus", "Handler"]
