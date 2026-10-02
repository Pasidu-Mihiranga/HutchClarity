"""Kafka event bus driver (full profile).

Uses ``aiokafka`` when installed and ``CLARITY_KAFKA_BOOTSTRAP`` (default
``localhost:9092``) is reachable. Without the client library the class still
imports and exposes the same publish/subscribe surface against an in-process
fallback so parity tests can skip rather than fail on import.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any


def _kafka_available() -> bool:
    try:
        import aiokafka  # noqa: F401
    except ImportError:
        return False
    return True


class KafkaBus:
    """Full-profile bus. Same surface as ``MockBus``.

    When ``aiokafka`` is missing, operates as a local fan-out (stub) so unit
    imports succeed; contract tests gate real Kafka with ``CLEARITY_FULL`` /
    ``CLARITY_FULL`` or ``pytest.importorskip("aiokafka")``.
    """

    def __init__(
        self,
        *,
        bootstrap_servers: str | None = None,
        topic_prefix: str = "clarity.",
    ) -> None:
        self.bootstrap_servers = bootstrap_servers or os.getenv(
            "CLARITY_KAFKA_BOOTSTRAP", "localhost:9092"
        )
        self.topic_prefix = topic_prefix
        self._handlers: dict[str, list[Any]] = {}
        self._published: list[tuple[str, dict[str, Any]]] = []
        self._producer: Any = None
        full = os.getenv("CLEARITY_FULL", os.getenv("CLARITY_FULL", ""))
        self._use_kafka = _kafka_available() and full == "1"

    def subscribe(self, topic: str, handler: Any) -> None:
        self._handlers.setdefault(topic, []).append(handler)

    async def _ensure_producer(self) -> Any:
        if self._producer is not None:
            return self._producer
        from aiokafka import AIOKafkaProducer

        self._producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        )
        await self._producer.start()
        return self._producer

    async def publish(self, topic: str, message: dict[str, Any]) -> None:
        self._published.append((topic, dict(message)))
        if self._use_kafka:
            producer = await self._ensure_producer()
            await producer.send_and_wait(f"{self.topic_prefix}{topic}", message)
        for handler in self._handlers.get(topic, []):
            if asyncio.iscoroutinefunction(handler):
                await handler(message)
            else:
                handler(message)

    async def close(self) -> None:
        if self._producer is not None:
            await self._producer.stop()
            self._producer = None

    @property
    def published(self) -> list[tuple[str, dict[str, Any]]]:
        return list(self._published)
