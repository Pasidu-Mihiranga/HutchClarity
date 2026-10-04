"""Audit ledger tests (plan section 20.3, ADR-0033, ADR-0034).

The outbox, the relay and the consumer framework moved to
``test_outbox_wiring.py`` when B04 split them apart, and per-subject ordering is
covered for every bus driver by ``tests/contract/test_bus_parity.py``.

**Tampering goes through the store, not the ledger object.** These tests used
to assign ``ledger._records`` directly. The trail now lives behind the
persistence port, which is also where an insider with database access would
edit it, so the tests write to the store the same way. That is the deliberate
contract change AGENTS.md section 10 asks to be stated: the attack is the same,
the place it is staged moved to where it would really happen.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from clarity.platform.audit.ledger import (
    AUDIT,
    AUDIT_HEAD,
    HASH_VERSION,
    AppendOnlyViolation,
    AuditEventType,
    AuditLedger,
    AuditRecord,
)
from clarity.platform.messaging.envelope import Event, EventType
from clarity.platform.persistence.memory import MemoryStore, MemoryUnitOfWork

from ..support.events import SAMPLES


def an_event(type_: EventType = EventType.ACTION_COMPLETED, subject: str = "sub_a") -> Event:
    return Event.of(SAMPLES[type_], subject=subject)


# --------------------------------------------------------------------------- #
# Audit ledger
# --------------------------------------------------------------------------- #


class Store:
    """The ledger's backing store, held so a test can play the insider."""

    def __init__(self) -> None:
        self.memory = MemoryStore()

    def unit(self) -> MemoryUnitOfWork:
        return MemoryUnitOfWork(self.memory)

    def ledger(self) -> AuditLedger:
        return AuditLedger(self.unit)

    def write(self, collection: str, key: str, value: Any) -> None:
        with self.unit() as unit:
            unit.repository(collection).put(key, value)
            unit.commit()

    def remove(self, collection: str, key: str) -> None:
        with self.unit() as unit:
            unit.repository(collection).delete(key)
            unit.commit()


def key(seq: int) -> str:
    return str(seq).zfill(12)


def append_three(ledger: AuditLedger) -> None:
    ledger.append(
        AuditEventType.DECISION_MADE,
        actor_ref="clarity-policy",
        object_ref="DEC-1",
        payload={"outcome": "ONE_TAP_FIX"},
        case_id="CASE-1",
    )
    ledger.append(
        AuditEventType.ACTION_EXECUTED,
        actor_ref="clarity-tool-layer",
        object_ref="ACT-1",
        payload={"amount_lkr": "49.00"},
        case_id="CASE-1",
    )
    ledger.append(
        AuditEventType.RECEIPT_ISSUED,
        actor_ref="clarity-receipts",
        object_ref="TR-2027-000001",
        payload={"receipt_id": "TR-2027-000001"},
        case_id="CASE-1",
    )


def test_a_fresh_chain_verifies():
    ledger = AuditLedger()
    append_three(ledger)

    result = ledger.verify()

    assert result.intact and result.length == 3


def test_each_record_links_to_its_predecessor():
    ledger = AuditLedger()
    append_three(ledger)

    records = ledger.records
    assert records[0].prev_hash is None
    assert records[1].prev_hash == records[0].chain_hash
    assert records[2].prev_hash == records[1].chain_hash


def test_altering_a_record_breaks_the_chain():
    """The guarantee: you cannot quietly change what happened."""
    store = Store()
    ledger = store.ledger()
    append_three(ledger)
    forged = ledger.records[1].model_copy(update={"payload_hash": "sha256:forged"})
    store.write(AUDIT, key(2), forged)  # a privileged edit, straight into the table

    result = ledger.verify()

    assert not result.intact
    assert result.broken_at == 2


#: Every field version 1 left outside the hash, with a forged value for it.
#: The first entry is the case found on 2026-10-04: rewriting who approved a
#: refund left ``verify()`` reporting the chain intact.
FORGERIES: list[tuple[str, Any]] = [
    ("actor_ref", "agent:nadeesha"),
    ("event_type", AuditEventType.STAFF_ACTION),
    ("actor_kind", "customer"),
    ("session_ref", "SES-forged"),
    ("object_ref", "plan:999"),
    ("case_id", "CASE-Z"),
    ("detail", {"amount_lkr": "50.00"}),
    ("occurred_at", datetime(2020, 1, 1, tzinfo=UTC)),
    ("recorded_at", datetime(2020, 1, 1, tzinfo=UTC)),
    ("seq", 7),
]


@pytest.mark.parametrize(("field", "forged_value"), FORGERIES, ids=[f for f, _ in FORGERIES])
def test_rewriting_any_field_of_a_record_is_detected(field: str, forged_value: Any):
    """ADR-0033: the hash covers the whole record, not only the payload hash."""
    store = Store()
    ledger = store.ledger()
    ledger.append(
        AuditEventType.APPROVAL_RECORDED,
        actor_ref="sup:ruwan",
        object_ref="plan:1",
        payload={"plan": 1, "amount_lkr": "12000.00"},
        case_id="CASE-A",
        detail={"amount_lkr": "12000.00"},
        session_ref="SES-1",
    )
    append_three(ledger)
    original = ledger.records[0]
    store.write(AUDIT, key(1), original.model_copy(update={field: forged_value}))

    result = ledger.verify()

    assert not result.intact, f"rewriting {field} went unnoticed"
    assert result.broken_at == 1


def test_removing_a_record_breaks_the_chain():
    store = Store()
    ledger = store.ledger()
    append_three(ledger)
    store.remove(AUDIT, key(2))

    assert not ledger.verify().intact


