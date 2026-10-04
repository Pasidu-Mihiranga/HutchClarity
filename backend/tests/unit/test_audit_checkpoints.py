"""Signed audit checkpoints (audit assurance plan Phase 2, ADR-0035).

Each test is an attack a hash chain alone cannot see, staged the way an insider
with full write access to the database would stage it: recompute the chain
honestly, rewind the head, delete the stored checkpoints. The chain verifies
every time; the checkpoints, signed with a key the database does not hold, are
what fail.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from itertools import pairwise
from typing import Any

import pytest

from clarity.app.container import AuditChainBroken, Clarity
from clarity.integration.drivers.mock.world import build_demo_world
from clarity.modules.receipts.signing import DevSigningService
from clarity.platform.audit.checkpoints import (
    AUDIT_CHECKPOINTS,
    Checkpoint,
    Checkpointer,
    statement_hash,
)
from clarity.platform.audit.ledger import (
    AUDIT,
    AUDIT_HEAD,
    AuditEventType,
    AuditLedger,
    record_hash,
)
from clarity.platform.persistence.memory import MemoryStore, MemoryUnitOfWork


class World:
    """A ledger, its checkpointer and the store behind them, for playing the insider."""

    def __init__(self, *, every: int = 1000) -> None:
        self.store = MemoryStore()
        self.ledger = AuditLedger(self.unit)
        self.signer = DevSigningService(kid="audit-test-1")
        self.checkpoints = Checkpointer(
            self.ledger,
            self.signer,
            self.unit,
            every_records=lambda: every,
            max_age=lambda: timedelta(days=1),
        )
        self.ledger.after_append(lambda _record: self.checkpoints.maybe_checkpoint())

    def unit(self) -> MemoryUnitOfWork:
        return MemoryUnitOfWork(self.store)

    def append(self, n: int) -> None:
        for i in range(n):
            self.ledger.append(
                AuditEventType.STAFF_ACTION,
                actor_ref="sup:ruwan",
                object_ref=f"plan:{i}",
                payload={"i": i},
            )

    def put(self, collection: str, key: str, value: Any) -> None:
        """Write around the application, as the insider these tests stage.

        ``as_custodian`` because the ordinary path refuses to overwrite an audit
        row (W1). These tests are about what remains detectable when someone has
        table access regardless.
        """
        with self.unit() as unit, unit.as_custodian():
            unit.repository(collection).put(key, value)
            unit.commit()

    def delete(self, collection: str, key: str) -> None:
        with self.unit() as unit:
            unit.repository(collection).delete(key)
            unit.commit()

    def rewind_head_to(self, seq: int) -> None:
        """Delete every record after ``seq`` and point the head at ``seq``."""
        records = self.ledger.records
        for record in records[seq:]:
            self.delete(AUDIT, str(record.seq).zfill(12))
        last = records[seq - 1]
        self.put(AUDIT_HEAD, "head", {"seq": last.seq, "chain_hash": last.chain_hash})


def key(seq: int) -> str:
    return str(seq).zfill(12)


def test_an_untouched_trail_verifies_against_its_checkpoints():
    world = World(every=5)
    world.append(12)

    result = world.checkpoints.verify()

    assert result.intact, result.reason
    assert result.checkpoints >= 2


def test_checkpoints_follow_the_policy_interval():
    world = World(every=5)
    world.append(12)

    seqs = [cp.seq for cp in world.checkpoints.all()]
    issued = world.ledger.of_type(AuditEventType.CHECKPOINT_ISSUED)

    assert seqs[0] == 1, "the first record is checkpointed at once"
    assert all(b - a <= 6 for a, b in pairwise(seqs))
    assert len(issued) == len(seqs), "every checkpoint is itself in the trail"


def test_rewriting_the_whole_trail_consistently_is_caught():
    """The attack a chain cannot see: every hash recomputed honestly."""
    world = World(every=3)
    world.append(6)
    assert world.ledger.verify().intact

    previous: str | None = None
    for record in world.ledger.records:
        changed = record.model_copy(update={"actor_ref": "agent:nadeesha", "prev_hash": previous})
        changed = changed.model_copy(update={"chain_hash": record_hash(changed)})
        world.put(AUDIT, key(changed.seq), changed)
        previous = changed.chain_hash
    world.put(AUDIT_HEAD, "head", {"seq": len(world.ledger.records), "chain_hash": previous})

    assert world.ledger.verify().intact, "the chain alone is fooled"
    result = world.checkpoints.verify()
    assert not result.intact
    assert result.reason == "trail was rewritten before a signed checkpoint"


def test_cutting_the_newest_records_reports_exactly_what_was_lost():
    world = World(every=4)
    world.append(10)
    last_checkpoint = world.checkpoints.latest()
    assert last_checkpoint is not None

    world.rewind_head_to(3)

    assert world.ledger.verify().intact, "the chain alone is fooled"
    result = world.checkpoints.verify()
    assert not result.intact
    assert result.lost_from == 4
    assert result.lost_to == last_checkpoint.seq


def test_deleting_the_checkpoints_too_is_caught_by_a_witness():
    """Why the latest checkpoint is published: a copy outside the database."""
    world = World(every=4)
    world.append(10)
    witness = world.checkpoints.latest()
    assert witness is not None

    world.rewind_head_to(3)
    for checkpoint in world.checkpoints.all():
        world.delete(AUDIT_CHECKPOINTS, key(checkpoint.seq))

    assert world.checkpoints.verify().intact, "with no checkpoints left, nothing objects"
    result = world.checkpoints.verify(witness=witness)
    assert not result.intact
    assert result.lost_to == witness.seq


def test_a_checkpoint_forged_without_the_key_is_refused():
    world = World(every=1000)
    world.append(3)
    head = world.ledger.records[-1]
    impostor = DevSigningService(kid="audit-test-1")  # same kid, different key
    at = datetime(2026, 10, 4, tzinfo=UTC)
    digest = statement_hash(head.seq, head.chain_hash, at)
    _, signature = impostor.sign(digest)
    world.put(
        AUDIT_CHECKPOINTS,
        key(head.seq),
        Checkpoint(
            seq=head.seq,
            chain_head=head.chain_hash,
            recorded_at=at,
            statement_hash=digest,
            kid="audit-test-1",
            signature=signature,
        ),
    )

    result = world.checkpoints.verify()

    assert not result.intact
    assert "signature does not verify" in (result.reason or "")


def test_a_rotated_key_still_verifies_old_checkpoints():
    world = World(every=3)
    world.append(4)
    world.signer.rotate("audit-test-2")
    world.append(4)

    kids = {cp.kid for cp in world.checkpoints.all()}

    assert kids == {"audit-test-1", "audit-test-2"}
    assert world.checkpoints.verify().intact


def test_the_checkpoint_key_is_not_the_receipt_key(clarity: Clarity):
    """A compromise of one must not forge the other (ADR-0035)."""
    assert set(clarity.audit_checkpoints.public_keys()).isdisjoint(clarity.signing.public_keys())


@pytest.fixture
def clarity() -> Clarity:
    return Clarity(world=build_demo_world())


def test_a_trail_cut_below_its_checkpoint_stops_startup(clarity: Clarity):
    for i in range(5):
        clarity.audit.append(
            AuditEventType.STAFF_ACTION, actor_ref="a", object_ref=str(i), payload={}
        )
    clarity.audit_checkpoints.checkpoint()
    records = clarity.audit.records
    with clarity.audit.open_unit() as unit:
        for record in records[2:]:
            unit.repository(AUDIT).delete(key(record.seq))
        unit.repository(AUDIT_HEAD).put(
            "head", {"seq": records[1].seq, "chain_hash": records[1].chain_hash}
        )
        unit.commit()

    with pytest.raises(AuditChainBroken, match="shorter than a signed checkpoint"):
        Clarity(
            world=build_demo_world(),
            audit=clarity.audit,
            audit_checkpoints=clarity.audit_checkpoints,
        )


def test_the_latest_checkpoint_is_public(clarity: Clarity):
    from fastapi.testclient import TestClient

    from clarity.interfaces.http.main import create_app

    api = TestClient(create_app(clarity))

    response = api.get("/.well-known/clarity-audit-checkpoint.json")

    assert response.status_code == 200
    body = response.json()
    assert body["algorithm"] == "Ed25519"
    assert body["public_key"]
    published = Checkpoint.model_validate({k: body[k] for k in Checkpoint.model_fields})
    assert clarity.audit_checkpoints.verify(witness=published).intact


# --------------------------------------------------------------------------- #
# Incremental verification (audit assurance plan, Phase 2 deferral)
# --------------------------------------------------------------------------- #


def test_an_incremental_check_starts_above_the_newest_checkpoint():
    world = World(every=5)
    world.append(12)
    latest = world.checkpoints.latest()
    assert latest is not None

    result = world.checkpoints.verify(incremental=True)

    assert result.intact, result.reason
    assert result.verified_from == latest.seq, "it anchors on the newest checkpoint"
    assert result.verified_from > 1, "and does not recompute from record 1"


def test_an_incremental_check_catches_a_truncated_trail():
    """The live question a heartbeat asks, and the one this answers."""
    world = World(every=100)
    world.append(20)
    world.checkpoints.checkpoint()
    world.rewind_head_to(10)

    result = world.checkpoints.verify(incremental=True)

    assert not result.intact
    assert result.reason is not None


def test_an_incremental_check_catches_an_edit_at_its_own_anchor():
    """The anchor row is recomputed, not just hash-compared.

    Without that, editing the anchor and leaving its stored hash alone would
    pass: nothing above the anchor depends on the anchor's contents, only on
    the hash it claims to have.
    """
    world = World(every=100)
    world.append(20)
    checkpoint = world.checkpoints.checkpoint()
    assert checkpoint is not None
    anchor = next(r for r in world.ledger.records if r.seq == checkpoint.seq)
    world.put(AUDIT, key(anchor.seq), anchor.model_copy(update={"actor_ref": "agent:nadeesha"}))

    result = world.checkpoints.verify(incremental=True)

    assert not result.intact
    assert result.broken_at == anchor.seq


def test_an_incremental_check_does_not_see_an_edit_below_its_anchor():
    """The documented boundary of the optimisation, pinned so nobody assumes more.

    Record 3 is rewritten and only its own ``chain_hash`` recomputed. Records 4
    upward still carry the ``prev_hash`` they always had, so the hash at the
    anchor is untouched and the dangling link sits below everything an
    incremental check recomputes. The **full** check is what catches this, and
    the assertion that it does is the other half of this test.
    """
    world = World(every=100)
    world.append(20)
    world.checkpoints.checkpoint()
    victim = world.ledger.records[2]
    forged = victim.model_copy(update={"actor_ref": "agent:nadeesha"})
    world.put(AUDIT, key(victim.seq), forged.model_copy(update={"chain_hash": record_hash(forged)}))

    incremental = world.checkpoints.verify(incremental=True)
    full = world.checkpoints.verify()

    assert incremental.intact, "the documented limitation, not a regression"
    assert not full.intact, "the full recompute is the tamper check"
    assert full.broken_at == victim.seq + 1


def test_an_incremental_check_does_not_trust_a_forged_checkpoint_as_its_anchor():
    """A forged checkpoint must not become the point verification starts from.

    Otherwise the attack writes itself: rewrite the trail, forge a checkpoint
    over the new head, and every later check skips the rewritten records.
    """
    world = World(every=100)
    world.append(10)
    honest = world.checkpoints.checkpoint()
    assert honest is not None

    # Rewrite the whole trail consistently, then forge a checkpoint over the
    # new head without the signing key.
    records = world.ledger.records
    victim = records[1]
    forged_record = victim.model_copy(update={"case_id": "CS-FORGED"})
    forged_record = forged_record.model_copy(update={"chain_hash": record_hash(forged_record)})
    world.put(AUDIT, key(victim.seq), forged_record)
    previous = forged_record
    for record in records[2:]:
        relinked = record.model_copy(update={"prev_hash": previous.chain_hash})
        relinked = relinked.model_copy(update={"chain_hash": record_hash(relinked)})
        world.put(AUDIT, key(relinked.seq), relinked)
        previous = relinked
    world.put(AUDIT_HEAD, "head", {"seq": previous.seq, "chain_hash": previous.chain_hash})
    world.put(
        AUDIT_CHECKPOINTS,
        key(previous.seq),
        Checkpoint(
            seq=previous.seq,
            chain_head=previous.chain_hash,
            recorded_at=datetime(2026, 10, 4, tzinfo=UTC),
            statement_hash=statement_hash(
                previous.seq, previous.chain_hash, datetime(2026, 10, 4, tzinfo=UTC)
            ),
            kid="audit-test-1",
            signature="AA" * 32,
        ),
    )

    result = world.checkpoints.verify(incremental=True)

    assert not result.intact, "a forged checkpoint must not vouch for the trail"
    assert result.verified_from == 1, "and must not become the anchor"


def test_an_incremental_check_falls_back_to_the_full_chain_with_no_checkpoint():
    ledger = AuditLedger()
    checkpoints = Checkpointer(
        ledger,
        DevSigningService(kid="audit-test-1"),
        ledger.open_unit,
        every_records=lambda: 1000,
        max_age=lambda: timedelta(days=1),
    )
    ledger.append(
        AuditEventType.STAFF_ACTION, actor_ref="sup:ruwan", object_ref="plan:1", payload={}
    )

    result = checkpoints.verify(incremental=True)

    assert result.intact, result.reason
    assert result.verified_from == 1


def test_an_incremental_verify_needs_the_hash_it_starts_from():
    ledger = AuditLedger()
    ledger.append(
        AuditEventType.STAFF_ACTION, actor_ref="sup:ruwan", object_ref="plan:1", payload={}
    )

    with pytest.raises(ValueError, match="needs the hash"):
        ledger.verify(since=1)


def test_an_incremental_verify_reports_a_missing_anchor():
    ledger = AuditLedger()
    ledger.append(
        AuditEventType.STAFF_ACTION, actor_ref="sup:ruwan", object_ref="plan:1", payload={}
    )

    result = ledger.verify(since=9, since_hash="whatever")

    assert not result.intact
    assert result.broken_at == 9
