"""The destroy-and-restore drill against a real PostgreSQL (plan Phase 6).

`tests/security/test_audit_recovery.py` proves the logic against the memory
store. This proves it against the store a deployment actually uses, which is
where the differences live: real transactions, a real head pointer in a real
row, and a delete that is a `DELETE` rather than a dictionary `pop`.

A drill that only ever runs in memory is a drill against a model of the system.
This one runs in the `full` CI lane on every merge, and skips without a database
so `make check` stays infrastructure-free (ADR-0006).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from clarity.app.collections import ALL_COLLECTIONS
from clarity.modules.receipts.signing import DevSigningService
from clarity.platform.audit.backup import backup_key_from
from clarity.platform.audit.checkpoints import AUDIT_CHECKPOINTS, Checkpointer
from clarity.platform.audit.ledger import AUDIT, AUDIT_HEAD, AuditEventType, AuditLedger
from clarity.platform.audit.vault import AuditVault
from clarity.platform.persistence.postgres import PostgresStore
from clarity.platform.security.principal import Assurance, Permission, Principal, Role

KEY = backup_key_from("a-drill-key-not-a-secret")

OPERATOR = Principal(
    ref="admin:kamal",
    roles=frozenset({Role.PLATFORM_ADMIN}),
    assurance=Assurance.MFA_RECENT,
    granted=frozenset({Permission.AUDIT_EXPORT, Permission.AUDIT_RESTORE}),
)


class Frozen:
    def __init__(self) -> None:
        self.now = datetime(2026, 10, 4, 9, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, by: timedelta) -> None:
        self.now += by


@pytest.fixture
def trail(store: PostgresStore):
    clock = Frozen()
    ledger = AuditLedger(store.unit, clock=clock)
    checkpoints = Checkpointer(
        ledger,
        DevSigningService(kid="audit-drill"),
        store.unit,
        every_records=lambda: 1000,
        max_age=lambda: timedelta(days=1),
        clock=clock,
    )
    vault = AuditVault(ledger, checkpoints, key=lambda: KEY, clock=clock)
    return clock, ledger, checkpoints, vault


def test_the_checkpoint_collection_has_a_table() -> None:
    """It was missing from the registry, so `full` had nowhere to put a checkpoint.

    A memory store makes a collection on first use, so the gap was invisible
    until something asked PostgreSQL for the table.
    """
    assert AUDIT_CHECKPOINTS in ALL_COLLECTIONS


def test_a_trail_destroyed_in_postgres_comes_back_whole(tmp_path: Path, trail) -> None:
    clock, ledger, checkpoints, vault = trail
    for index in range(15):
        ledger.append(
            AuditEventType.STAFF_ACTION,
            actor_ref="sup:ruwan",
            object_ref=f"plan:{index}",
            payload={"i": index},
            detail={"amount_lkr": "900.00"},
        )
        clock.advance(timedelta(seconds=1))
    witness = checkpoints.checkpoint()
    assert witness is not None
    path = tmp_path / "drill.backup"
    bundle = vault.back_up(OPERATOR, path)
    before = [record.chain_hash for record in ledger.records]

    with store_unit(ledger) as unit:
        for collection in (AUDIT, AUDIT_CHECKPOINTS, AUDIT_HEAD):
            repository = unit.repository(collection)
            for key in list(repository.keys()):
                repository.delete(key)
        unit.commit()
    assert len(ledger) == 0, "the tables are empty"

    report = vault.restore(OPERATOR, path, witness=witness, accept_loss=True)

    assert ledger.verify().intact, report.summary
    covered = bundle.covers[1]
    assert [r.chain_hash for r in ledger.records if r.seq <= covered] == before[:covered]
    assert ledger.of_type(AuditEventType.RESTORE_PERFORMED)


def store_unit(ledger: AuditLedger):
    return ledger.open_unit()
