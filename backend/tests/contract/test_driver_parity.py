"""Driver parity: mock drivers always; Kafka/Valkey only when full infra is on."""

from __future__ import annotations

import os

import pytest

from clarity.integration.drivers.mock.blob import MockBlobStore
from clarity.integration.drivers.mock.bus import MockBus
from clarity.integration.drivers.mock.cache import MockCache


def _full_enabled() -> bool:
    return os.getenv("CLEARITY_FULL", os.getenv("CLARITY_FULL", "")) == "1"


@pytest.mark.asyncio
async def test_mock_bus_publish_subscribe() -> None:
    bus = MockBus()
    seen: list[dict] = []

    async def handler(msg: dict) -> None:
        seen.append(msg)

    bus.subscribe("case.created", handler)
    await bus.publish("case.created", {"case_id": "CASE-1"})
    assert seen == [{"case_id": "CASE-1"}]
    assert bus.published == [("case.created", {"case_id": "CASE-1"})]


@pytest.mark.asyncio
async def test_mock_cache_roundtrip() -> None:
    cache = MockCache()
    assert await cache.get("k") is None
    await cache.set("k", b"v", ttl_seconds=60)
    assert await cache.get("k") == b"v"
    await cache.delete("k")
    assert await cache.get("k") is None


@pytest.mark.asyncio
async def test_mock_blob_roundtrip() -> None:
    store = MockBlobStore()
    locator = await store.put("receipts/r1.pdf", b"%PDF", content_type="application/pdf")
    assert locator == "receipts/r1.pdf"
    assert await store.get("receipts/r1.pdf") == b"%PDF"
    await store.delete("receipts/r1.pdf")
    with pytest.raises(KeyError):
        await store.get("receipts/r1.pdf")


@pytest.mark.asyncio
async def test_kafka_bus_parity_when_available() -> None:
    if not _full_enabled():
        pytest.importorskip("aiokafka")
    from clarity.integration.drivers.full.kafka_bus import KafkaBus

    bus = KafkaBus()
    seen: list[dict] = []
    bus.subscribe("action.completed", lambda m: seen.append(m))
    await bus.publish("action.completed", {"action_id": "ACT-1"})
    assert seen == [{"action_id": "ACT-1"}]
    assert ("action.completed", {"action_id": "ACT-1"}) in bus.published
    await bus.close()


@pytest.mark.asyncio
async def test_valkey_cache_parity_when_available() -> None:
    if not _full_enabled():
        pytest.importorskip("redis")
    from clarity.integration.drivers.valkey_cache import ValkeyCache

    cache = ValkeyCache()
    await cache.set("parity", b"ok", ttl_seconds=30)
    assert await cache.get("parity") == b"ok"
    await cache.delete("parity")
    await cache.close()
