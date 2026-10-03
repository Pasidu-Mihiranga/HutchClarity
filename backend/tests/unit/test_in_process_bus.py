"""The in-process bus driver's own guarantees (issue #11, B03).

Everything in ``tests/contract/test_bus_parity.py`` holds for this driver too.
What is here is what this driver promises *beyond* the port. Two things, both
because the queue is in memory and no network sits between publish and drain:

- **A failure delays exactly one customer**, since there is one queue per
  subject rather than per partition.
- **One drain delivers everything already published.**

Kafka can promise neither, so neither belongs in the shared suite. The second
one used to be assumed throughout it, which is what made its Kafka runs fail
about three times in five (2026-10-03).
"""

from __future__ import annotations

import pytest

from clarity.contracts.events import DomainEventType, InvalidEventPayload
from clarity.platform.messaging.drivers.in_process import BusClosed, InProcessEventBus
from clarity.platform.messaging.envelope import Event

from ..support.events import SAMPLES

DILANI = "sub_dilani"
NIMAL = "sub_nimal"
CASE_CREATED = DomainEventType.CASE_CREATED


def an_event(subject: str = DILANI) -> Event:
    return Event.of(SAMPLES[CASE_CREATED], subject=subject)


def test_a_failure_blocks_only_the_failing_subject() -> None:
    bus = InProcessEventBus()
    seen: list[str] = []

    def fails_for_dilani(event: Event) -> None:
        if event.subject == DILANI:
            raise RuntimeError("transient")
        seen.append(event.id)

    bus.subscribe(CASE_CREATED, group="timeline", handler=fails_for_dilani)
    bus.publish(an_event(DILANI))
    nimal = an_event(NIMAL)
    bus.publish(nimal)

    report = bus.drain()
    assert seen == [nimal.id], "another customer's events must keep flowing"
    assert report.failed == 1
    assert report.stalled == {"timeline": 1}


def test_pending_shows_what_a_group_has_not_taken() -> None:
    bus = InProcessEventBus()
    bus.subscribe(CASE_CREATED, group="timeline", handler=_always_fails)
    event = an_event()
    bus.publish(event)

    bus.drain()
    assert [e.id for e in bus.pending("timeline")] == [event.id]
    assert bus.pending("nobody") == []


def test_a_delivered_subject_leaves_no_empty_queue_behind() -> None:
    """Queues are reclaimed, so a long-running process does not grow per customer."""
    bus = InProcessEventBus()
    bus.subscribe(CASE_CREATED, group="timeline", handler=lambda e: None)
    bus.publish(an_event())
    bus.drain()
    assert bus.pending("timeline") == []


def test_a_malformed_payload_fails_at_the_producer() -> None:
    """The publisher finds its own mistake, not somebody else's consumer."""
    bus = InProcessEventBus()
    bus.subscribe(CASE_CREATED, group="timeline", handler=lambda e: None)
    broken = an_event()
    broken.data = {"nothing": "valid"}

    with pytest.raises(InvalidEventPayload):
        bus.publish(broken)


def test_a_closed_bus_refuses_use() -> None:
    bus = InProcessEventBus()
    bus.subscribe(CASE_CREATED, group="timeline", handler=lambda e: None)
    bus.close()
    with pytest.raises(BusClosed):
        bus.publish(an_event())
    with pytest.raises(BusClosed):
        bus.drain()


def test_groups_lists_what_subscribed() -> None:
    bus = InProcessEventBus()
    bus.subscribe(CASE_CREATED, group="timeline", handler=lambda e: None)
    bus.subscribe(CASE_CREATED, group="insights", handler=lambda e: None)
    assert bus.groups == ["insights", "timeline"]


def _always_fails(event: Event) -> None:
    raise RuntimeError("this consumer is broken")


def test_one_drain_delivers_everything_already_published() -> None:
    """The timing promise the shared parity suite must not assume.

    The port says only that a later drain offers what a drain did not (see
    ``EventBus.drain``), because a networked driver has to fetch. This driver
    has the events in memory, so for it the weaker promise would hide a real
    regression: anything published before a drain is delivered by that drain,
    in one call, with no retry and nothing left pending.
    """
    bus = InProcessEventBus()
    seen: list[str] = []
    bus.subscribe(CASE_CREATED, group="timeline", handler=lambda e: seen.append(e.id))
    published = [an_event(DILANI) for _ in range(3)] + [an_event(NIMAL) for _ in range(3)]
    for event in published:
        bus.publish(event)

    report = bus.drain()

    assert report.delivered == len(published)
    assert report.is_clear
    assert sorted(seen) == sorted(event.id for event in published)
    assert bus.pending("timeline") == []
