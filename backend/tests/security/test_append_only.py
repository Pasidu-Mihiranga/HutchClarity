"""The audit tables only ever grow (audit assurance plan W1, ADR-0034).

Two layers, and the difference between them is the whole point.

**The application cannot overwrite an audit row.** The write path for an
append-only collection plainly inserts, so there is no code path through Clarity
that replaces a record. That is what these tests cover, in the memory store, in
`lite`, where they can run anywhere.

**The database will not let it either.** The migration takes `UPDATE` and
`DELETE` away from the writing role and gives `DELETE` to a separate custodian
role for restore and archival. That is covered in
`tests/integration/test_append_only_grants.py`, which needs PostgreSQL.

Neither replaces the hash chain. The chain is what catches someone who goes
around both, by writing to the table directly, and the tamper tests in
`test_events_and_audit.py` and `test_audit_checkpoints.py` still do exactly that
through the named `as_custodian` span.
"""

from __future__ import annotations

import pytest

from clarity.platform.audit.ledger import AUDIT, AUDIT_HEAD, AuditEventType, AuditLedger
from clarity.platform.persistence.memory import AppendOnlyWrite, MemoryStore, MemoryUnitOfWork
from clarity.platform.persistence.schemas import APPEND_ONLY, is_append_only


@pytest.fixture
def store() -> MemoryStore:
    return MemoryStore()


@pytest.fixture
def ledger(store: MemoryStore) -> AuditLedger:
    return AuditLedger(lambda: MemoryUnitOfWork(store))


def test_the_audit_tables_are_the_append_only_ones():
    """Named explicitly, so adding a collection here is a decision, not a drift."""
    assert "platform.audit" in APPEND_ONLY
    assert "platform.audit_checkpoints" in APPEND_ONLY
    assert "platform.audit_segments" in APPEND_ONLY


def test_the_pointers_are_deliberately_not_append_only():
    """A head pointer moves by design; an append-only pointer is a contradiction.

    They hold no history, only the current position, and a wrong pointer is
    detectable because the chain it points into is not.
    """
    assert not is_append_only(AUDIT_HEAD)
    assert not is_append_only("platform.audit_floor")


def test_an_audit_record_cannot_be_overwritten(store: MemoryStore, ledger: AuditLedger):
    ledger.append(
        AuditEventType.STAFF_ACTION, actor_ref="sup:ruwan", object_ref="plan:1", payload={}
    )
    first = ledger.records[0]

    with MemoryUnitOfWork(store) as unit, pytest.raises(AppendOnlyWrite) as raised:
        unit.repository(AUDIT).put(
            str(first.seq).zfill(12), first.model_copy(update={"actor_ref": "agent:nadeesha"})
        )

    assert raised.value.collection == AUDIT
    assert ledger.records[0].actor_ref == "sup:ruwan", "and nothing changed"


def test_appending_still_works(ledger: AuditLedger):
    """The guard must not be so strict that the trail cannot grow."""
    for index in range(5):
        ledger.append(
            AuditEventType.STAFF_ACTION,
            actor_ref="sup:ruwan",
            object_ref=f"plan:{index}",
            payload={"i": index},
        )

    assert len(ledger) == 5
    assert ledger.verify().intact


def test_an_ordinary_collection_is_still_updatable(store: MemoryStore):
    """Append-only is for the trail, not a new rule for everything."""
    with MemoryUnitOfWork(store) as unit:
        unit.repository("case.records").put("CS-1", {"v": 1})
        unit.commit()
    with MemoryUnitOfWork(store) as unit:
        unit.repository("case.records").put("CS-1", {"v": 2})
        unit.commit()

    with MemoryUnitOfWork(store) as unit:
        assert unit.repository("case.records").get("CS-1") == {"v": 2}


def test_the_head_pointer_is_still_updatable(store: MemoryStore, ledger: AuditLedger):
    """It moves on every append, so the guard must leave it alone."""
    for index in range(3):
        ledger.append(
            AuditEventType.STAFF_ACTION,
            actor_ref="sup:ruwan",
            object_ref=f"plan:{index}",
            payload={},
        )

    assert ledger.head == ledger.records[-1].chain_hash


def test_the_custodian_span_is_the_named_way_through(store: MemoryStore, ledger: AuditLedger):
    """Restore and archival rewrite audit rows legitimately, and say so.

    The span exists so the privilege is visible at the call site and greppable,
    rather than being an accident of whether a delete happened to be staged first.
    """
    ledger.append(
        AuditEventType.STAFF_ACTION, actor_ref="sup:ruwan", object_ref="plan:1", payload={}
    )
    first = ledger.records[0]

    with MemoryUnitOfWork(store) as unit, unit.as_custodian():
        unit.repository(AUDIT).put(
            str(first.seq).zfill(12), first.model_copy(update={"actor_ref": "restored"})
        )
        unit.commit()

    assert ledger.records[0].actor_ref == "restored"


def test_the_custodian_span_closes_behind_itself(store: MemoryStore, ledger: AuditLedger):
    """A bounded privilege, or it is not a privilege."""
    ledger.append(
        AuditEventType.STAFF_ACTION, actor_ref="sup:ruwan", object_ref="plan:1", payload={}
    )
    first = ledger.records[0]
    key = str(first.seq).zfill(12)

    with MemoryUnitOfWork(store) as unit:
        with unit.as_custodian():
            unit.repository(AUDIT).put(key, first.model_copy(update={"actor_ref": "a"}))
        with pytest.raises(AppendOnlyWrite):
            unit.repository(AUDIT).put(key, first.model_copy(update={"actor_ref": "b"}))


def test_a_restore_still_works_through_the_guard(tmp_path):
    """The end to end check: the operation the span exists for must still run."""
    from datetime import UTC, datetime, timedelta

    from clarity.modules.receipts.signing import DevSigningService
    from clarity.platform.audit.backup import backup_key_from
    from clarity.platform.audit.checkpoints import Checkpointer
    from clarity.platform.audit.vault import AuditVault
    from clarity.platform.security.principal import Assurance, Permission, Principal, Role

    store = MemoryStore()

    def unit() -> MemoryUnitOfWork:
        return MemoryUnitOfWork(store)

    clock = lambda: datetime(2026, 10, 4, 9, 0, tzinfo=UTC)  # noqa: E731
    ledger = AuditLedger(unit, clock=clock)
    checkpoints = Checkpointer(
        ledger,
        DevSigningService(kid="append-only-test"),
        unit,
        every_records=lambda: 1000,
        max_age=lambda: timedelta(days=1),
        clock=clock,
    )
    vault = AuditVault(ledger, checkpoints, key=lambda: backup_key_from("k"), clock=clock)
    operator = Principal(
        ref="admin:kamal",
        roles=frozenset({Role.PLATFORM_ADMIN}),
        assurance=Assurance.MFA_RECENT,
        granted=frozenset({Permission.AUDIT_EXPORT, Permission.AUDIT_RESTORE}),
    )
    for index in range(5):
        ledger.append(
            AuditEventType.STAFF_ACTION,
            actor_ref="sup:ruwan",
            object_ref=f"plan:{index}",
            payload={},
        )
    path = tmp_path / "t.backup"
    vault.back_up(operator, path)
    ledger.append(
        AuditEventType.STAFF_ACTION, actor_ref="sup:ruwan", object_ref="plan:later", payload={}
    )

    report = vault.restore(operator, path, accept_loss=True)

    assert report.restored_to_seq == 5
    assert ledger.verify().intact
