"""clarity-stream entrypoint — attaches InMemoryBus (lite) consumers.

Full profile swaps the bus for Kafka at the composition root; consumers stay
the same callables registered here.
"""

from __future__ import annotations

import asyncio
import logging

from clarity.kernel.events import Event, EventType
from clarity.platform.app import AppBuilder
from clarity.platform.config.settings import get_settings
from clarity.platform.messaging.outbox import InMemoryBus
from clarity.platform.observability.otel import setup_otel

logger = logging.getLogger("clarity.stream")


async def _log_consumer(event: Event) -> None:
    logger.info("consumed %s subject=%s id=%s", event.type.value, event.subject, event.id)


def create_bus() -> InMemoryBus:
    settings = get_settings()
    setup_otel(exporter=settings.otel_exporter, service_name="clarity-stream")
    builder = AppBuilder(profile=settings.profile.value, settings=settings)
    bus = InMemoryBus()
    builder.provide(InMemoryBus, bus)

    from clarity.modules.proactive.module import ProactiveModule

    builder.register_module(ProactiveModule())

    # Baseline consumers for stream health / demo.
    for event_type in (
        EventType.CASE_CREATED,
        EventType.ACTION_COMPLETED,
        EventType.RISK_DETECTED,
    ):
        bus.subscribe(event_type, _log_consumer)
    return bus


async def run_forever(*, idle_seconds: float = 5.0) -> None:
    """Keep the process alive so lite in-process consumers stay registered."""
    create_bus()
    logger.info("stream consumers ready")
    while True:
        await asyncio.sleep(idle_seconds)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_forever())


if __name__ == "__main__":
    main()
