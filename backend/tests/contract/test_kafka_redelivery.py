"""Redelivery after a handler failure, in the Kafka driver specifically.

`test_bus_parity.py` already asserts the behaviour every driver owes: a failure
delays delivery and never drops it. This file exists because the Kafka driver
broke that promise in a way the parity suite could only catch by luck.

**What was wrong.** A drain rewinds a blocked partition with `resume` and
`seek`, then polls. `seek` is asynchronous: it drops the local fetch queue and
the refill is a round trip to the broker. So the first poll after a rewind can
return nothing while the retried message is still in flight. The drain read
that as "idle" and returned `delivered=0, failed=0, stalled={}`, which makes
`is_clear` true. A relay would log everything clear with the event undelivered.

**Why it looked like a flaky test.** The default poll window is 0.5s, which
usually covers the round trip, so it passed. Under the full suite, with the
broker busy, it did not: the parity test failed in two of three full runs and
passed 26 of 26 times in isolation.

**Why these tests are not flaky.** They shrink the poll window below a broker
round trip instead of waiting for load to do it. That turns a race into a
certainty: before the fix, the first test here fails every time.
"""

from __future__ import annotations

import os
import time
from collections.abc import Iterator
from uuid import uuid4

import pytest

from clarity.contracts.events import CaseCreatedV1, DomainEventType
from clarity.kernel.common import Channel, Language
from clarity.platform.messaging.envelope import Event

CASE_CREATED = DomainEventType.CASE_CREATED

#: Far below a broker round trip, so an empty first poll after the rewind is
#: guaranteed rather than occasional.
TOO_SHORT_TO_FETCH = 0.001


def an_event() -> Event:
    return Event.of(
        CaseCreatedV1(
            case_id=f"CASE-{uuid4().hex[:10]}",
            case_no="C-1",
            channel=Channel.APP,
            trigger="customer",
            language=Language.EN,
            money_at_stake_lkr="49.00",
        ),
        subject="sub-redelivery",
    )


def _bus(**overrides: float) -> Iterator[object]:
    bootstrap = os.environ.get("CLARITY_KAFKA_BOOTSTRAP")
    if not bootstrap:
        pytest.skip("set CLARITY_KAFKA_BOOTSTRAP to run against Kafka")
    module = pytest.importorskip(
        "clarity.platform.messaging.drivers.kafka",
        reason="the kafka extra is not installed",
    )
    bus = module.KafkaEventBus(
        bootstrap_servers=bootstrap,
        topic_prefix=f"clarity-redeliver-{uuid4().hex[:12]}",
        partitions=1,
        **overrides,
    )
    try:
        yield bus
    finally:
        bus.close()


def _until_failed(bus: object, *, attempts: int = 2000) -> None:
    """Drain until the handler has failed once.

    A one millisecond poll is too short for the broker's first fetch as well,
    so getting the event in takes a few goes. That is setup, not the claim: the
    claim is what the drain *after* the rewind reports.
    """
    for _ in range(attempts):
        if bus.drain().failed == 1:  # type: ignore[attr-defined]
            return
    pytest.fail("the event never reached the handler")


@pytest.fixture
def impatient_bus() -> Iterator[object]:
    """A bus whose poll window is too short to ever win the fetch race."""
    yield from _bus(poll_seconds=TOO_SHORT_TO_FETCH)


@pytest.fixture
def unforgiving_bus() -> Iterator[object]:
    """A bus that gives a rewound partition no grace at all."""
    yield from _bus(poll_seconds=TOO_SHORT_TO_FETCH, rewind_grace_seconds=0.0)


# -- the regression ------------------------------------------------------- #


def test_a_drain_does_not_report_clear_before_the_retry_arrives(impatient_bus):
    """The bug, pinned. Before the fix this failed on every run.

    The assertion that matters is the pair: `is_clear` and the handler having
    actually run. Either alone passes while the driver is broken, because a
    drain that gave up early reports clear and delivers nothing.
    """
    bus = impatient_bus
    seen: list[str] = []
    broken = [True]

    def recovers(event: Event) -> None:
        if broken[0]:
            raise RuntimeError("the adapter was down")
        seen.append(event.id)

    bus.subscribe(CASE_CREATED, group="timeline", handler=recovers)
    event = an_event()
    bus.publish(event)
    _until_failed(bus)
    broken[0] = False

    report = bus.drain()

    assert report.is_clear, report
    assert report.delivered == 1
    assert seen == [event.id], "reported clear without redelivering"


