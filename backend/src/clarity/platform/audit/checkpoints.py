"""Signed audit checkpoints (audit assurance plan, Phase 2; ADR-0035).

A hash chain detects an *edit*. It cannot detect a *rewrite*: someone who can
write every row, and the head pointer, can recompute a chain that verifies, or
cut the newest records off the end and rewind the head to match. A checkpoint
closes that. It is a signature over ``(seq, chain_head, recorded_at)`` made with
a key the database does not hold, so forging one needs the signing key, not
table access, and a trail that no longer reaches a checkpoint's ``seq`` or no
longer has that head at that ``seq`` fails verification with the exact range.

**Infrastructure: none new.** The signer is the same kind as the Trust
Receipts' (OpenBao Transit in ``full``, a local Ed25519 key in ``lite``) with a
**separate key**, so a compromise of one does not forge the other.

This module is ``platform`` (L2): it cannot import the receipts module's
signer, so it declares the three methods it needs as a protocol, and verifies
Ed25519 itself from public material only, exactly as an outside verifier would.
"""

from __future__ import annotations

import base64
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Protocol

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from clarity.kernel.canonical import hash_payload
from clarity.kernel.common import ClarityModel, utc_now
from clarity.platform.audit.ledger import AuditEventType, AuditLedger, AuditRecord
from clarity.platform.persistence import Repository, UnitOfWorkFactory

#: One collection is one table in B05.
AUDIT_CHECKPOINTS = "platform.audit_checkpoints"

_KEY_WIDTH = 12


class CheckpointSigner(Protocol):
    """What a checkpoint needs from a signer. The receipt signers satisfy it."""

    def sign(self, payload_hash: str) -> tuple[str, str]: ...

    def public_keys(self) -> dict[str, str]: ...


class Checkpoint(ClarityModel):
    """A signed statement: the trail had reached ``seq`` with head ``chain_head``."""

    seq: int
    chain_head: str
    recorded_at: datetime
    statement_hash: str
    kid: str
    signature: str


def statement_hash(seq: int, chain_head: str, recorded_at: datetime) -> str:
    """What is signed. A purpose label keeps it from being mistaken for a receipt hash."""
    return hash_payload(
        {
            "purpose": "clarity.audit.checkpoint",
            "seq": seq,
            "chain_head": chain_head,
            "recorded_at": recorded_at.isoformat(),
        }
    )


def signature_valid(checkpoint: Checkpoint, public_keys: dict[str, str]) -> bool:
    """Check one checkpoint against published public keys. Nothing secret needed."""
    encoded = public_keys.get(checkpoint.kid)
    if encoded is None:
        return False
    try:
        public = Ed25519PublicKey.from_public_bytes(base64.b64decode(encoded))
        public.verify(
            base64.b64decode(checkpoint.signature),
            checkpoint.statement_hash.encode("utf-8"),
        )
    except (InvalidSignature, ValueError):
        return False
    return True


@dataclass
class CheckpointVerification:
    """The trail checked against its chain **and** its signed checkpoints."""

    intact: bool
    length: int
    checkpoints: int
    last_checkpoint_seq: int | None = None
    broken_at: int | None = None
    reason: str | None = None
    lost_from: int | None = None
    """First ``seq`` a checkpoint proves existed and the trail no longer holds."""
    lost_to: int | None = None


def _key(seq: int) -> str:
    return str(seq).zfill(_KEY_WIDTH)


