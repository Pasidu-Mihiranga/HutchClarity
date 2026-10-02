"""In-process event bus driver for the ``demo`` profile (B03, ADR-0027).

One FIFO queue per (consumer group, subject) stands in for a Kafka partition
assigned to a consumer group. That is the whole trick: the ordering and
blocking behaviour a real partition gives is reproduced in a dict, so a test
that passes here means the same thing as a test that passes against Kafka.

Simulated: this driver keeps events in the process and loses them on restart.
It exists so a reviewer can run Clarity with no broker.
"""

from __future__ import annotations

import threading
from collections import defaultdict, deque
from dataclasses import dataclass, field

from clarity.platform.messaging.bus import DeliveryReport, Handler
from clarity.platform.messaging.envelope import Event, EventType


class BusClosed(RuntimeError):
    """The bus was used after ``close``."""


@dataclass
class _Group:
    """One consumer group: its handlers and its own copy of the stream."""

    handlers: dict[EventType, list[Handler]] = field(default_factory=lambda: defaultdict(list))
    #: subject -> events this group has not taken yet, oldest first.
    partitions: dict[str, deque[Event]] = field(default_factory=lambda: defaultdict(deque))

    def wants(self, event: Event) -> bool:
        return bool(self.handlers.get(event.type))


class InProcessEventBus:
    """An ``EventBus`` that dispatches inside this process."""

    def __init__(self) -> None:
        self._groups: dict[str, _Group] = {}
        self._lock = threading.RLock()
        #: (group, subject) -> the lock that owns draining that partition. In
        #: Kafka a partition is assigned to exactly one consumer in a group;
        #: this is that rule, so two threads draining at once cannot both take
        #: the same event or pop past each other.
        self._partitions: dict[tuple[str, str], threading.RLock] = {}
        self._closed = False

    # -- the EventBus port ----------------------------------------------- #

    def publish(self, event: Event) -> None:
        self._guard()
        # Validate at the producer, as the outbox does: a malformed payload must
        # fail where it was written, not in somebody else's consumer.
        event.payload()
        with self._lock:
            for group in self._groups.values():
                if group.wants(event):
                    group.partitions[event.subject].append(event)

    def subscribe(self, event_type: EventType, *, group: str, handler: Handler) -> None:
        self._guard()
        with self._lock:
            self._groups.setdefault(group, _Group()).handlers[event_type].append(handler)

    def drain(self) -> DeliveryReport:
        self._guard()
        delivered = failed = 0
        stalled: dict[str, int] = {}

        for name, group in self._snapshot_groups():
            blocked = 0
            for subject in self._subjects(group):
                # Blocking, not skipping: a caller that drains in order to read
                # what an event produced must not return before the thread that
                # owns the partition has finished producing it.
                with self._partition_lock(name, subject):
                    taken, broke = self._drain_partition(group, subject)
                delivered += taken
                if broke:
                    failed += 1
                    blocked += 1
            if blocked:
                stalled[name] = blocked

        return DeliveryReport(delivered=delivered, failed=failed, stalled=stalled)

    def close(self) -> None:
        with self._lock:
            self._groups.clear()
            self._partitions.clear()
            self._closed = True

    # -- inspection, for the relay and for tests -------------------------- #

    def pending(self, group: str) -> list[Event]:
        """Events this group has not taken, including any blocking one."""
        with self._lock:
            found = self._groups.get(group)
            if found is None:
                return []
            return [event for queue in found.partitions.values() for event in queue]

    @property
    def groups(self) -> list[str]:
        with self._lock:
            return sorted(self._groups)

    # -- internals -------------------------------------------------------- #

    def _drain_partition(self, group: _Group, subject: str) -> tuple[int, bool]:
        """Deliver this subject's queue head-first. Stops at the first failure.

        Returns (delivered, blocked). Stopping is the point: the head stays at
        the head, so a retry sees the same event and order is never broken by a
        failure.

        The caller holds this partition's lock. Handlers run outside the bus
        lock, so a handler that publishes cannot deadlock against it.
        """
        delivered = 0
        while True:
            with self._lock:
                queue = group.partitions.get(subject)
                if not queue:
                    group.partitions.pop(subject, None)
                    return delivered, False
                event = queue[0]

            try:
                for handler in group.handlers.get(event.type, []):
                    handler(event)
            except Exception:
                return delivered, True

            with self._lock:
                queue = group.partitions.get(subject)
                if queue and queue[0] is event:
                    queue.popleft()
            delivered += 1

    def _partition_lock(self, group: str, subject: str) -> threading.RLock:
        with self._lock:
            return self._partitions.setdefault((group, subject), threading.RLock())

    def _subjects(self, group: _Group) -> list[str]:
        with self._lock:
            return list(group.partitions)

    def _snapshot_groups(self) -> list[tuple[str, _Group]]:
        with self._lock:
            return list(self._groups.items())

    def _guard(self) -> None:
        if self._closed:
            raise BusClosed("this bus is closed")


__all__ = ["BusClosed", "InProcessEventBus"]
