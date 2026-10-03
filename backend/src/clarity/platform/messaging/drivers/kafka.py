"""Kafka event bus driver for the ``full`` profile (B03, ADR-0014).

Topic per event type, key per subject, consumer group per subscriber. The key
is what buys the port's ordering guarantee: Kafka keeps one partition in order
and routes a key to one partition, so everything about one ``subscriber_ref``
is consumed in the order it was produced.

Two things this driver must get right, and the parity suite proves it does:

**Subscribing is not complete until partitions are assigned.** A Kafka consumer
joins its group lazily, on the first poll, and a new group starts at the end of
the log. Returning from ``subscribe`` before the join finishes would silently
drop every event published in the gap, which for ``action.completed`` means a
receipt that is never issued. So ``subscribe`` creates the topic and blocks
until the broker has assigned it.

**An offset moves only after a handler returned.** Auto-commit is off and a
failure rewinds the partition, which is what makes delivery at-least-once
rather than at-most-once.

**One honest difference from the in-process driver.** Kafka's unit of blocking
is a partition, not a subject, and a partition carries many subjects. When a
handler fails, this driver rewinds that partition, so every subject sharing it
waits behind the failure. The port's guarantees still hold (order per subject,
at least once, isolated groups) but a failure here delays more customers than
it would in process. Narrowing that needs per-key retry topics, which is B04's
dead-letter and backoff work, not the bus's.

Requires the ``kafka`` extra and a broker: ``make up-full`` starts one, and
``make test-full`` runs the parity suites against it.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from clarity.platform.messaging.bus import DeliveryReport, Handler
from clarity.platform.messaging.envelope import Event, EventType

if TYPE_CHECKING:  # pragma: no cover - import-time typing only
    from confluent_kafka import Consumer, Message, Producer

#: Prefix for every topic this driver owns, so a broker can host other traffic.
DEFAULT_TOPIC_PREFIX = "clarity"

#: How long one drain waits for the broker before concluding it is idle.
DEFAULT_POLL_SECONDS = 0.5

#: How long ``subscribe`` waits for the group to be assigned its partitions.
DEFAULT_ASSIGN_TIMEOUT_SECONDS = 30.0

#: How long a drain keeps waiting for a partition it has just rewound.
#:
#: ``seek`` is asynchronous: it invalidates the local fetch queue and the next
#: fetch has to reach the broker and come back. So the first poll after a
#: rewind can legitimately return nothing while the retried message is still in
#: flight. Treating that as "idle" is what let a drain report everything clear
#: with a failed event still undelivered, which is the one thing this driver
#: promises not to do. Only applies when something was rewound, so an ordinary
#: idle drain still returns after a single empty poll.
DEFAULT_REWIND_GRACE_SECONDS = 15.0

#: Partitions per topic. More partitions narrow how many subjects one failure
#: delays; the number is a deployment choice, not a correctness one.
DEFAULT_PARTITIONS = 6


class KafkaUnavailable(RuntimeError):
    """The ``kafka`` extra is not installed, or the broker could not be reached."""


def _require_confluent() -> Any:
    try:
        import confluent_kafka
        import confluent_kafka.admin  # the admin API is not imported by the package
    except ImportError as error:
        raise KafkaUnavailable(
            "the Kafka driver needs the kafka extra: pip install -e backend[kafka]"
        ) from error
    return confluent_kafka


class KafkaEventBus:
    """An ``EventBus`` backed by Apache Kafka."""

    def __init__(
        self,
        *,
        bootstrap_servers: str,
        topic_prefix: str = DEFAULT_TOPIC_PREFIX,
        poll_seconds: float = DEFAULT_POLL_SECONDS,
        assign_timeout_seconds: float = DEFAULT_ASSIGN_TIMEOUT_SECONDS,
        partitions: int = DEFAULT_PARTITIONS,
        rewind_grace_seconds: float = DEFAULT_REWIND_GRACE_SECONDS,
    ) -> None:
        self._kafka = _require_confluent()
        self._bootstrap = bootstrap_servers
        self._prefix = topic_prefix
        self._poll_seconds = poll_seconds
        self._assign_timeout = assign_timeout_seconds
        self._rewind_grace = rewind_grace_seconds
        self._partitions = partitions
        self._producer: Producer = self._kafka.Producer(
            {
                "bootstrap.servers": bootstrap_servers,
                # The relay must not lose an event it reported as published.
                "enable.idempotence": True,
                "acks": "all",
            }
        )
        self._handlers: dict[str, dict[EventType, list[Handler]]] = defaultdict(
            lambda: defaultdict(list)
        )
        self._consumers: dict[str, Consumer] = {}
        #: Messages a subscribe-time poll returned before a drain asked for them.
        self._buffered: dict[str, deque[Message]] = defaultdict(deque)
        #: group -> (topic, partition) -> the offset a handler failed on. The
        #: partition is paused until the next drain rewinds and resumes it.
        self._blocked: dict[str, dict[tuple[str, int], int]] = defaultdict(dict)
        #: group -> (topic, partition) -> the next offset to read. Kept here
        #: rather than asked for, because `committed()` is an OffsetFetch round
        #: trip to the group coordinator and a drain would pay it per partition
        #: per tick.
        self._position: dict[str, dict[tuple[str, int], int]] = defaultdict(dict)
        #: group -> the topic list it is currently subscribed to. A second
        #: `subscribe` with the same list would rebalance for nothing, and a
        #: rebalance is where positions get lost (see `_assigned`).
        self._subscribed: dict[str, list[str]] = {}
        #: group -> whether the broker has assigned partitions since the last
        #: `consumer.subscribe`. Set by the rebalance callback, which is the
        #: only place a `seek` is honoured.
        self._assigned: dict[str, bool] = {}
        self._closed = False

    # -- the EventBus port ----------------------------------------------- #

    def publish(self, event: Event) -> None:
        self._guard()
        event.payload()
        self._producer.produce(
            topic=self._topic(event.type),
            key=event.subject.encode(),
            value=event.model_dump_json().encode(),
            headers=[
                ("schema", event.schema_id.encode()),
                ("correlation-id", (event.correlation_id or "").encode()),
            ],
        )
        # Block until the broker acknowledges: the relay marks an outbox row sent
        # only after this returns, so a crash here means a redelivery, not a loss.
        self._producer.flush()

    def subscribe(self, event_type: EventType, *, group: str, handler: Handler) -> None:
        self._guard()
        self._handlers[group][event_type].append(handler)
        topics = sorted(self._topic(t) for t in self._handlers[group])
        consumer = self._consumer_for(group)

        # A second handler for a type this group already has needs no broker
        # call at all. Re-subscribing to the same topics triggers a rebalance,
        # and a rebalance that lands between a publish and a drain used to lose
        # the event, so the cheapest fix is not to ask for one.
        if topics == self._subscribed.get(group):
            return

        self._ensure_topics(topics)
        self._subscribed[group] = topics
        self._assigned[group] = False
        # `on_assign` is the only place a `seek` survives. Setting the offsets
        # here and calling `assign` is how a consumer starts somewhere other
        # than its default, and it is what makes the pin hold across the
        # rebalance that adding a topic causes.
        consumer.subscribe(topics, on_assign=self._pin_on_assign(group))
        self._await_assignment(group, consumer, len(topics))

    def drain(self) -> DeliveryReport:
        self._guard()
        delivered = failed = 0
        stalled: dict[str, int] = {}

        for group, consumer in self._consumers.items():
            taken, blocked = self._drain_group(group, consumer)
            delivered += taken
            failed += blocked
            if blocked:
                stalled[group] = blocked

        return DeliveryReport(delivered=delivered, failed=failed, stalled=stalled)

    def close(self) -> None:
        if self._closed:
            return
        self._producer.flush()
        for consumer in self._consumers.values():
            consumer.close()
        self._consumers.clear()
        self._buffered.clear()
        self._subscribed.clear()
        self._assigned.clear()
        self._blocked.clear()
        self._position.clear()
        self._closed = True

    # -- internals -------------------------------------------------------- #

    def _drain_group(self, group: str, consumer: Consumer) -> tuple[int, int]:
        """Deliver until idle. A failed message pauses its partition.

                Pausing matters. Rewinding alone is not enough: the consumer's live
                position moves as messages leave the local fetch queue, so polling on
                past a failure would carry the position beyond the offset we rewound to
                and the failed event would never be read again in this session.

                **An empty poll does not mean the log is empty.** Kafka offers no such
                guarantee: the data may be on the broker and simply not fetched yet,
                because a fetch is a round trip and ``seek`` throws the local queue
                away. Treating the first empty poll as "idle" was a bug with two faces.
                A drain straight after a rewind reported everything clear with the
                failed event undelivered, and a drain over a freshly published batch
                could stop halfway through it.

        So "idle" is asked of the broker instead of assumed. ``publish`` flushes,
                so anything published before this drain started is already durable, and
                the partition's high watermark says how far it reaches. On every empty
                poll the drain compares that against how far it has read, and keeps
                going while either a rewound partition or an unread offset is
                outstanding, up to the grace deadline. A rewound partition still
                outstanding when the grace runs out stays recorded as blocked, so the
                report says "stalled" rather than "all clear".
        """
        awaiting = self._rewind_blocked(group, consumer)
        delivered = 0
        deadline = time.monotonic() + self._rewind_grace

        while True:
            message = self._next(group, consumer)
            if message is None:
                # Recomputed here, not once at entry. At entry the cached
                # watermark can still predate the publish; by the time a poll
                # has come back empty it has driven a fetch and the cache knows
                # what the partition really holds. Free to re-read, so there is
                # no reason to trust the older answer.
                waiting = awaiting or self._outstanding(group, consumer, awaiting)
                if waiting and time.monotonic() < deadline:
                    continue
                break
            if message.error():
                raise KafkaUnavailable(str(message.error()))

            topic, index, offset = _where(message)
            awaiting.pop((topic, index), None)

            event = Event.model_validate_json(_body(message))
            try:
                for handler in self._handlers[group].get(event.type, []):
                    handler(event)
            except Exception:
                self._block(group, consumer, message)
                continue
            consumer.commit(message=message, asynchronous=False)
            self._position[group][(topic, index)] = offset + 1
            delivered += 1

        # Rewound and never heard from. Nothing was delivered for these and
        # nothing failed either, so without putting them back the drain would
        # report clear while a retry is still outstanding.
        for (topic, index), offset in awaiting.items():
            self._blocked[group][(topic, index)] = offset
            consumer.pause([self._kafka.TopicPartition(topic, index, offset)])

        return delivered, len(self._blocked[group])

    def _block(self, group: str, consumer: Consumer, message: Message) -> None:
        """Stop this partition at the failed offset, leaving the others running."""
        topic, index, offset = _where(message)
        self._blocked[group][(topic, index)] = offset
        consumer.pause([self._kafka.TopicPartition(topic, index, offset)])

    def _outstanding(
        self,
        group: str,
        consumer: Consumer,
        rewound: dict[tuple[str, int], int],
    ) -> dict[tuple[str, int], int]:
        """The last offset each partition holds that this group has not read.

                Both halves are deliberately free of broker calls. The high watermark
                comes from librdkafka's cache, which every fetch response updates, and
                the position is the one this driver has been keeping as it commits.

                Measured, because the obvious version is unusable: an uncached
                ``get_watermark_offsets`` and a ``committed()`` cost about 515 ms each
                per partition, which turned an idle drain from 0.5 s into 3.5 s with
                six partitions. The cached read costs 0.01 ms and knew about six
                freshly published messages before the first poll.

        Paused partitions are left out, and that exclusion is load bearing. A
                partition blocked behind a failure produces nothing by design, so
                waiting for it would make every drain pay the full grace for as long as
                an adapter stayed down: measured at 15 s per drain before this was
                excluded. ``awaiting`` and ``_blocked`` already carry those, with their
                own deadline.
        """
        targets: dict[tuple[str, int], int] = {}
        positions = self._position[group]
        blocked = self._blocked[group]
        for partition in consumer.assignment():
            key = (partition.topic, partition.partition)
            if key in rewound or key in blocked:
                continue
            _, high = consumer.get_watermark_offsets(partition, cached=True)
            if high is None or high <= positions.get(key, high):
                continue
            targets[key] = high - 1
        return targets

    def _rewind_blocked(self, group: str, consumer: Consumer) -> dict[tuple[str, int], int]:
        """Resume every paused partition at the offset that failed, and retry it.

        Returns what was rewound, so the caller knows which partitions it is
        still owed a message from before it may call itself idle.
        """
        blocked = self._blocked.pop(group, {})
        for (topic, index), offset in blocked.items():
            partition = self._kafka.TopicPartition(topic, index, offset)
            consumer.resume([partition])
            consumer.seek(partition)
        return dict(blocked)

    def _next(self, group: str, consumer: Consumer) -> Message | None:
        buffered = self._buffered[group]
        if buffered:
            return buffered.popleft()
        polled: Message | None = consumer.poll(self._poll_seconds)
        return polled

    def _ensure_topics(self, topics: list[str]) -> None:
        """Create the topics up front, so a consumer can be assigned them.

        Relying on auto-creation would leave a subscribing consumer with no
        partitions to be assigned, and the wait below would time out.
        """
        admin = self._kafka.admin.AdminClient({"bootstrap.servers": self._bootstrap})
        existing = set(admin.list_topics(timeout=10).topics)
        wanted = [name for name in topics if name not in existing]
        if not wanted:
            return
        new_topics = [
            self._kafka.admin.NewTopic(name, num_partitions=self._partitions, replication_factor=1)
            for name in wanted
        ]
        for name, future in admin.create_topics(new_topics).items():
            try:
                future.result(timeout=30)
            except Exception as error:
                # A concurrent creation is fine; anything else is not.
                if "already exists" not in str(error).lower():
                    raise KafkaUnavailable(f"could not create topic {name}: {error}") from error

    def _await_assignment(self, group: str, consumer: Consumer, topic_count: int) -> None:
        """Block until the rebalance callback has positioned this consumer.

        Assignment alone is not enough. A consumer resolves ``latest`` on its
        first fetch, which would be after the producer had already written, so
        the events in between would be skipped. Pinning the position is what
        makes "nothing published after subscribe is lost" true, and the pin has
        to happen in the rebalance callback, so this waits for the callback
        rather than for ``assignment()`` to look right.

        Waiting on ``assignment()`` is what the first version did, and it reads
        as satisfied while a rebalance is still in flight: the seek then applies
        to a partition about to be revoked, is discarded with it, and the
        consumer falls back to resolving ``latest`` at fetch time, which is
        after the publish. Measured at four losses in five with a group that
        subscribes to a second event type (2026-10-03).
        """
        deadline = time.monotonic() + self._assign_timeout
        while time.monotonic() < deadline:
            # Polling is what drives the group join and the callback with it.
            # Anything it hands back is a real event, so it is buffered rather
            # than dropped.
            message = consumer.poll(0.1)
            if message is not None and not message.error():
                self._buffered[group].append(message)
            if self._assigned.get(group) and len(consumer.assignment()) >= topic_count:
                return
        raise KafkaUnavailable(
            f"consumer group {group} was not assigned its partitions within "
            f"{self._assign_timeout:.0f}s; is the broker reachable?"
        )

    def _pin_on_assign(self, group: str) -> Callable[[Consumer, list[Any]], None]:
        """The rebalance callback: decide where each partition starts reading.

        Called by librdkafka with the final assignment, which is the only point
        where choosing an offset sticks. Three cases, in order:

        1. **A partition this driver already tracked.** Resume exactly where it
           was. This is the case the old code got wrong: a rebalance caused by
           adding a topic must not move the partitions the group already had.
        2. **Blocked behind a failed handler.** Resume at the failed offset, so
           a rebalance cannot turn a retry into a skip (at least once).
        3. **New to this group.** Its committed offset if it has one, so a
           restart cannot skip an event it never processed; otherwise the end of
           the log, which is what the in-process driver does for a late
           subscriber.
        """

        def assigned(consumer: Consumer, partitions: list[Any]) -> None:
            positions = self._position[group]
            blocked = self._blocked[group]
            for partition in partitions:
                key = (partition.topic, partition.partition)
                known = positions.get(key, blocked.get(key))
                if known is not None:
                    partition.offset = known
                else:
                    partition.offset = self._start_offset(consumer, partition)
                positions[key] = partition.offset
            # Assigning here overrides the default assignment, which is how a
            # consumer is told to start anywhere but its reset policy.
            consumer.assign(partitions)
            self._assigned[group] = True

        return assigned

    def _start_offset(self, consumer: Consumer, partition: Any) -> int:
        """Where a partition this group has never read should start."""
        committed = consumer.committed([partition], timeout=10)[0]
        if committed.offset >= 0:
            return int(committed.offset)
        _, high = consumer.get_watermark_offsets(partition, timeout=10, cached=False)
        return int(high)

    def _consumer_for(self, group: str) -> Consumer:
        if group not in self._consumers:
            self._consumers[group] = self._kafka.Consumer(
                {
                    "bootstrap.servers": self._bootstrap,
                    "group.id": f"{self._prefix}.{group}",
                    # Offsets move only when a handler returned, so a crash
                    # redelivers rather than skips (at least once).
                    "enable.auto.commit": False,
                    # A new group starts at the end, as the in-process driver
                    # does. Nothing published after subscribe is missed, because
                    # subscribe does not return until partitions are assigned.
                    "auto.offset.reset": "latest",
                }
            )
        return self._consumers[group]

    def _topic(self, event_type: EventType) -> str:
        return f"{self._prefix}.{event_type.value}"

    def _guard(self) -> None:
        if self._closed:
            raise KafkaUnavailable("this bus is closed")


def _body(message: Message) -> bytes:
    """The message payload, refusing a message that carries none.

    A Kafka record may have a null value (a tombstone in a compacted topic).
    Clarity publishes no tombstones, so one here means something else is writing
    to our topics and the event cannot be trusted.

    The payload is checked with ``isinstance`` rather than trusted, because
    ``confluent_kafka`` is an optional dependency that ships no stubs: in the
    lite lane, where it is not installed, every value it hands back is ``Any``
    and a declared return type would be a claim mypy cannot check. The check
    is the same guarantee in both lanes.
    """
    value = message.value()
    if value is None:
        topic, index, offset = _where(message)
        raise KafkaUnavailable(f"{topic}[{index}]@{offset} carries no payload")
    if not isinstance(value, bytes):
        topic, index, offset = _where(message)
        raise KafkaUnavailable(
            f"{topic}[{index}]@{offset} carries {type(value).__name__}, not bytes"
        )
    return value


def _where(message: Message) -> tuple[str, int, int]:
    """The message's topic, partition and offset, all of which must be known."""
    topic, index, offset = message.topic(), message.partition(), message.offset()
    if topic is None or index is None or offset is None:
        raise KafkaUnavailable(f"the broker returned a message with no position: {message!r}")
    return topic, index, offset


__all__ = [
    "DEFAULT_ASSIGN_TIMEOUT_SECONDS",
    "DEFAULT_PARTITIONS",
    "DEFAULT_POLL_SECONDS",
    "DEFAULT_REWIND_GRACE_SECONDS",
    "DEFAULT_TOPIC_PREFIX",
    "KafkaEventBus",
    "KafkaUnavailable",
]