class Checkpointer:
    """Signs the trail's head on a schedule and verifies the trail against it.

    ``every_records`` and ``max_age`` are callables so the composition root can
    resolve them from the policy store at the moment they apply (I10); this
    module holds no threshold of its own.
    """

    def __init__(
        self,
        ledger: AuditLedger,
        signer: CheckpointSigner,
        open_unit: UnitOfWorkFactory,
        *,
        every_records: Callable[[], int],
        max_age: Callable[[], timedelta],
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._ledger = ledger
        self._signer = signer
        self._open_unit = open_unit
        self._every_records = every_records
        self._max_age = max_age
        self._clock = clock or utc_now
        self._lock = threading.Lock()

    # -- issuing ------------------------------------------------------------ #

    def checkpoint(self) -> Checkpoint | None:
        """Sign the current head now, unless it is already checkpointed."""
        with self._lock:
            records = self._ledger.records
            if not records:
                return None
            last = self.latest()
            head = records[-1]
            if last is not None and last.seq >= head.seq:
                return None
            return self._issue(head)

    def maybe_checkpoint(self) -> Checkpoint | None:
        """Checkpoint if enough records, or enough time, has passed since the last."""
        records = self._ledger.records
        if not records:
            return None
        last = self.latest()
        head = records[-1]
        if last is None:
            return self.checkpoint()
        unsigned = head.seq - last.seq
        if unsigned <= 0:
            return None
        if unsigned >= self._every_records() or self._clock() - last.recorded_at >= self._max_age():
            return self.checkpoint()
        return None

    def _issue(self, head: AuditRecord) -> Checkpoint:
        recorded_at = self._clock()
        digest = statement_hash(head.seq, head.chain_hash, recorded_at)
        kid, signature = self._signer.sign(digest)
        checkpoint = Checkpoint(
            seq=head.seq,
            chain_head=head.chain_hash,
            recorded_at=recorded_at,
            statement_hash=digest,
            kid=kid,
            signature=signature,
        )
        with self._open_unit() as unit:
            store: Repository[str, Checkpoint] = unit.repository(AUDIT_CHECKPOINTS)
            store.put(_key(checkpoint.seq), checkpoint)
            unit.commit()
        # The checkpoint is itself an event in the trail. Recording it moves
        # the head on by one, which the next checkpoint covers.
        self._ledger.append(
            AuditEventType.CHECKPOINT_ISSUED,
            actor_ref="clarity-audit",
            object_ref=f"checkpoint:{checkpoint.seq}",
            payload=checkpoint.model_dump(mode="json"),
            detail={"seq": checkpoint.seq, "kid": kid, "chain_head": checkpoint.chain_head},
        )
        return checkpoint

    # -- reading ------------------------------------------------------------ #

    def all(self) -> list[Checkpoint]:
        with self._open_unit() as unit:
            store: Repository[str, Checkpoint] = unit.repository(AUDIT_CHECKPOINTS)
            return [cp for key in sorted(store.keys()) if (cp := store.get(key)) is not None]

    def latest(self) -> Checkpoint | None:
        found = self.all()
        return found[-1] if found else None

    def public_keys(self) -> dict[str, str]:
        return self._signer.public_keys()

    # -- verifying ------------------------------------------------------------ #

    def verify(self, *, witness: Checkpoint | None = None) -> CheckpointVerification:
        """The chain, every stored checkpoint, and optionally one held elsewhere.

        ``witness`` is a checkpoint obtained from outside the database: the
        public endpoint's copy someone saved, or one embedded in a receipt.
        It is what catches an insider who deleted the checkpoints as well.
        """
        records = self._ledger.records
        chain = self._ledger.verify()
        checkpoints = self.all()
        if witness is not None and all(cp.seq != witness.seq for cp in checkpoints):
            checkpoints = sorted([*checkpoints, witness], key=lambda cp: cp.seq)
        keys = self.public_keys()
        result = CheckpointVerification(
            intact=chain.intact,
            length=len(records),
            checkpoints=len(checkpoints),
            last_checkpoint_seq=checkpoints[-1].seq if checkpoints else None,
            broken_at=chain.broken_at,
            reason=chain.reason,
        )
        if not chain.intact:
            return result

        # Every checkpoint must be genuine before any of them is used as proof:
        # a forged checkpoint with a large seq must not inflate a loss report.
        for cp in checkpoints:
            if cp.statement_hash != statement_hash(cp.seq, cp.chain_head, cp.recorded_at):
                return _fail(result, cp.seq, "checkpoint statement does not match its fields")
            if not signature_valid(cp, keys):
                return _fail(result, cp.seq, f"checkpoint signature does not verify (kid {cp.kid})")
        for cp in checkpoints:
            if cp.seq <= len(records) and records[cp.seq - 1].chain_hash != cp.chain_head:
                return _fail(result, cp.seq, "trail was rewritten before a signed checkpoint")
        beyond = [cp.seq for cp in checkpoints if cp.seq > len(records)]
        if beyond:
            # The *highest* checkpoint is the proof of how far the trail
            # reached. Stopping at the first one past the end would understate
            # the loss, which is the one thing a loss report must not do.
            failed = _fail(result, len(records) + 1, "trail is shorter than a signed checkpoint")
            failed.lost_from = len(records) + 1
            failed.lost_to = max(beyond)
            return failed
        return result


def _fail(result: CheckpointVerification, at: int, reason: str) -> CheckpointVerification:
    result.intact = False
    result.broken_at = at
    result.reason = reason
    return result


def checkpoint_document(checkpoint: Checkpoint, public_keys: dict[str, str]) -> dict[str, Any]:
    """What the public endpoint serves: enough for anyone to verify and keep."""
    return {
        **checkpoint.model_dump(mode="json"),
        "public_key": public_keys.get(checkpoint.kid),
        "algorithm": "Ed25519",
        "signed": "UTF-8 bytes of statement_hash",
    }


__all__ = [
    "AUDIT_CHECKPOINTS",
    "Checkpoint",
    "CheckpointSigner",
    "CheckpointVerification",
    "Checkpointer",
    "checkpoint_document",
    "signature_valid",
    "statement_hash",
]
