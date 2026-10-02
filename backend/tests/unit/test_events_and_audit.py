"""Audit ledger tests (plan section 20.3).

The outbox, the relay and the consumer framework moved to
``test_outbox_wiring.py`` when B04 split them apart, and per-subject ordering is
covered for every bus driver by ``tests/contract/test_bus_parity.py``.
"""

from __future__ import annotations

from clarity.platform.audit.ledger import AuditEventType, AuditLedger
from clarity.platform.messaging.envelope import Event, EventType

from ..support.events import SAMPLES


def an_event(type_: EventType = EventType.ACTION_COMPLETED, subject: str = "sub_a") -> Event:
    return Event.of(SAMPLES[type_], subject=subject)


# --------------------------------------------------------------------------- #
# Audit ledger
# --------------------------------------------------------------------------- #


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
    ledger = AuditLedger()
    append_three(ledger)
    tampered = ledger.records
    tampered[1] = tampered[1].model_copy(update={"payload_hash": "sha256:forged"})
    ledger._records = tampered  # simulate a privileged edit

    result = ledger.verify()

    assert not result.intact
    assert result.broken_at == 2


def test_removing_a_record_breaks_the_chain():
    ledger = AuditLedger()
    append_three(ledger)
    ledger._records = [ledger.records[0], ledger.records[2]]

    assert not ledger.verify().intact


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
