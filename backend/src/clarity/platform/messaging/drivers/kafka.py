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
    ) -> None:
        self._kafka = _require_confluent()
        self._bootstrap = bootstrap_servers
        self._prefix = topic_prefix
        self._poll_seconds = poll_seconds
        self._assign_timeout = assign_timeout_seconds
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
        self._ensure_topics(topics)
        consumer = self._consumer_for(group)
        consumer.subscribe(topics)
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
        self._blocked.clear()
        self._closed = True

    # -- internals -------------------------------------------------------- #

    def _drain_group(self, group: str, consumer: Consumer) -> tuple[int, int]:
        """Deliver until idle. A failed message pauses its partition.

        Pausing matters. Rewinding alone is not enough: the consumer's live
        position moves as messages leave the local fetch queue, so polling on
        past a failure would carry the position beyond the offset we rewound to
        and the failed event would never be read again in this session.
        """
        self._rewind_blocked(group, consumer)
        delivered = 0

        while True:
            message = self._next(group, consumer)
            if message is None:
                return delivered, len(self._blocked[group])
            if message.error():
                raise KafkaUnavailable(str(message.error()))

            event = Event.model_validate_json(_body(message))
            try:
                for handler in self._handlers[group].get(event.type, []):
                    handler(event)
            except Exception:
                self._block(group, consumer, message)
                continue
            consumer.commit(message=message, asynchronous=False)
            delivered += 1

    def _block(self, group: str, consumer: Consumer, message: Message) -> None:
        """Stop this partition at the failed offset, leaving the others running."""
        topic, index, offset = _where(message)
        self._blocked[group][(topic, index)] = offset
        consumer.pause([self._kafka.TopicPartition(topic, index, offset)])

    def _rewind_blocked(self, group: str, consumer: Consumer) -> None:
        """Resume every paused partition at the offset that failed, and retry it."""
        blocked = self._blocked.pop(group, {})
        for (topic, index), offset in blocked.items():
            partition = self._kafka.TopicPartition(topic, index, offset)
            consumer.resume([partition])
            consumer.seek(partition)

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
        """Block until this consumer is assigned its partitions and positioned.

        Assignment alone is not enough. A consumer resolves ``latest`` on its
        first fetch, which would be after the producer had already written, so
        the events in between would be skipped. Pinning the position here is
        what makes "nothing published after subscribe is lost" true.
        """
        deadline = time.monotonic() + self._assign_timeout
        while time.monotonic() < deadline:
            # Polling is what drives the group join. Anything it hands back is
            # a real event, so it is buffered rather than dropped.
            message = consumer.poll(0.1)
            if message is not None and not message.error():
                self._buffered[group].append(message)
            if len(consumer.assignment()) >= topic_count:
                self._pin_start(consumer)
                return
        raise KafkaUnavailable(
            f"consumer group {group} was not assigned its partitions within "
            f"{self._assign_timeout:.0f}s; is the broker reachable?"
        )

    def _pin_start(self, consumer: Consumer) -> None:
        """Resolve where each partition starts reading, before anything is sent.

        A group that has run before resumes at its committed offset, so a
        restart cannot skip an event it never processed. A group that has not
        starts at the end of the log, which is what the in-process driver does
        for a late subscriber.
        """
        for partition in consumer.assignment():
            committed = consumer.committed([partition], timeout=10)[0]
            if committed.offset >= 0:
                continue
            _, high = consumer.get_watermark_offsets(partition, timeout=10, cached=False)
            partition.offset = high
            consumer.seek(partition)

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
    """
    value = message.value()
    if value is None:
        topic, index, offset = _where(message)
        raise KafkaUnavailable(f"{topic}[{index}]@{offset} carries no payload")
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
    "DEFAULT_TOPIC_PREFIX",
    "KafkaEventBus",
    "KafkaUnavailable",
]
