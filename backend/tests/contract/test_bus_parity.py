"""Event bus parity suite (issue #11, B03; ADR-0014; plan 21 section 11.4).

One contract for the bus, which every driver must pass. The in-process driver
runs everywhere; the Kafka driver runs when a broker is reachable, which in CI
is the ``full`` lane (B10). A driver that cannot pass this suite is a finding
about that driver, found here rather than in production.

The three guarantees under test are the ones the money path leans on: per
subject order, at-least-once delivery, and consumer groups that cannot affect
each other. Each assertion is written so it means the same thing whether the
queue behind it is a dict or a Kafka partition.

What is deliberately *not* here: how widely one failure spreads. The in-process
driver blocks the failing subject alone; Kafka blocks the whole partition, which
carries many subjects. Both honour the port, so the narrower in-process promise
is tested in ``tests/unit/test_in_process_bus.py`` instead of being asserted of
every driver.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from uuid import uuid4

import pytest

from clarity.contracts.events import DomainEventType
from clarity.platform.messaging.bus import EventBus
from clarity.platform.messaging.drivers.in_process import InProcessEventBus
from clarity.platform.messaging.envelope import Event

from ..support.events import SAMPLES

DILANI = "sub_dilani"
NIMAL = "sub_nimal"

CASE_CREATED = DomainEventType.CASE_CREATED
ACTION_COMPLETED = DomainEventType.ACTION_COMPLETED


def an_event(subject: str = DILANI, kind: DomainEventType = CASE_CREATED) -> Event:
    return Event.of(SAMPLES[kind], subject=subject)


# -- drivers ------------------------------------------------------------- #


def _in_process() -> Iterator[EventBus]:
    bus = InProcessEventBus()
    try:
        yield bus
    finally:
        bus.close()


def _kafka() -> Iterator[EventBus]:
    """The ``full`` profile driver. Skipped unless a broker is configured."""
    bootstrap = os.environ.get("CLARITY_KAFKA_BOOTSTRAP")
    if not bootstrap:
        pytest.skip("set CLARITY_KAFKA_BOOTSTRAP to run the suite against Kafka")
    kafka_module = pytest.importorskip(
        "clarity.platform.messaging.drivers.kafka",
        reason="the kafka extra is not installed",
    )
    bus = kafka_module.KafkaEventBus(
        bootstrap_servers=bootstrap,
        # A fresh prefix per test. The prefix names both the topics and the
        # consumer groups, so one test cannot read another's events or inherit
        # its committed offsets. Topics are left behind for inspection; a dev
        # broker is disposable (`make down-full`).
        topic_prefix=f"clarity-test-{uuid4().hex[:12]}",
        # One partition, so a test that asserts ordering is deterministic.
        partitions=1,
    )
    try:
        yield bus
    finally:
        bus.close()


DRIVERS: dict[str, Callable[[], Iterator[EventBus]]] = {
    "in_process": _in_process,
    "kafka": _kafka,
}


@pytest.fixture(params=sorted(DRIVERS), ids=sorted(DRIVERS))
def bus(request: pytest.FixtureRequest) -> Iterator[EventBus]:
    yield from DRIVERS[request.param]()


# -- acceptance 1: order per subject ------------------------------------- #


def test_three_events_for_one_subscriber_arrive_in_order(bus: EventBus) -> None:
    seen: list[str] = []
    bus.subscribe(CASE_CREATED, group="timeline", handler=lambda e: seen.append(e.id))

    published = [an_event() for _ in range(3)]
    for event in published:
        bus.publish(event)
    bus.drain()

    assert seen == [event.id for event in published]


def test_order_is_per_subject_not_global(bus: EventBus) -> None:
    """Two customers interleave freely; each one's own order is intact."""
    seen: dict[str, list[str]] = {DILANI: [], NIMAL: []}
    bus.subscribe(CASE_CREATED, group="timeline", handler=lambda e: seen[e.subject].append(e.id))

    dilani = [an_event(DILANI) for _ in range(3)]
    nimal = [an_event(NIMAL) for _ in range(3)]
    for first, second in zip(dilani, nimal, strict=True):
        bus.publish(first)
        bus.publish(second)
    bus.drain()

    assert seen[DILANI] == [event.id for event in dilani]
    assert seen[NIMAL] == [event.id for event in nimal]


# -- acceptance 2: at least once, processed once overall ------------------ #


def test_a_handler_that_fails_once_sees_the_event_again(bus: EventBus) -> None:
    attempts: list[str] = []
    succeeded: list[str] = []

    def flaky(event: Event) -> None:
        attempts.append(event.id)
        if len(attempts) == 1:
            raise RuntimeError("the receipt signer was briefly unavailable")
        succeeded.append(event.id)

    bus.subscribe(ACTION_COMPLETED, group="receipts", handler=flaky)
    event = an_event(kind=ACTION_COMPLETED)
    bus.publish(event)

    first = bus.drain()
    assert first.failed == 1
    assert succeeded == []

    second = bus.drain()
    assert second.is_clear
    # Delivered twice, processed once: that is at-least-once, and it is why a
    # consumer must be idempotent (B04 adds the processed_event record).
    assert attempts == [event.id, event.id]
    assert succeeded == [event.id]