def test_the_retry_is_committed_so_it_does_not_come_back_again(impatient_bus):
    """Delayed, not duplicated. A third drain must find nothing."""
    bus = impatient_bus
    seen: list[str] = []
    broken = [True]

    def recovers(event: Event) -> None:
        if broken[0]:
            raise RuntimeError("down")
        seen.append(event.id)

    bus.subscribe(CASE_CREATED, group="timeline", handler=recovers)
    bus.publish(an_event())

    _until_failed(bus)
    broken[0] = False
    bus.drain()
    third = bus.drain()

    assert len(seen) == 1, f"the event was delivered {len(seen)} times"
    assert third.is_clear
    assert third.delivered == 0


def test_messages_after_the_failed_one_are_not_skipped(impatient_bus):
    """The reason the rewind uses `seek` and not just a resume.

    The live position moves as messages leave the fetch queue, so resuming
    without seeking would carry the consumer past everything that arrived while
    the partition was blocked.
    """
    bus = impatient_bus
    seen: list[str] = []
    fail_first = [True]

    def recovers(event: Event) -> None:
        if fail_first[0]:
            fail_first[0] = False
            raise RuntimeError("down for the first one only")
        seen.append(event.id)

    bus.subscribe(CASE_CREATED, group="timeline", handler=recovers)
    published = [an_event() for _ in range(3)]
    for event in published:
        bus.publish(event)

    _until_failed(bus)
    for _ in range(2000):
        if bus.drain().is_clear and len(seen) == len(published):
            break

    # The first one was retried and the other two were not lost behind it.
    assert seen == [event.id for event in published]


# -- the drain must not simply always wait -------------------------------- #


def test_an_idle_drain_still_returns_promptly(impatient_bus):
    """The guard against fixing this with a blanket wait.

    The grace applies only while a rewound partition owes a message. An
    ordinary idle drain must still come back after one empty poll, or every
    relay tick would pay the grace.
    """
    bus = impatient_bus
    bus.subscribe(CASE_CREATED, group="timeline", handler=lambda event: None)

    started = time.monotonic()
    report = bus.drain()
    elapsed = time.monotonic() - started

    assert report.is_clear
    assert elapsed < 1.0, f"an idle drain took {elapsed:.2f}s"


def test_a_rewind_that_never_arrives_is_reported_as_stalled(unforgiving_bus):
    """With no grace the retry cannot land, and the drain must say so.

    This is the honest failure: "I could not confirm the retry" is reported as
    still stalled, never as clear. Without putting the partition back the drain
    would claim everything was fine with the event still outstanding.
    """
    bus = unforgiving_bus
    seen: list[str] = []

    def always_broken(event: Event) -> None:
        raise RuntimeError("the adapter is still down")

    bus.subscribe(CASE_CREATED, group="timeline", handler=always_broken)
    bus.publish(an_event())
    _until_failed(bus)

    # The handler is still broken, so even a retry that landed would fail. What
    # is being checked is that a rewind which produced nothing does not read as
    # success.
    report = bus.drain()

    assert not report.is_clear, report
    assert report.failed >= 1
    assert report.stalled, "the blocked partition should still be recorded"
    assert seen == []


@pytest.fixture
def patient_bus() -> Iterator[object]:
    """Impatient polls, but enough grace for one rewind to land."""
    yield from _bus(poll_seconds=TOO_SHORT_TO_FETCH, rewind_grace_seconds=5.0)


def test_the_grace_is_what_makes_a_rewind_converge(patient_bus):
    """The counterpart to the test above, and the reason the grace exists.

    With no grace a drain re-seeks on every attempt and throws away the fetch
    it was waiting for, so it can starve indefinitely. One drain that waits is
    what turns the retry into a delivery.
    """
    bus = patient_bus
    seen: list[str] = []
    broken = [True]

    def recovers(event: Event) -> None:
        if broken[0]:
            raise RuntimeError("down")
        seen.append(event.id)

    bus.subscribe(CASE_CREATED, group="timeline", handler=recovers)
    event = an_event()
    bus.publish(event)
    _until_failed(bus)
    broken[0] = False

    report = bus.drain()

    assert report.is_clear, report
    assert seen == [event.id], "the grace did not let the retry land"
