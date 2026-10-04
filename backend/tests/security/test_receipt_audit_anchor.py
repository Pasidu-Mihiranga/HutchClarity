"""Receipts witness the audit head (audit assurance plan Phase 2, ADR-0035).

Signed checkpoints make the trail tamper-evident, but an insider who can rewrite
the trail can also delete the stored checkpoints. The design therefore needs a
copy of the head somewhere Clarity cannot reach. The public witness endpoint is
one such place and depends on somebody having fetched it. Receipts are the other,
and the better one: they are *delivered*, to customers, at the moment money moves,
and nobody can collect them back.

The compatibility half of this matters as much as the feature. Adding a field to
a signed payload changes the hash of every receipt ever issued, which would break
the signature on receipts already in customers' hands. A receipt that verified
yesterday has to verify today.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from clarity.contracts.receipt import (
    SCHEMA_VERSION,
    ReceiptAuditAnchor,
    ReceiptPayload,
)
from clarity.modules.receipts.signing import DevSigningService
from clarity.platform.audit.checkpoints import Checkpointer, anchor_verifies
from clarity.platform.audit.ledger import AuditEventType, AuditLedger
from clarity.platform.persistence.memory import MemoryStore, MemoryUnitOfWork


@pytest.fixture
def checkpoints() -> Checkpointer:
    store = MemoryStore()

    def unit() -> MemoryUnitOfWork:
        return MemoryUnitOfWork(store)

    ledger = AuditLedger(unit)
    maker = Checkpointer(
        ledger,
        DevSigningService(kid="anchor-test"),
        unit,
        every_records=lambda: 1000,
        max_age=lambda: timedelta(days=1),
    )
    for index in range(4):
        ledger.append(
            AuditEventType.ACTION_EXECUTED,
            actor_ref="clarity",
            object_ref=f"plan:{index}",
            payload={},
        )
    maker.checkpoint()
    return maker


def anchor_from(checkpoints: Checkpointer) -> ReceiptAuditAnchor:
    latest = checkpoints.latest()
    assert latest is not None
    return ReceiptAuditAnchor(
        checkpoint_seq=latest.seq,
        chain_head=latest.chain_head,
        recorded_at=latest.recorded_at,
        statement_hash=latest.statement_hash,
        kid=latest.kid,
        signature=latest.signature,
    )


# --------------------------------------------------------------------------- #
# The anchor is a real, independently checkable witness
# --------------------------------------------------------------------------- #


def test_an_anchor_verifies_against_the_published_key(checkpoints: Checkpointer):
    """The holder needs nothing from Clarity but the public key."""
    assert anchor_verifies(anchor_from(checkpoints), checkpoints.public_keys())


def test_a_forged_sequence_number_does_not_ride_on_a_genuine_signature(
    checkpoints: Checkpointer,
):
    """Otherwise an anchor could claim any head with a signature copied from another.

    The statement hash binds the seq and the head together, and it is recomputed
    from the fields rather than trusted, which is what closes this.
    """
    forged = anchor_from(checkpoints).model_copy(update={"checkpoint_seq": 99_999})

    assert not anchor_verifies(forged, checkpoints.public_keys())


def test_a_forged_chain_head_is_caught(checkpoints: Checkpointer):
    forged = anchor_from(checkpoints).model_copy(update={"chain_head": "sha256:" + "0" * 64})

    assert not anchor_verifies(forged, checkpoints.public_keys())


def test_an_unknown_key_does_not_verify(checkpoints: Checkpointer):
    assert not anchor_verifies(anchor_from(checkpoints), {"someone-else": "AAAA"})


def test_a_tampered_signature_is_caught(checkpoints: Checkpointer):
    forged = anchor_from(checkpoints).model_copy(update={"signature": "AA" * 44})

    assert not anchor_verifies(forged, checkpoints.public_keys())


# --------------------------------------------------------------------------- #
# A receipt that verified yesterday verifies today
# --------------------------------------------------------------------------- #


def a_payload(**overrides: object) -> ReceiptPayload:
    from clarity.contracts.decision import ActionStatus, ActionType, Outcome
    from clarity.contracts.receipt import (
        ActorType,
        ReceiptActor,
        ReceiptCause,
        ReceiptDecision,
        ReceiptSubject,
    )

    base: dict[str, object] = {
        "receipt_id": "TR-2026-000001",
        "case_id": "CS-2026-0001",
        "issued_at": datetime(2026, 10, 4, 9, 0, tzinfo=UTC),
        "subject": ReceiptSubject(msisdn_masked="07X XXX 4567", subscriber_ref_hash="sha256:abc"),
        "what_happened": ReceiptCause(cause_rule="RP-VAS-001", rule_version=1, summary="x"),
        "decision": ReceiptDecision(
            decision_id="DEC-1",
            outcome=Outcome.AUTO_FIX,
            policy_version="1",
            input_hash="sha256:in",
        ),
        "actor": ReceiptActor(type=ActorType.SYSTEM_AUTO_FIX, system="clarity"),
    }
    assert ActionStatus and ActionType  # imported for the caller's convenience
    return ReceiptPayload(**(base | overrides))  # type: ignore[arg-type]


def test_a_schema_1_0_receipt_hashes_exactly_as_it_always_did(checkpoints: Checkpointer):
    """The compatibility rule, and the reason the schema version is read at all.

    A 1.0 payload never had an ``audit_anchor``. Hashing one *with* the field
    present as ``null`` would change its hash, which would break the signature on
    every receipt already issued and delivered.
    """
    old = a_payload(schema_version="1.0")
    # The hash a 1.0 receipt was signed with: the dump without the new key.
    from clarity.kernel.canonical import hash_payload

    document = old.model_dump(mode="json")
    document.pop("audit_anchor", None)

    assert old.compute_hash() == hash_payload(document)


def test_a_schema_1_0_receipt_ignores_an_anchor_even_if_one_is_set(
    checkpoints: Checkpointer,
):
    """Belt and braces: the version decides, not whether the field happens to be filled."""
    without = a_payload(schema_version="1.0")
    with_anchor = a_payload(schema_version="1.0", audit_anchor=anchor_from(checkpoints))

    assert without.compute_hash() == with_anchor.compute_hash()


def test_a_current_receipt_hashes_the_anchor_in(checkpoints: Checkpointer):
    """Otherwise carrying it would prove nothing: an unsigned field can be swapped."""
    without = a_payload()
    with_anchor = a_payload(audit_anchor=anchor_from(checkpoints))

    assert without.schema_version == SCHEMA_VERSION
    assert without.compute_hash() != with_anchor.compute_hash()


def test_changing_the_anchor_changes_the_hash(checkpoints: Checkpointer):
    anchor = anchor_from(checkpoints)
    one = a_payload(audit_anchor=anchor)
    other = a_payload(audit_anchor=anchor.model_copy(update={"checkpoint_seq": 7}))

    assert one.compute_hash() != other.compute_hash()


# --------------------------------------------------------------------------- #
# End to end, through the container
# --------------------------------------------------------------------------- #


def test_an_issued_receipt_carries_a_verifiable_anchor():
    from clarity.app.container import Clarity

    clarity = Clarity()
    anchor = clarity._current_audit_anchor()

    assert anchor is not None, "the container signs a checkpoint at startup"
    assert anchor_verifies(anchor, clarity.audit_checkpoints.public_keys())


def test_a_receipt_still_issues_when_the_anchor_cannot_be_read():
    """A customer is owed their proof whatever the audit side is doing.

    An absent anchor weakens the audit witness and must not weaken the receipt,
    and the absence is visible in the payload so nobody mistakes it for one that
    was checked.
    """
    from clarity.modules.receipts.service import ReceiptService

    def exploding() -> ReceiptAuditAnchor | None:
        raise RuntimeError("the checkpointer is unavailable")

    service = ReceiptService.__new__(ReceiptService)
    service._audit_anchor = exploding  # type: ignore[attr-defined]

    assert service._anchor() is None