def test_a_failure_does_not_reorder_the_subject_behind_it(bus: EventBus) -> None:
    """The blocked event stays at the head: a later one cannot overtake it."""
    seen: list[str] = []
    failures: list[str] = []

    def fails_the_first_time(event: Event) -> None:
        if event.id == first.id and not failures:
            failures.append(event.id)
            raise RuntimeError("transient")
        seen.append(event.id)

    bus.subscribe(CASE_CREATED, group="timeline", handler=fails_the_first_time)
    first, second = an_event(), an_event()
    bus.publish(first)
    bus.publish(second)

    bus.drain()
    assert seen == [], "nothing may be delivered past a blocked event"

    bus.drain()
    assert seen == [first.id, second.id]


def test_a_blocked_event_clears_once_the_handler_recovers(bus: EventBus) -> None:
    """A failure delays delivery, it never drops it."""
    seen: list[str] = []
    broken = [True]

    def recovers(event: Event) -> None:
        if broken[0]:
            raise RuntimeError("the adapter was down")
        seen.append(event.id)

    bus.subscribe(CASE_CREATED, group="timeline", handler=recovers)
    event = an_event()
    bus.publish(event)

    assert bus.drain().failed == 1
    broken[0] = False
    assert bus.drain().is_clear
    assert seen == [event.id]


# -- consumer group isolation -------------------------------------------- #


def test_every_group_gets_its_own_copy(bus: EventBus) -> None:
    timeline: list[str] = []
    insights: list[str] = []
    bus.subscribe(CASE_CREATED, group="timeline", handler=lambda e: timeline.append(e.id))
    bus.subscribe(CASE_CREATED, group="insights", handler=lambda e: insights.append(e.id))

    event = an_event()
    bus.publish(event)
    bus.drain()

    assert timeline == [event.id]
    assert insights == [event.id]


def test_one_group_failing_does_not_hold_up_another(bus: EventBus) -> None:
    healthy: list[str] = []
    bus.subscribe(CASE_CREATED, group="broken", handler=_always_fails)
    bus.subscribe(CASE_CREATED, group="healthy", handler=lambda e: healthy.append(e.id))

    event = an_event()
    bus.publish(event)
    report = bus.drain()

    assert healthy == [event.id]
    assert report.failed == 1
    assert "broken" in report.stalled
    assert "healthy" not in report.stalled


def test_a_group_only_receives_the_types_it_subscribed_to(bus: EventBus) -> None:
    seen: list[DomainEventType] = []
    bus.subscribe(ACTION_COMPLETED, group="receipts", handler=lambda e: seen.append(e.type))

    bus.publish(an_event(kind=CASE_CREATED))
    bus.publish(an_event(kind=ACTION_COMPLETED))
    bus.drain()

    assert seen == [ACTION_COMPLETED]


def test_an_event_nobody_subscribed_to_is_not_an_error(bus: EventBus) -> None:
    bus.publish(an_event())
    assert bus.drain().is_clear


# -- the rest of the contract -------------------------------------------- #


def test_two_handlers_in_one_group_both_run(bus: EventBus) -> None:
    first: list[str] = []
    second: list[str] = []
    bus.subscribe(CASE_CREATED, group="timeline", handler=lambda e: first.append(e.id))
    bus.subscribe(CASE_CREATED, group="timeline", handler=lambda e: second.append(e.id))

    event = an_event()
    bus.publish(event)
    bus.drain()

    assert first == [event.id] and second == [event.id]


def test_a_drain_with_nothing_published_is_clear(bus: EventBus) -> None:
    bus.subscribe(CASE_CREATED, group="timeline", handler=lambda e: None)
    report = bus.drain()
    assert report.is_clear
    assert report.delivered == 0


def test_a_subscriber_registered_after_publish_does_not_get_the_backlog(bus: EventBus) -> None:
    """A group's stream starts when it subscribes, as a new Kafka group does."""
    bus.publish(an_event())
    seen: list[str] = []
    bus.subscribe(CASE_CREATED, group="late", handler=lambda e: seen.append(e.id))
    bus.drain()
    assert seen == []


def test_the_report_counts_handler_calls(bus: EventBus) -> None:
    bus.subscribe(CASE_CREATED, group="a", handler=lambda e: None)
    bus.subscribe(CASE_CREATED, group="b", handler=lambda e: None)
    bus.publish(an_event())
    bus.publish(an_event(NIMAL))

    report = bus.drain()
    assert report.delivered == 4, "two events, two groups"
    assert report.is_clear


def _always_fails(event: Event) -> None:
    raise RuntimeError("this consumer is broken")
