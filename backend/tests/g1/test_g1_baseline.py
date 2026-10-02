"""G1 baseline gate — in-memory, no Postgres required."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from clarity.kernel import (
    CorrelationContext,
    Event,
    EventType,
    Permission,
    Principal,
    Role,
)
from clarity.platform import (
    AuditLedger,
    InMemoryBus,
    MemoryIdempotencyStore,
    PythonPolicy,
    request_hash,
)


@pytest.mark.asyncio
async def test_outbox_publish_order() -> None:
    bus = InMemoryBus()
    events = [
        Event(type=EventType.CASE_CREATED, subject=f"case-{i}", data={"n": i})
        for i in range(5)
    ]
    for event in events:
        await bus.publish(event)
    assert [e.id for e in bus.published] == [e.id for e in events]
    assert [e.data["n"] for e in bus.published] == list(range(5))


def test_idempotency_50_way() -> None:
    store = MemoryIdempotencyStore()
    key = "idem-50"
    scope = "POST /v1/cases"
    payload = {"subscriber_ref": "sub_demo", "channel": "web"}
    digest = request_hash(payload)
    expected = {"case_id": "CAS_FIXED", "status": "open"}

    def worker(_: int) -> dict:
        return store.put(
            key=key,
            scope=scope,
            request_hash_value=digest,
            response=expected,
            status_code=201,
        )

    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=50) as pool:
        futures = [pool.submit(worker, i) for i in range(50)]
        for fut in as_completed(futures):
            results.append(fut.result())

    assert len(results) == 50
    assert all(r["response"] == expected for r in results)
    assert all(r["status_code"] == 201 for r in results)
    assert store.get(key=key, scope=scope)["response"] == expected


def test_audit_tamper_detected() -> None:
    ledger = AuditLedger()
    ledger.append(actor="agent-1", action="case.read", subject="CAS_1", detail={"ok": True})
    ledger.append(actor="agent-1", action="action.approve", subject="ACT_1")
    assert ledger.verify() is True
    ledger.tamper(0, action="case.read.TAMPERED")
    assert ledger.verify() is False


def test_deny_by_default() -> None:
    policy = PythonPolicy()
    anon = Principal(subject="anon", roles=set(), permissions=set())
    assert policy.allow(anon, Permission.CASE_READ) is False
    with pytest.raises(Exception) as excinfo:
        policy.require(anon, Permission.ACTION_APPROVE)
    assert "denied" in str(excinfo.value).lower()

    # Principal with a role that does not include action:approve
    customer = Principal.from_roles(subject="cust-1", roles={Role.CUSTOMER})
    assert policy.allow(customer, Permission.ACTION_APPROVE) is False
    # Unknown / not-granted permission stays denied
    assert policy.allow(customer, Permission.KILL_SWITCH) is False


def test_correlation_context_propagation() -> None:
    CorrelationContext.clear()
    ctx = CorrelationContext(correlation_id="COR_TEST_PROP", causation_id="EVT_1")
    CorrelationContext.bind(ctx)
    current = CorrelationContext.current()
    assert current.correlation_id == "COR_TEST_PROP"
    assert current.causation_id == "EVT_1"
    assert current is ctx
    CorrelationContext.clear()
