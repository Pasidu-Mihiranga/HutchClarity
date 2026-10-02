"""In-process event bus (lite profile parity with Kafka)."""

from __future__ import annotations

import asyncio
from typing import Any


class MockBus:
    """Lite-profile publish/subscribe bus."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[Any]] = {}
        self._published: list[tuple[str, dict[str, Any]]] = []

    def subscribe(self, topic: str, handler: Any) -> None:
        self._handlers.setdefault(topic, []).append(handler)

    async def publish(self, topic: str, message: dict[str, Any]) -> None:
        self._published.append((topic, dict(message)))
        for handler in self._handlers.get(topic, []):
            if asyncio.iscoroutinefunction(handler):
                await handler(message)
            else:
                handler(message)

    @property
    def published(self) -> list[tuple[str, dict[str, Any]]]:
        return list(self._published)
