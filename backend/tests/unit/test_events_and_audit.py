"""Event outbox and audit ledger tests (plan §18.4, §20.3)."""

from __future__ import annotations

from clarity.platform.audit.ledger import AuditEventType, AuditLedger
from clarity.platform.messaging.envelope import Event, EventType
from clarity.platform.messaging.outbox import Outbox


def an_event(type_: EventType = EventType.ACTION_COMPLETED, subject: str = "sub_a") -> Event:
    return Event(type=type_, subject=subject, data={"amount_lkr": "49.00"})


# --------------------------------------------------------------------------- #
# Outbox
# --------------------------------------------------------------------------- #


def test_appending_publishes_nothing_until_the_relay_runs():
    """The whole point of an outbox: the write happens first."""
    outbox = Outbox()
    outbox.append(an_event())

    assert outbox.published == []
    assert len(outbox.pending) == 1


def test_relay_delivers_to_subscribers():
    outbox = Outbox()
    seen: list[Event] = []
    outbox.subscribe(EventType.ACTION_COMPLETED, "receipts", seen.append)
    outbox.append(an_event())

    assert outbox.relay() == 1
    assert len(seen) == 1


def test_a_consumer_ignores_a_redelivered_event():
    """At-least-once delivery must not issue two receipts for one action."""
    outbox = Outbox()
    seen: list[Event] = []
    outbox.subscribe(EventType.ACTION_COMPLETED, "receipts", seen.append)
    event = an_event()

    outbox.append(event)
    outbox.relay()
    outbox.append(event)
    outbox.relay()

    assert len(seen) == 1, "the duplicate was ignored"
    assert outbox.stats("receipts").duplicates == 1


def test_a_failing_consumer_does_not_stop_the_others():
    outbox = Outbox()
    delivered: list[str] = []

    def broken(_: Event) -> None:
        raise RuntimeError("downstream is down")

    outbox.subscribe(EventType.ACTION_COMPLETED, "broken", broken)
    outbox.subscribe(EventType.ACTION_COMPLETED, "working", lambda e: delivered.append(e.id))
    outbox.append(an_event())
    outbox.relay()

    assert delivered, "the healthy consumer still received it"


def test_a_failed_delivery_is_retried_then_dead_lettered():
    outbox = Outbox(max_attempts=2)

    def broken(_: Event) -> None:
        raise RuntimeError("still down")

    outbox.subscribe(EventType.ACTION_COMPLETED, "broken", broken)
    outbox.append(an_event())

    outbox.relay()
    assert outbox.pending, "retried, not dropped"
    outbox.relay()

    assert outbox.dead_letters, "gives up after max_attempts"


def test_a_stuck_critical_event_is_surfaced_not_buried():
    """A lost receipt or action must page a human, not sit in a DLQ."""
    outbox = Outbox(max_attempts=1)
    outbox.subscribe(
        EventType.RECEIPT_ISSUED, "broken", lambda _: (_ for _ in ()).throw(RuntimeError("x"))
    )
    outbox.append(an_event(EventType.RECEIPT_ISSUED))
    outbox.relay()

    assert outbox.undelivered_critical


def test_per_subject_ordering_is_preserved():
    outbox = Outbox()
    order: list[str] = []
    for type_ in (EventType.CASE_CREATED, EventType.DECISION_GENERATED, EventType.ACTION_COMPLETED):
        outbox.subscribe(type_, "recorder", lambda e: order.append(e.type.value))
        outbox.append(an_event(type_))

    outbox.relay()

    assert order == ["case.created", "decision.generated", "action.completed"]


def test_a_derived_event_keeps_the_trace():
    first = an_event(EventType.ACTION_COMPLETED)

    second = first.caused(EventType.RECEIPT_ISSUED, receipt_id="TR-2027-000001")

    assert second.causation_id == first.id
    assert second.correlation_id == first.id
    assert second.subject == first.subject


def test_a_trace_can_be_reassembled_from_one_request():
    outbox = Outbox()
    first = outbox.append(an_event(EventType.CASE_CREATED))
    outbox.append(first.caused(EventType.DECISION_GENERATED))
    outbox.append(first.caused(EventType.RECEIPT_ISSUED))
    outbox.relay()

    assert len(outbox.trace(first.id)) == 3


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
