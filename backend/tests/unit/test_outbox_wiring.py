"""Outbox wiring, relay and consumer framework (issue #12, B04; ADR-0014).

The three failures this suite pins are the ones that cost money rather than
uptime: an event published for a change that never happened, an event lost
because the relay died at the wrong moment, and an event that fails forever
without anyone being told.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from itertools import pairwise

import pytest

from clarity.contracts.events import DomainEventType
from clarity.platform.messaging.bus import EventBus
from clarity.platform.messaging.consumers import (
    CollectingAlertHook,
    ConsumerRegistry,
    UnalertedDeadLetter,
)
from clarity.platform.messaging.correlation import current_correlation_id
from clarity.platform.messaging.drivers.in_process import InProcessEventBus
from clarity.platform.messaging.envelope import Event
from clarity.platform.messaging.outbox import OutboxStatus, outbox_in
from clarity.platform.messaging.relay import Relay
from clarity.platform.persistence import MemoryStore, MemoryUnitOfWork, UnitOfWork

from ..support.events import SAMPLES

DILANI = "sub_dilani"
CASE_CREATED = DomainEventType.CASE_CREATED
ACTION_COMPLETED = DomainEventType.ACTION_COMPLETED
CASES = "case.records"

START = datetime(2027, 9, 14, 14, 6, tzinfo=UTC)


def an_event(kind: DomainEventType = CASE_CREATED, subject: str = DILANI) -> Event:
    return Event.of(SAMPLES[kind], subject=subject)


class FakeClock:
    """A clock the test moves, so backoff is tested without sleeping."""

    def __init__(self, at: datetime = START) -> None:
        self.at = at

    def __call__(self) -> datetime:
        return self.at

    def advance(self, by: timedelta) -> None:
        self.at += by


@pytest.fixture
def store() -> MemoryStore:
    return MemoryStore()


@pytest.fixture
def open_unit(store: MemoryStore) -> Callable[[], UnitOfWork]:
    return lambda: MemoryUnitOfWork(store)


@pytest.fixture
def bus() -> Iterator[EventBus]:
    made = InProcessEventBus()
    try:
        yield made
    finally:
        made.close()


# -- acceptance 1: a rolled-back change publishes nothing ----------------- #


def test_a_rolled_back_unit_of_work_publishes_no_event(
    open_unit: Callable[[], UnitOfWork], bus: EventBus
) -> None:
    seen: list[str] = []
    bus.subscribe(CASE_CREATED, group="timeline", handler=lambda e: seen.append(e.id))
    relay = Relay(open_unit=open_unit, bus=bus)

    # A state change and its event, in one unit of work, abandoned.
    with open_unit() as unit:
        unit.repository(CASES).put("CASE-1", {"case_id": "CASE-1"})
        outbox_in(unit).append(an_event())
        unit.rollback()

    assert relay.run_once().published == 0
    bus.drain()
    assert seen == []

    # And the state change is gone too: both or neither.
    with open_unit() as unit:
        assert unit.repository(CASES).get("CASE-1") is None


def test_a_committed_change_publishes_its_event(
    open_unit: Callable[[], UnitOfWork], bus: EventBus
) -> None:
    seen: list[str] = []
    bus.subscribe(CASE_CREATED, group="timeline", handler=lambda e: seen.append(e.id))
    relay = Relay(open_unit=open_unit, bus=bus)

    with open_unit() as unit:
        unit.repository(CASES).put("CASE-2", {"case_id": "CASE-2"})
        event = outbox_in(unit).append(an_event())
        unit.commit()

    assert relay.run_once().published == 1
    bus.drain()
    assert seen == [event.id]


def test_appending_publishes_nothing_until_the_relay_runs(
    open_unit: Callable[[], UnitOfWork], bus: EventBus
) -> None:
    """The whole point of an outbox: the write happens first."""
    seen: list[str] = []
    bus.subscribe(CASE_CREATED, group="timeline", handler=lambda e: seen.append(e.id))

    with open_unit() as unit:
        outbox_in(unit).append(an_event())
        unit.commit()

    bus.drain()
    assert seen == [], "nothing reaches the bus without the relay"
    with open_unit() as unit:
        assert len(outbox_in(unit).pending()) == 1


# -- acceptance 2: the relay dies between publishing and recording -------- #


class CrashesAfterPublishing:
    """A bus that accepts the event and then kills the relay.

    This is the one interleaving the design cannot make atomic, so it is the one
    worth a test: the event is really on the bus, and the outbox row still says
    pending.
    """

    def __init__(self, inner: EventBus) -> None:
        self._inner = inner
        self.armed = True

    def publish(self, event: Event) -> None:
        self._inner.publish(event)
        if self.armed:
            self.armed = False
            raise KeyboardInterrupt("the relay process was killed")

    def subscribe(self, event_type: DomainEventType, *, group: str, handler: object) -> None:
        raise NotImplementedError

    def drain(self) -> object:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError


def test_a_relay_killed_before_recording_redelivers_and_applies_once(
    open_unit: Callable[[], UnitOfWork], bus: EventBus
) -> None:
    applied: list[str] = []
    clock = FakeClock()
    consumers = ConsumerRegistry(
        open_unit=open_unit, bus=bus, now=clock, alert=CollectingAlertHook()
    )
    consumers.register(ACTION_COMPLETED, group="receipts", handler=lambda e: applied.append(e.id))

    with open_unit() as unit:
        event = outbox_in(unit).append(an_event(ACTION_COMPLETED))
        unit.commit()

    # The relay publishes, then dies before it can mark the row sent.
    crashing = CrashesAfterPublishing(bus)
    with pytest.raises(KeyboardInterrupt):
        Relay(open_unit=open_unit, bus=crashing, now=clock).run_once()

    with open_unit() as unit:
        row = outbox_in(unit).get(event.id)
        assert row is not None
        assert row.status is OutboxStatus.PENDING, "the row must survive the crash"

    # It restarts and publishes the same event again: the row was never cleared.
    assert Relay(open_unit=open_unit, bus=bus, now=clock).run_once().published == 1
    bus.drain()

    # Delivered twice, applied once. That is what processed_event is for.
    assert applied == [event.id]
    assert consumers.stats("receipts").received == 1
    assert consumers.stats("receipts").duplicates == 1

    with open_unit() as unit:
        row = outbox_in(unit).get(event.id)
        assert row is not None
        assert row.status is OutboxStatus.SENT


def test_a_redelivered_event_is_applied_once(
    open_unit: Callable[[], UnitOfWork], bus: EventBus
) -> None:
    """At-least-once delivery must not issue two receipts for one action."""
    applied: list[str] = []
    consumers = ConsumerRegistry(
        open_unit=open_unit, bus=bus, now=FakeClock(), alert=CollectingAlertHook()
    )
    consumers.register(ACTION_COMPLETED, group="receipts", handler=lambda e: applied.append(e.id))

    event = an_event(ACTION_COMPLETED)
    for _ in range(3):
        bus.publish(event)
    bus.drain()

    assert applied == [event.id]
    assert consumers.stats("receipts").duplicates == 2


def test_two_groups_each_apply_the_event_once(
    open_unit: Callable[[], UnitOfWork], bus: EventBus
) -> None:
    """Deduplication is per group: receipts and insights both get their turn."""
    receipts: list[str] = []
    insights: list[str] = []
    consumers = ConsumerRegistry(
        open_unit=open_unit, bus=bus, now=FakeClock(), alert=CollectingAlertHook()
    )
    consumers.register(ACTION_COMPLETED, group="receipts", handler=lambda e: receipts.append(e.id))
    consumers.register(ACTION_COMPLETED, group="insights", handler=lambda e: insights.append(e.id))

    event = an_event(ACTION_COMPLETED)
    bus.publish(event)
    bus.publish(event)
    bus.drain()

    assert receipts == [event.id]
    assert insights == [event.id]


# -- acceptance 3: retries exhausted, dead letter, alert ------------------ #


def test_a_consumer_that_always_fails_is_dead_lettered_and_alerts(
    open_unit: Callable[[], UnitOfWork], bus: EventBus
) -> None:
    clock = FakeClock()
    alerts = CollectingAlertHook()
    consumers = ConsumerRegistry(
        open_unit=open_unit,
        bus=bus,
        now=clock,
        max_attempts=3,
        backoff=timedelta(seconds=2),
        alert=alerts,
    )
    consumers.register(ACTION_COMPLETED, group="receipts", handler=_always_fails)

    event = an_event(ACTION_COMPLETED)
    bus.publish(event)

    # Three attempts, each after its backoff has elapsed.
    for _ in range(3):
        bus.drain()
        clock.advance(timedelta(minutes=1))
        bus.drain()

    letters = consumers.dead_letters()
    assert len(letters) == 1
    letter = letters[0]
    assert letter.event.id == event.id
    assert letter.group == "receipts"
    assert letter.attempts == 3
    assert "the signer is gone" in letter.last_error
    assert letter.is_critical, "action.completed moved money"

    assert alerts.raised == [letter], "a dead letter must reach a person"
    assert alerts.critical == [letter]
    assert consumers.stats("receipts").dead_lettered == 1


def test_a_dead_lettered_event_stops_blocking_the_queue(
    open_unit: Callable[[], UnitOfWork], bus: EventBus
) -> None:
    """The reason a dead-letter store exists: the next event gets through."""
    clock = FakeClock()
    applied: list[str] = []

    def fails_only_for_the_first(event: Event) -> None:
        if event.id == poison.id:
            raise RuntimeError("the signer is gone")
        applied.append(event.id)

    consumers = ConsumerRegistry(
        open_unit=open_unit, bus=bus, now=clock, max_attempts=2, alert=CollectingAlertHook()
    )
    consumers.register(ACTION_COMPLETED, group="receipts", handler=fails_only_for_the_first)

    poison = an_event(ACTION_COMPLETED)
    healthy = an_event(ACTION_COMPLETED)
    bus.publish(poison)
    bus.publish(healthy)

    for _ in range(3):
        bus.drain()
        clock.advance(timedelta(minutes=1))

    assert applied == [healthy.id], "the event behind the poison one must get through"
    assert len(consumers.dead_letters()) == 1


def test_a_retry_waits_for_its_backoff(open_unit: Callable[[], UnitOfWork], bus: EventBus) -> None:
    clock = FakeClock()
    attempts: list[datetime] = []

    def records_then_fails(event: Event) -> None:
        attempts.append(clock.at)
        raise RuntimeError("the signer is gone")

    consumers = ConsumerRegistry(
        open_unit=open_unit,
        bus=bus,
        now=clock,
        max_attempts=5,
        backoff=timedelta(seconds=2),
        alert=CollectingAlertHook(),
    )
    consumers.register(ACTION_COMPLETED, group="receipts", handler=records_then_fails)
    bus.publish(an_event(ACTION_COMPLETED))

    bus.drain()
    assert len(attempts) == 1

    # Too soon: the handler is not called again.
    clock.advance(timedelta(seconds=1))
    bus.drain()
    assert len(attempts) == 1
    assert consumers.stats("receipts").deferred == 1

    # Now the first delay has elapsed.
    clock.advance(timedelta(seconds=2))
    bus.drain()
    assert len(attempts) == 2


def test_backoff_doubles_between_attempts(
    open_unit: Callable[[], UnitOfWork], bus: EventBus
) -> None:
    clock = FakeClock()
    attempts: list[datetime] = []

    def records_then_fails(event: Event) -> None:
        attempts.append(clock.at)
        raise RuntimeError("the signer is gone")

    consumers = ConsumerRegistry(
        open_unit=open_unit,
        bus=bus,
        now=clock,
        max_attempts=4,
        backoff=timedelta(seconds=2),
        alert=CollectingAlertHook(),
    )
    consumers.register(ACTION_COMPLETED, group="receipts", handler=records_then_fails)
    bus.publish(an_event(ACTION_COMPLETED))

    # Walk the clock in one-second steps and let the backoff decide when to run.
    for _ in range(20):
        bus.drain()
        clock.advance(timedelta(seconds=1))

    gaps = [later - earlier for earlier, later in pairwise(attempts)]
    assert gaps == [timedelta(seconds=2), timedelta(seconds=4), timedelta(seconds=8)]


def test_a_critical_consumer_without_an_alert_hook_is_refused(
    open_unit: Callable[[], UnitOfWork], bus: EventBus
) -> None:
    """Refused at wiring time, while someone is still looking.

    Raising when the event actually dies would be useless: the bus reads an
    exception from a consumer as a delivery failure, so the alert would be
    swallowed as a retry and nobody would be told.
    """
    consumers = ConsumerRegistry(open_unit=open_unit, bus=bus, now=FakeClock())

    with pytest.raises(UnalertedDeadLetter, match="nobody was told"):
        consumers.register(ACTION_COMPLETED, group="receipts", handler=_always_fails)


def test_a_non_critical_consumer_needs_no_alert_hook(
    open_unit: Callable[[], UnitOfWork], bus: EventBus
) -> None:
    """Only the events that move money or promise something force the hook."""
    seen: list[str] = []
    consumers = ConsumerRegistry(open_unit=open_unit, bus=bus, now=FakeClock())
    consumers.register(CASE_CREATED, group="timeline", handler=lambda e: seen.append(e.id))

    event = an_event()
    bus.publish(event)
    bus.drain()
    assert seen == [event.id]


def test_a_recovering_consumer_is_not_dead_lettered(
    open_unit: Callable[[], UnitOfWork], bus: EventBus
) -> None:
    clock = FakeClock()
    applied: list[str] = []
    broken = [True]

    def recovers(event: Event) -> None:
        if broken[0]:
            raise RuntimeError("the signer is gone")
        applied.append(event.id)

    consumers = ConsumerRegistry(
        open_unit=open_unit, bus=bus, now=clock, alert=CollectingAlertHook()
    )
    consumers.register(ACTION_COMPLETED, group="receipts", handler=recovers)
    event = an_event(ACTION_COMPLETED)
    bus.publish(event)

    bus.drain()
    broken[0] = False
    clock.advance(timedelta(minutes=1))
    bus.drain()

    assert applied == [event.id]
    assert consumers.dead_letters() == []


# -- the correlation id carries through ----------------------------------- #


def test_the_correlation_id_reaches_the_consumer(
    open_unit: Callable[[], UnitOfWork], bus: EventBus
) -> None:
    seen: list[str | None] = []
    consumers = ConsumerRegistry(open_unit=open_unit, bus=bus, now=FakeClock())
    consumers.register(
        CASE_CREATED, group="timeline", handler=lambda e: seen.append(current_correlation_id())
    )

    event = Event.of(SAMPLES[CASE_CREATED], subject=DILANI, correlation_id="REQ-42")
    with open_unit() as unit:
        outbox_in(unit).append(event)
        unit.commit()
    Relay(open_unit=open_unit, bus=bus).run_once()
    bus.drain()

    assert seen == ["REQ-42"]


def test_the_correlation_id_does_not_leak_between_events(
    open_unit: Callable[[], UnitOfWork], bus: EventBus
) -> None:
    seen: list[str | None] = []
    consumers = ConsumerRegistry(open_unit=open_unit, bus=bus, now=FakeClock())
    consumers.register(
        CASE_CREATED, group="timeline", handler=lambda e: seen.append(current_correlation_id())
    )

    bus.publish(Event.of(SAMPLES[CASE_CREATED], subject=DILANI, correlation_id="REQ-1"))
    bus.publish(Event.of(SAMPLES[CASE_CREATED], subject=DILANI, correlation_id="REQ-2"))
    bus.drain()

    assert seen == ["REQ-1", "REQ-2"]
    assert current_correlation_id() is None, "the id must not outlive the handler"


def test_an_event_without_a_correlation_id_starts_its_own_trace(
    open_unit: Callable[[], UnitOfWork], bus: EventBus
) -> None:
    seen: list[str | None] = []
    consumers = ConsumerRegistry(open_unit=open_unit, bus=bus, now=FakeClock())
    consumers.register(
        CASE_CREATED, group="timeline", handler=lambda e: seen.append(current_correlation_id())
    )

    event = an_event()
    bus.publish(event)
    bus.drain()

    assert seen == [event.id]


def test_a_trace_can_be_reassembled_from_one_request(
    open_unit: Callable[[], UnitOfWork],
) -> None:
    """One request, three events: the outbox can answer what it caused."""
    with open_unit() as unit:
        outbox = outbox_in(unit)
        first = outbox.append(an_event(CASE_CREATED))
        outbox.append(first.caused(SAMPLES[DomainEventType.DECISION_GENERATED]))
        outbox.append(first.caused(SAMPLES[DomainEventType.RECEIPT_ISSUED]))
        unit.commit()

    with open_unit() as unit:
        assert len(outbox_in(unit).trace(first.id)) == 3


def test_a_derived_event_keeps_the_trace() -> None:
    first = Event.of(SAMPLES[CASE_CREATED], subject=DILANI, correlation_id="REQ-7")
    second = first.caused(SAMPLES[ACTION_COMPLETED])

    assert second.correlation_id == "REQ-7"
    assert second.causation_id == first.id
    assert second.subject == first.subject


def _always_fails(event: Event) -> None:
    raise RuntimeError("the signer is gone")
