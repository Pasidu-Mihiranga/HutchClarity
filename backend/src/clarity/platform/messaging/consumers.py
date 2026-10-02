"""The consumer framework (B04, ADR-0014; plan 21 section 11.4).

Delivery is at-least-once, so every consumer needs the same four pieces of
bookkeeping. Writing them once here is what stops each module inventing its own
half of it:

**``processed_event``.** One row per (consumer group, event id). A redelivered
``action.completed`` finds its row and returns without acting, which is what
makes one action produce one receipt rather than two.

**Retry with backoff.** A handler that raises is tried again, not immediately
but after a growing delay, so a dependency that is briefly down is waited for
rather than hammered.

**A dead-letter store.** After the last attempt the event is set aside, so one
permanently broken event stops blocking everything queued behind it.

**An alert hook.** A dead letter is not a resolution, it is an unresolved
problem that a person has to look at. For the events in ``CRITICAL_EVENTS``
(money moved, or a customer was promised something) the hook is the only thing
standing between a silent DLQ row and a missing receipt, so it fires on every
dead letter and the registry refuses to dead-letter a critical event quietly.

The record of what was processed is written in a unit of work (B02), so a
consumer that commits its own state change can be given the same unit and have
both land together. Nothing here decides anything about a case; it is
bookkeeping around a handler.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from clarity.kernel.common import utc_now
from clarity.platform.messaging.bus import EventBus, Handler
from clarity.platform.messaging.correlation import correlated
from clarity.platform.messaging.envelope import CRITICAL_EVENTS, Event, EventType
from clarity.platform.persistence import (
    ConcurrentUpdate,
    Repository,
    UnitOfWork,
    UnitOfWorkFactory,
)

#: Collections the drivers use. Each one is a table in B05.
PROCESSED = "platform.processed_event"
ATTEMPTS = "platform.consumer_attempts"
DEAD_LETTERS = "platform.dead_letters"

#: Attempts before an event is set aside. The fourth delivery dead-letters it.
DEFAULT_MAX_ATTEMPTS = 3

#: First retry delay. Each further attempt doubles it.
DEFAULT_BACKOFF = timedelta(seconds=2)


class EventIsInBackoff(RuntimeError):
    """This event failed recently and its retry is not due yet.

    Raised so the bus leaves the event undelivered and offers it again later.
    It is flow control, not an error in the consumer.
    """


@dataclass
class ProcessedEvent:
    """Proof that one consumer group has already applied one event."""

    group: str
    event_id: str
    at: datetime

    @property
    def key(self) -> str:
        return f"{self.group}:{self.event_id}"


@dataclass
class AttemptRecord:
    """How often a group has failed on an event, and when to try again."""

    group: str
    event_id: str
    attempts: int = 0
    last_error: str | None = None
    next_attempt_at: datetime | None = None

    @property
    def key(self) -> str:
        return f"{self.group}:{self.event_id}"


@dataclass
class DeadLetter:
    """An event a consumer could not apply, set aside for a person."""

    event: Event
    group: str
    attempts: int
    last_error: str
    at: datetime
    is_critical: bool = False
    """True when the event moved money or promised a customer something."""

    @property
    def key(self) -> str:
        return f"{self.group}:{self.event.id}"


#: Called with every dead letter, so a person finds out.
AlertHook = Callable[[DeadLetter], None]


@dataclass
class ConsumerStats:
    received: int = 0
    duplicates: int = 0
    failures: int = 0
    dead_lettered: int = 0
    deferred: int = 0
    """Deliveries skipped because the retry was not due yet."""


class UnalertedDeadLetter(RuntimeError):
    """A consumer of a critical event was registered with no alert hook.

    Raised at registration, not when an event actually dies. A dead letter for
    ``action.completed`` means money moved and the customer has no receipt, so
    the wiring that would leave that undiscovered is refused while someone is
    still looking at it. Raising later would be worse than useless: the bus
    treats an exception from a consumer as a delivery failure, so the alert
    would be swallowed as a retry and the operator would be told nothing.
    """


class ConsumerRegistry:
    """Subscribes handlers to the bus with the bookkeeping wrapped around them."""

    def __init__(
        self,
        *,
        open_unit: UnitOfWorkFactory,
        bus: EventBus,
        now: Callable[[], datetime] = utc_now,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        backoff: timedelta = DEFAULT_BACKOFF,
        alert: AlertHook | None = None,
    ) -> None:
        self._open_unit = open_unit
        self._bus = bus
        self._now = now
        self._max_attempts = max_attempts
        self._backoff = backoff
        self._alert = alert
        self._stats: dict[str, ConsumerStats] = {}

    def register(self, event_type: EventType, *, group: str, handler: Handler) -> None:
        """Subscribe ``handler``, wrapped in deduplication, retry and alerting.

        Refuses a consumer of a critical event when no alert hook is configured:
        see ``UnalertedDeadLetter`` for why that is checked here and not later.
        """
        if event_type in CRITICAL_EVENTS and self._alert is None:
            raise UnalertedDeadLetter(
                f"{group} consumes {event_type.value}, which is a critical event, "
                "so ConsumerRegistry needs an alert hook: a dead letter here means "
                "money moved and nobody was told"
            )
        self._stats.setdefault(group, ConsumerStats())
        self._bus.subscribe(event_type, group=group, handler=self._wrap(group, handler))

    def stats(self, group: str) -> ConsumerStats:
        return self._stats.setdefault(group, ConsumerStats())

    def dead_letters(self) -> list[DeadLetter]:
        """Non-empty is an unresolved problem, not a cleared one."""
        with self._open_unit() as unit:
            return self._dead(unit).values()

    def has_processed(self, group: str, event_id: str) -> bool:
        with self._open_unit() as unit:
            return self._processed(unit).get(f"{group}:{event_id}") is not None

    # -- the wrapper ------------------------------------------------------- #

    def _wrap(self, group: str, handler: Handler) -> Handler:
        def consume(event: Event) -> None:
            stats = self.stats(group)

            if self.has_processed(group, event.id):
                # The relay published twice, or the bus redelivered. Either way
                # this group has already applied it.
                stats.duplicates += 1
                return

            attempt = self._attempt_for(group, event.id)
            if attempt.next_attempt_at is not None and self._now() < attempt.next_attempt_at:
                stats.deferred += 1
                raise EventIsInBackoff(
                    f"{group} retries {event.id} at {attempt.next_attempt_at.isoformat()}"
                )

            # The correlation id follows the event in, so anything the handler
            # logs or derives stays on the same trace.
            try:
                with correlated(event.correlation_id or event.id):
                    handler(event)
            except Exception as error:
                stats.failures += 1
                self._after_failure(group, event, attempt, error)
                return
            self._mark_processed(group, event.id)
            stats.received += 1

        return consume

    def _after_failure(
        self, group: str, event: Event, attempt: AttemptRecord, error: Exception
    ) -> None:
        """Count the failure, then either schedule a retry or dead-letter it."""
        attempt.attempts += 1
        attempt.last_error = f"{type(error).__name__}: {error}"
        exhausted = attempt.attempts >= self._max_attempts

        if exhausted:
            self._dead_letter(group, event, attempt)
            attempt.next_attempt_at = None
            self._save_attempt(attempt)
            # Returning normally retires the event: it is in the dead-letter
            # store, so leaving it on the bus would block everything behind it.
            return

        # Double the delay each time: 2s, 4s, 8s.
        delay = self._backoff * (2 ** (attempt.attempts - 1))
        attempt.next_attempt_at = self._now() + delay
        self._save_attempt(attempt)
        # Raising hands the event back to the bus, which will offer it again.
        raise error

    def _dead_letter(self, group: str, event: Event, attempt: AttemptRecord) -> None:
        letter = DeadLetter(
            event=event,
            group=group,
            attempts=attempt.attempts,
            last_error=attempt.last_error or "unknown",
            at=self._now(),
            is_critical=event.is_critical,
        )
        with self._open_unit() as unit:
            self._dead(unit).put(letter.key, letter)
            try:
                unit.commit()
            except ConcurrentUpdate:
                # Already dead-lettered by another worker; do not alert twice.
                return
        self.stats(group).dead_lettered += 1
        if self._alert is not None:
            self._alert(letter)

    # -- storage ----------------------------------------------------------- #

    def _attempt_for(self, group: str, event_id: str) -> AttemptRecord:
        with self._open_unit() as unit:
            found = self._attempts(unit).get(f"{group}:{event_id}")
        return found or AttemptRecord(group=group, event_id=event_id)

    def _save_attempt(self, attempt: AttemptRecord) -> None:
        with self._open_unit() as unit:
            self._attempts(unit).put(attempt.key, attempt)
            try:
                unit.commit()
            except ConcurrentUpdate:
                # Two workers failed on the same event at once. Either one's
                # schedule is a valid next retry time, so the loser stands down.
                return

    def _mark_processed(self, group: str, event_id: str) -> None:
        with self._open_unit() as unit:
            record = ProcessedEvent(group=group, event_id=event_id, at=self._now())
            self._processed(unit).put(record.key, record)
            try:
                unit.commit()
            except ConcurrentUpdate:
                # Another worker in this group recorded the same event first,
                # which is the state this call wanted. The handler ran twice,
                # which is why a handler must be idempotent.
                return

    @staticmethod
    def _processed(unit: UnitOfWork) -> Repository[str, ProcessedEvent]:
        return unit.repository(PROCESSED)

    @staticmethod
    def _attempts(unit: UnitOfWork) -> Repository[str, AttemptRecord]:
        return unit.repository(ATTEMPTS)

    @staticmethod
    def _dead(unit: UnitOfWork) -> Repository[str, DeadLetter]:
        return unit.repository(DEAD_LETTERS)


@dataclass
class CollectingAlertHook:
    """An alert hook that records instead of raising. For tests and the demo."""

    raised: list[DeadLetter] = field(default_factory=list)

    def __call__(self, letter: DeadLetter) -> None:
        self.raised.append(letter)

    @property
    def critical(self) -> list[DeadLetter]:
        return [letter for letter in self.raised if letter.is_critical]


__all__ = [
    "ATTEMPTS",
    "DEAD_LETTERS",
    "DEFAULT_BACKOFF",
    "DEFAULT_MAX_ATTEMPTS",
    "PROCESSED",
    "AlertHook",
    "AttemptRecord",
    "CollectingAlertHook",
    "ConsumerRegistry",
    "ConsumerStats",
    "DeadLetter",
    "EventIsInBackoff",
    "ProcessedEvent",
    "UnalertedDeadLetter",
]
