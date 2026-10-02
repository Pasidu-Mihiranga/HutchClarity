"""Transactional outbox and in-process bus (plan §18.4).

The rule this enforces: **never write to the database and publish to a broker
as two separate acts.** If the publish fails after the write, the world and the
event stream disagree; if the write fails after the publish, consumers act on
something that did not happen. So events are appended to an outbox alongside
the state change, and a relay publishes them afterwards, retrying until they
land.

Consumers are at-least-once, so each one records the event ids it has already
processed and ignores repeats. That is what makes a redelivered
``action.completed`` issue one receipt rather than two.

**Prototype note.** The relay is in-process and the outbox is a list. Production
puts the outbox in PostgreSQL in the same transaction as the state change, with
Debezium or an app relay forwarding to Kafka (plan §18.4). The ordering and
idempotency guarantees modelled here are the ones that matter.
"""

from __future__ import annotations

import threading
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass

from clarity.platform.messaging.envelope import Event, EventType

Handler = Callable[[Event], None]


@dataclass
class _Delivery:
    event: Event
    attempts: int = 0
    delivered: bool = False
    dead_lettered: bool = False
    last_error: str | None = None


@dataclass
class ConsumerStats:
    received: int = 0
    duplicates: int = 0
    failures: int = 0


class Outbox:
    """Collects events produced during a state change, then publishes them."""

    def __init__(self, *, max_attempts: int = 3) -> None:
        self._pending: list[_Delivery] = []
        self._published: list[Event] = []
        self._dlq: list[_Delivery] = []
        self._handlers: dict[EventType, list[tuple[str, Handler]]] = defaultdict(list)
        self._processed: dict[str, set[str]] = defaultdict(set)
        self._stats: dict[str, ConsumerStats] = defaultdict(ConsumerStats)
        self._max_attempts = max_attempts
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ #
    # Producing
    # ------------------------------------------------------------------ #

    def append(self, event: Event) -> Event:
        """Record an event. Nothing is delivered until :meth:`relay` runs."""
        with self._lock:
            self._pending.append(_Delivery(event=event))
        return event

    def subscribe(self, event_type: EventType, name: str, handler: Handler) -> None:
        """Register a named consumer. The name is its idempotency scope."""
        self._handlers[event_type].append((name, handler))

    # ------------------------------------------------------------------ #
    # Relaying
    # ------------------------------------------------------------------ #

    def relay(self) -> int:
        """Deliver pending events in order. Returns how many were published.

        Per-subject ordering is preserved because the outbox is append-ordered
        and this drains it sequentially.
        """
        with self._lock:
            batch, self._pending = self._pending, []

        published = 0
        for delivery in batch:
            if self._deliver(delivery):
                published += 1
            else:
                with self._lock:
                    if delivery.dead_lettered:
                        self._dlq.append(delivery)
                    else:
                        self._pending.append(delivery)
        return published

    def _deliver(self, delivery: _Delivery) -> bool:
        event = delivery.event
        delivery.attempts += 1
        failed = False

        for name, handler in self._handlers.get(event.type, []):
            seen = self._processed[name]
            if event.id in seen:
                self._stats[name].duplicates += 1
                continue
            try:
                handler(event)
            except Exception as error:
                self._stats[name].failures += 1
                delivery.last_error = f"{name}: {error}"
                failed = True
                continue
            seen.add(event.id)
            self._stats[name].received += 1

        if failed:
            if delivery.attempts >= self._max_attempts:
                # Critical events must not disappear into a DLQ unnoticed.
                delivery.dead_lettered = True
            return False

        delivery.delivered = True
        with self._lock:
            self._published.append(event)
        return True

    # ------------------------------------------------------------------ #
    # Inspection
    # ------------------------------------------------------------------ #

    @property
    def published(self) -> list[Event]:
        return list(self._published)

    @property
    def pending(self) -> list[Event]:
        return [d.event for d in self._pending]

    @property
    def dead_letters(self) -> list[Event]:
        """Non-empty is an alert condition (plan §18.4)."""
        return [d.event for d in self._dlq]

    @property
    def undelivered_critical(self) -> list[Event]:
        """Critical events stuck or dead-lettered - pages a human."""
        return [d.event for d in (*self._pending, *self._dlq) if d.event.is_critical]

    def stats(self, consumer: str) -> ConsumerStats:
        return self._stats[consumer]

    def events_for(self, subject: str) -> list[Event]:
        """Everything published about one subscriber, in order."""
        return [e for e in self._published if e.subject == subject]

    def trace(self, correlation_id: str) -> list[Event]:
        """Every event from one request, for end-to-end tracing."""
        return [
            e
            for e in self._published
            if e.correlation_id == correlation_id or e.id == correlation_id
        ]