def test_removing_the_newest_records_is_detected_by_the_head():
    """The head pointer outlives a delete from the end of the table.

    An insider who also rewinds the head defeats this; signed checkpoints held
    outside the database are what catch that (audit assurance plan, Phase 2).
    """
    store = Store()
    ledger = store.ledger()
    append_three(ledger)
    store.remove(AUDIT, key(3))

    result = ledger.verify()

    assert not result.intact
    assert result.reason == "head does not match the chain"


def test_a_record_written_around_the_ledger_is_refused():
    """A row at the next sequence number that the head does not know about."""
    store = Store()
    ledger = store.ledger()
    append_three(ledger)
    store.write(AUDIT, key(4), ledger.records[2].model_copy(update={"seq": 4}))

    with pytest.raises(AppendOnlyViolation):
        ledger.append(
            AuditEventType.STAFF_ACTION,
            actor_ref="sup:ruwan",
            object_ref="x",
            payload={},
        )


def test_two_ledgers_on_one_store_write_one_chain():
    """The API and the MCP server share a store in ``full``: one trail, not two."""
    store = Store()
    api, mcp = store.ledger(), store.ledger()
    for turn in range(3):
        api.append(AuditEventType.DECISION_MADE, actor_ref="api", object_ref=f"D{turn}", payload={})
        mcp.append(AuditEventType.MCP_INVOKED, actor_ref="mcp", object_ref=f"M{turn}", payload={})

    records = api.records

    assert [r.seq for r in records] == list(range(1, 7))
    assert api.verify().intact and mcp.verify().intact
    assert api.head == mcp.head


def test_the_trail_outlives_the_ledger_object():
    """A restart builds a new ledger over the same store and finds the trail."""
    store = Store()
    append_three(store.ledger())

    reopened = store.ledger()

    assert len(reopened) == 3
    assert reopened.verify().intact


def test_a_clock_running_backwards_never_backdates_a_record():
    """Recorded times stay non-decreasing, so a backdated row stands out."""
    times = iter(
        [
            datetime(2026, 10, 4, 10, 0, tzinfo=UTC),
            datetime(2026, 10, 4, 9, 0, tzinfo=UTC),
        ]
    )
    ledger = AuditLedger(clock=lambda: next(times))

    ledger.append(
        AuditEventType.STAFF_ACTION,
        actor_ref="a",
        object_ref="1",
        payload={},
        now=datetime(2026, 10, 4, tzinfo=UTC),
    )
    ledger.append(
        AuditEventType.STAFF_ACTION,
        actor_ref="a",
        object_ref="2",
        payload={},
        now=datetime(2026, 10, 4, tzinfo=UTC),
    )

    first, second = ledger.records
    assert second.recorded_at >= first.recorded_at
    assert ledger.verify().intact


def test_a_backdated_record_is_detected():
    store = Store()
    ledger = store.ledger()
    append_three(ledger)
    third = ledger.records[2]
    earlier = ledger.records[1].recorded_at - timedelta(minutes=5)
    # Rehash it honestly, as an insider who knows the rule would, so the only
    # thing wrong with it is the time.
    from clarity.platform.audit.ledger import record_hash

    moved = third.model_copy(update={"recorded_at": earlier})
    moved = moved.model_copy(update={"chain_hash": record_hash(moved)})
    store.write(AUDIT, key(3), moved)
    store.write(AUDIT_HEAD, "head", {"seq": 3, "chain_hash": moved.chain_hash})

    result = ledger.verify()

    assert not result.intact
    assert result.reason == "recorded earlier than its predecessor"


def test_a_record_carries_its_actor_kind_and_session():
    ledger = AuditLedger()
    record: AuditRecord = ledger.append(
        AuditEventType.APPROVAL_RECORDED,
        actor_ref="sup:ruwan",
        object_ref="plan:1",
        payload={},
        session_ref="SES-1",
        actor_kind="staff",  # type: ignore[arg-type]
    )

    assert record.actor_kind == "staff"
    assert record.session_ref == "SES-1"
    assert record.hash_version == HASH_VERSION


def test_the_ledger_cannot_be_altered_through_its_public_api():
    ledger = AuditLedger()
    append_three(ledger)

    ledger.records.clear()

    assert len(ledger) == 3, "records property returns a copy"


def test_a_case_trail_can_be_exported():
    """What a regulator pack is built from (deck S9)."""
    ledger = AuditLedger()
    append_three(ledger)
    ledger.append(
        AuditEventType.DECISION_MADE,
        actor_ref="clarity-policy",
        object_ref="DEC-2",
        payload={"outcome": "EXPLAIN_ONLY"},
        case_id="CASE-2",
    )

    assert len(ledger.for_case("CASE-1")) == 3
    assert len(ledger.for_case("CASE-2")) == 1


def test_the_ledger_proves_a_document_without_storing_it():
    ledger = AuditLedger()
    payload = {"receipt_id": "TR-2027-000001", "amount_lkr": "49.00"}
    record = ledger.append(
        AuditEventType.RECEIPT_ISSUED,
        actor_ref="clarity-receipts",
        object_ref="TR-2027-000001",
        payload=payload,
    )

    assert ledger.proves(record, payload)
    assert not ledger.proves(record, {**payload, "amount_lkr": "4900.00"})


def test_the_head_moves_with_every_append():
    ledger = AuditLedger()
    assert ledger.head is None

    append_three(ledger)

    assert ledger.head == ledger.records[-1].chain_hash
