"""Event bus parity suite (issue #11, B03; ADR-0014; plan 21 section 11.4).

One contract for the bus, which every driver must pass. The in-process driver
runs everywhere; the Kafka driver runs when a broker is reachable, which in CI
is the ``full`` lane (B10). A driver that cannot pass this suite is a finding
about that driver, found here rather than in production.

The three guarantees under test are the ones the money path leans on: per
subject order, at-least-once delivery, and consumer groups that cannot affect
each other. Each assertion is written so it means the same thing whether the
queue behind it is a dict or a Kafka partition.

What is deliberately *not* here, both for the same reason: a promise only the
in-process driver makes is asserted of that driver alone, in
``tests/unit/test_in_process_bus.py``, rather than of every driver.

**How widely one failure spreads.** The in-process driver blocks the failing
subject alone; Kafka blocks the whole partition, which carries many subjects.

**How many drains delivery takes.** The in-process driver has its queue in
memory, so one drain after a publish delivers it. Kafka fetches, and a fetch is
a round trip, so an event already durable may not be in hand yet. Asserting
"publish, drain once, expect everything" tested the in-process timing and made
the Kafka runs of this suite fail about three times in five. So the tests below
whose claim is *what* gets delivered use ``deliver``, which drains until quiet;
the tests whose claim is about a failure boundary keep their explicit drains,
because for them each individual drain is the thing being asserted.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Iterator
from uuid import uuid4

import pytest

from clarity.contracts.events import DomainEventType
from clarity.platform.messaging.bus import DeliveryReport, EventBus
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


# -- draining ------------------------------------------------------------ #

#: Generous: it bounds a hang, it is not a timing assertion. A reached deadline
#: is reported as a failure naming what was still missing, never as success.
QUIET_DEADLINE_SECONDS = 20.0


def deliver(bus: EventBus, *, expect: int | None = None) -> DeliveryReport:
    """Drain until the bus has nothing left, and report the totals.

    Use this where the claim is *what* was delivered: the order it arrived in,
    which groups saw it, how many deliveries it counted. The port does not
    promise that one drain is enough (see ``EventBus.drain``), so a test that
    drains once is asserting the in-process driver's timing.

    How much quiet is enough depends on whether there is a count to confirm it,
    because one empty fetch is exactly what the driver itself used to misread as
    "nothing left" and the helper must not reintroduce that bug on the test
    side:

    - **With ``expect``**, one empty drain is enough once the count is reached.
      The count is the evidence that nothing is still in flight; the empty drain
      then confirms nothing *more* is coming, which is what catches a duplicate.
      An empty drain while the count is short means the fetch has not caught up,
      so draining continues. ``expect`` is a floor and never a stop, so a driver
      that over-delivers still fails the test's own assertion.
    - **Without it**, where the claim is that nothing arrives at all, there is no
      count, so quiet has to be established by **two** consecutive empty drains.

    That costs a poll window only in the two tests that need it, rather than in
    all twelve. Against Kafka each drain is a 0.5 s poll, and a blanket two
    drains everywhere added about a second per call for nothing.
    """
    totals = DeliveryReport()
    quiet = 0
    needed = 1 if expect is not None else 2
    deadline = time.monotonic() + QUIET_DEADLINE_SECONDS
    while time.monotonic() < deadline:
        report = bus.drain()
        totals = DeliveryReport(
            delivered=totals.delivered + report.delivered,
            failed=totals.failed + report.failed,
            stalled=report.stalled,
        )
        if report.delivered or report.failed:
            quiet = 0
            continue
        quiet += 1
        if quiet >= needed and (expect is None or totals.delivered >= expect):
            return totals
    pytest.fail(
        f"the bus never went quiet in {QUIET_DEADLINE_SECONDS}s "
        f"(delivered {totals.delivered}"
        + (f" of an expected {expect}" if expect is not None else "")
        + f", failed {totals.failed}, stalled {totals.stalled})"
    )


def drain_until(
    bus: EventBus,
    offered: Callable[[DeliveryReport], bool],
    why: str,
) -> DeliveryReport:
    """Drain until one drain's own report satisfies ``offered``, and return it.

    The counterpart to ``deliver``, for the failure tests. Their claim is about
    a single drain ("the first offer failed", "nothing came past the blocked
    one"), so draining until quiet would perform the retry inside the helper
    and assert nothing. This waits only for the event to be *in hand*, which is
    the fetch the port makes no promise about, and hands that one drain's
    report back untouched for the test to assert on.
    """
    deadline = time.monotonic() + QUIET_DEADLINE_SECONDS
    while time.monotonic() < deadline:
        report = bus.drain()
        if offered(report):
            return report
    pytest.fail(f"{why}: did not happen within {QUIET_DEADLINE_SECONDS}s")


def until_failed(bus: EventBus) -> DeliveryReport:
    """Drain until one drain saw the failure, and return that drain's report.

    Every failure test here wants the same moment: the drain in which the
    handler that is meant to fail actually failed. Waiting for "a handler was
    called at all" is not enough, because in the two-group test the healthy
    group satisfies that on its own while the failing group has not fetched.
    """
    return drain_until(
        bus,
        lambda report: report.failed >= 1,
        "the failing handler was never offered the event",
    )


# -- acceptance 1: order per subject ------------------------------------- #


def test_three_events_for_one_subscriber_arrive_in_order(bus: EventBus) -> None:
    seen: list[str] = []
    bus.subscribe(CASE_CREATED, group="timeline", handler=lambda e: seen.append(e.id))

    published = [an_event() for _ in range(3)]
    for event in published:
        bus.publish(event)
    deliver(bus, expect=len(published))

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
    deliver(bus, expect=len(dilani) + len(nimal))

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

    first = until_failed(bus)
    assert first.failed == 1
    assert succeeded == []

    second = deliver(bus, expect=1)
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

    assert until_failed(bus).failed == 1
    assert seen == [], "nothing may be delivered past a blocked event"

    deliver(bus, expect=2)
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

    assert until_failed(bus).failed == 1
    broken[0] = False
    assert deliver(bus, expect=1).is_clear
    assert seen == [event.id]


# -- consumer group isolation -------------------------------------------- #


def test_every_group_gets_its_own_copy(bus: EventBus) -> None:
    timeline: list[str] = []
    insights: list[str] = []
    bus.subscribe(CASE_CREATED, group="timeline", handler=lambda e: timeline.append(e.id))
    bus.subscribe(CASE_CREATED, group="insights", handler=lambda e: insights.append(e.id))

    event = an_event()
    bus.publish(event)
    deliver(bus, expect=2)

    assert timeline == [event.id]
    assert insights == [event.id]


def test_one_group_failing_does_not_hold_up_another(bus: EventBus) -> None:
    healthy: list[str] = []
    bus.subscribe(CASE_CREATED, group="broken", handler=_always_fails)
    bus.subscribe(CASE_CREATED, group="healthy", handler=lambda e: healthy.append(e.id))

    event = an_event()
    bus.publish(event)
    report = until_failed(bus)

    assert healthy == [event.id], "a failing group held up a healthy one"
    assert report.failed == 1
    assert "broken" in report.stalled
    assert "healthy" not in report.stalled


def test_a_group_only_receives_the_types_it_subscribed_to(bus: EventBus) -> None:
    seen: list[DomainEventType] = []
    bus.subscribe(ACTION_COMPLETED, group="receipts", handler=lambda e: seen.append(e.type))

    bus.publish(an_event(kind=CASE_CREATED))
    bus.publish(an_event(kind=ACTION_COMPLETED))
    deliver(bus, expect=1)

    assert seen == [ACTION_COMPLETED]


def test_an_event_nobody_subscribed_to_is_not_an_error(bus: EventBus) -> None:
    bus.publish(an_event())
    assert deliver(bus).is_clear


# -- the rest of the contract -------------------------------------------- #


def test_two_handlers_in_one_group_count_as_one_delivery(bus: EventBus) -> None:
    """Both handlers run, and the report counts the event once.

    The case that tells ``delivered`` apart from "handler calls": the group is
    the unit that takes or retries an event, so two handlers inside it are one
    delivery, and a raise from either retries the event for both.
    """
    first: list[str] = []
    second: list[str] = []
    bus.subscribe(CASE_CREATED, group="timeline", handler=lambda e: first.append(e.id))
    bus.subscribe(CASE_CREATED, group="timeline", handler=lambda e: second.append(e.id))

    event = an_event()
    bus.publish(event)
    report = deliver(bus, expect=1)

    assert first == [event.id] and second == [event.id]
    assert report.delivered == 1, "one event, one group, however many handlers"


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
    deliver(bus)
    assert seen == []


def test_a_group_adding_a_second_type_does_not_lose_the_first(bus: EventBus) -> None:
    """Subscribing to another type must not disturb the types already held.

    The port's promise is that nothing published after a subscribe is lost. A
    group that consumes several event types subscribes several times, which is
    the ordinary wiring: ``notifications`` and ``proactive`` in the composition
    root both do it in a loop.

    For a broker that costs a rebalance per subscribe, and the Kafka driver was
    losing the already-assigned partitions' position to it: the new assignment
    discarded the pinned offset, the consumer then resolved its reset policy at
    fetch time, and an event published afterwards was skipped for good. Measured
    at four losses in five before the fix (2026-10-03). It showed up as a flake
    in the two-handler test, which was the only other one that subscribed twice.
    """
    seen: list[str] = []
    bus.subscribe(CASE_CREATED, group="timeline", handler=lambda e: seen.append(e.id))
    bus.subscribe(ACTION_COMPLETED, group="timeline", handler=lambda e: seen.append(e.id))

    # Published to the type subscribed *first*, which is the one a rebalance
    # for the second subscribe can strand.
    first = an_event(kind=CASE_CREATED)
    second = an_event(kind=ACTION_COMPLETED)
    bus.publish(first)
    bus.publish(second)
    deliver(bus, expect=2)

    assert sorted(seen) == sorted([first.id, second.id])


def test_the_report_counts_one_delivery_per_event_per_group(bus: EventBus) -> None:
    """Both drivers count the unit a group takes or retries: the event.

    Named for handler calls until 2026-10-03, which is not what either driver
    reports and not what the port means. With one handler per group the two
    numbers coincide, so the name was never contradicted here;
    ``test_two_handlers_in_one_group_count_as_one_delivery`` pins the case that
    tells them apart.
    """
    bus.subscribe(CASE_CREATED, group="a", handler=lambda e: None)
    bus.subscribe(CASE_CREATED, group="b", handler=lambda e: None)
    bus.publish(an_event())
    bus.publish(an_event(NIMAL))

    report = deliver(bus, expect=4)
    assert report.delivered == 4, "two events, two groups"
    assert report.is_clear


def _always_fails(event: Event) -> None:
    raise RuntimeError("this consumer is broken")
