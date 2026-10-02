"""Event bus port — lite InMemory / full Kafka share this surface."""

from __future__ import annotations

from typing import Any, Protocol


class BusPort(Protocol):
    """Publish/subscribe surface used by composition-root drivers."""

    def subscribe(self, topic: str, handler: Any) -> None:
        """Register a sync or async handler for ``topic``."""

    async def publish(self, topic: str, message: dict[str, Any]) -> None:
        """Publish ``message`` to ``topic`` and invoke local subscribers."""

    @property
    def published(self) -> list[tuple[str, dict[str, Any]]]:
        """Messages published through this driver (for tests / lite inspection)."""
