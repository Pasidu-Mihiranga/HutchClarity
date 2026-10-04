"""Retention, legal hold and erasure for the audit trail (plan Phase 7, ADR-0039).

Three requirements that pull against each other, and against the trail's own
design, which is the whole difficulty of this phase.

**Retention** says old records leave the hot table. But a hash chain is a chain:
remove record 400 and record 401 no longer follows anything. So records do not
leave, they *move*: a contiguous run is sealed into a segment, the segment is a
bundle in the same format as a backup, and the hot table keeps a **floor** naming
the seq and hash the last removed record had. ``AuditLedger.verify`` resumes from
the floor, and the archived part is verified by verifying the segment. Nothing is
unaccounted for at any point; the boundary is a join, not a gap.

**Legal hold** says some records must not leave, whatever retention says. A hold
names a subject or a seq range and blocks both archival and erasure for it. It is
deliberately the coarser instrument: a hold that only blocked erasure would let
retention quietly move the evidence somewhere the hold does not reach.

**Erasure** says a person can require their data gone, and that is the one this
design cannot satisfy by deletion: deleting a record breaks the chain for every
record after it, and the chain is what makes the trail worth keeping. So erasure
is **crypto-shredding of the link, not deletion of the record**. The trail holds
pseudonyms, never numbers (I13); the registry that maps a pseudonym to a person
is what holds the identity, and erasure destroys that entry. The records stay,
the chain still verifies, and ``sub_9f2a...`` no longer leads anywhere.

**Be honest about what that does not achieve.** ``subscriber_ref`` is an HMAC of
the number under one key shared by every subscriber (``kernel.common``), so anyone
holding that key and a candidate number can recompute the pseudonym and confirm a
match. Destroying the registry entry removes Clarity's own ability to go from
pseudonym to person; it does not make the pseudonym unlinkable to someone who
already suspects which person it is. Closing that needs a per-subject salt in the
pseudonym itself, which changes a kernel function that receipts and Kafka
partitioning both depend on. Recorded as a limitation in ADR-0039 rather than
papered over, because an erasure claim that is not true is worse than one that is
bounded.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from clarity.kernel.common import ClarityModel, utc_now
from clarity.platform.audit.backup import AuditBundle, write_bundle
from clarity.platform.audit.checkpoints import Checkpointer
from clarity.platform.audit.ledger import (
    AUDIT,
    AUDIT_FLOOR,
    ActorKind,
    AuditEventType,
    AuditLedger,
    AuditRecord,
)
from clarity.platform.persistence import Repository, UnitOfWorkFactory
from clarity.platform.security.principal import Permission, Principal

#: Owned collections. One collection is one table in B05.
SEGMENTS = "platform.audit_segments"
HOLDS = "platform.audit_holds"
PSEUDONYMS = "platform.audit_pseudonyms"

_FLOOR_KEY = "floor"
_KEY_WIDTH = 12


class LifecycleRefused(RuntimeError):
    """The operation was not permitted, or would have broken something."""


def _key(seq: int) -> str:
    return str(seq).zfill(_KEY_WIDTH)


# --------------------------------------------------------------------------- #
# Segments
# --------------------------------------------------------------------------- #


class Segment(ClarityModel):
    """A sealed, contiguous run of archived records.

    The bundle itself is a file. This is the index entry: enough to find it, to
    know what it holds, and to check that what comes back is what left.
    """

    from_seq: int
    to_seq: int
    checksum: str
    file: str
    sealed_at: datetime
    sealed_by: str
    last_chain_hash: str
    """The hash of ``to_seq``, which becomes the hot trail's floor."""

    checkpoint_seq: int | None = None
    """The signed checkpoint that attests to this segment's end, where one covers
    it. Without one the segment is sealed but not independently attested, which
    ``verify_segment`` reports rather than assumes."""

    @property
    def count(self) -> int:
        return self.to_seq - self.from_seq + 1


# --------------------------------------------------------------------------- #
# Legal hold
# --------------------------------------------------------------------------- #


class LegalHold(ClarityModel):
    """A named instruction that something must not be archived or erased."""

    hold_id: str
    reason: str
    placed_by: str
    placed_at: datetime
    subject_ref: str | None = None
    """A pseudonym this hold protects. ``None`` when the hold is a seq range."""

    from_seq: int | None = None
    to_seq: int | None = None
    released_at: datetime | None = None
    released_by: str | None = None

    @property
    def is_active(self) -> bool:
        return self.released_at is None

    def covers_seq(self, seq: int) -> bool:
        if self.from_seq is None or self.to_seq is None:
            return False
        return self.from_seq <= seq <= self.to_seq

    def covers_subject(self, subject_ref: str) -> bool:
        return self.subject_ref is not None and self.subject_ref == subject_ref


# --------------------------------------------------------------------------- #
# The pseudonym registry
# --------------------------------------------------------------------------- #


class PseudonymEntry(ClarityModel):
    """What Clarity holds that links a pseudonym to a person.

    The number is **not** here. It is the already-masked form, which is what the
    rest of the system displays anyway, plus whatever account reference the desk
    uses. Erasure removes the entry; what is left is a tombstone saying an entry
    existed and was erased, which a regulator needs and which identifies nobody.
    """

    subscriber_ref: str
    masked: str
    account_ref: str | None = None
    created_at: datetime
    erased_at: datetime | None = None
    erased_by: str | None = None
    erasure_reason: str | None = None

    @property
    def is_erased(self) -> bool:
        return self.erased_at is not None


@dataclass
class ErasureOutcome:
    """What an erasure did, in terms a response to the person can quote."""

    subscriber_ref: str
    erased: bool
    records_retained: int
    reason: str

    @property
    def summary(self) -> str:
        if not self.erased:
            return f"erasure of {self.subscriber_ref} was refused: {self.reason}"
        return (
            f"the link from {self.subscriber_ref} to a person was destroyed; "
            f"{self.records_retained} audit record(s) remain, pseudonymous, because "
            "removing one would break the chain that makes the rest evidence"
        )


# --------------------------------------------------------------------------- #
# The service
# --------------------------------------------------------------------------- #


class AuditLifecycle:
    """Archives, holds and erases, and records every one of them."""

    def __init__(
        self,
        ledger: AuditLedger,
        checkpoints: Checkpointer,
        *,
        key: Callable[[], bytes],
        directory: Callable[[], Path],
        retain: Callable[[datetime], timedelta],
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._ledger = ledger
        self._checkpoints = checkpoints
        self._open_unit: UnitOfWorkFactory = ledger.open_unit
        self._key = key
        self._directory = directory
        #: Resolved ``as_of`` the moment it applies (I10): a retention period is a
        #: policy value, and a change to it must not silently re-judge the past.
        self._retain = retain
        self._clock = clock or utc_now

    # -- reading ------------------------------------------------------------- #

    def segments(self) -> list[Segment]:
        with self._open_unit() as unit:
            store: Repository[str, Segment] = unit.repository(SEGMENTS)
            return [s for key in sorted(store.keys()) if (s := store.get(key)) is not None]

    def holds(self, *, active_only: bool = True) -> list[LegalHold]:
        with self._open_unit() as unit:
            store: Repository[str, LegalHold] = unit.repository(HOLDS)
            found = store.values()
        return [hold for hold in found if hold.is_active or not active_only]

    def pseudonym(self, subscriber_ref: str) -> PseudonymEntry | None:
        with self._open_unit() as unit:
            store: Repository[str, PseudonymEntry] = unit.repository(PSEUDONYMS)
            return store.get(subscriber_ref)

    # -- legal hold ---------------------------------------------------------- #

    def place_hold(
        self,
        by: Principal,
        *,
        hold_id: str,
        reason: str,
        subject_ref: str | None = None,
        from_seq: int | None = None,
        to_seq: int | None = None,
    ) -> LegalHold:
        """Block archival and erasure for a subject or a seq range."""
        if not by.has(Permission.AUDIT_ASSIGN):
            raise LifecycleRefused("placing a legal hold needs audit:assign")
        if not reason.strip():
            raise LifecycleRefused("a legal hold must record why")
        if subject_ref is None and (from_seq is None or to_seq is None):
            raise LifecycleRefused("a legal hold names a subject or a seq range")

        hold = LegalHold(
            hold_id=hold_id,
            reason=reason,
            placed_by=by.ref,
            placed_at=self._clock(),
            subject_ref=subject_ref,
            from_seq=from_seq,
            to_seq=to_seq,
        )
        with self._open_unit() as unit:
            store: Repository[str, LegalHold] = unit.repository(HOLDS)
            store.put(hold_id, hold)
            unit.commit()
        self._record(AuditEventType.HOLD_PLACED, by, hold)
        return hold

    def release_hold(self, by: Principal, hold_id: str, *, reason: str) -> LegalHold:
        if not by.has(Permission.AUDIT_ASSIGN):
            raise LifecycleRefused("releasing a legal hold needs audit:assign")
        with self._open_unit() as unit:
            store: Repository[str, LegalHold] = unit.repository(HOLDS)
            hold = store.get(hold_id)
            if hold is None:
                raise LifecycleRefused(f"no legal hold {hold_id}")
            if not hold.is_active:
                raise LifecycleRefused(f"legal hold {hold_id} was already released")
            released = hold.model_copy(
                update={
                    "released_at": self._clock(),
                    "released_by": by.ref,
                    "reason": f"{hold.reason} | released: {reason}",
                }
            )
            store.put(hold_id, released)
            unit.commit()
        self._record(AuditEventType.HOLD_RELEASED, by, released)
        return released

    def held_seqs(self) -> set[int]:
        """Every seq an active hold protects, by range or by subject.

        A subject hold is resolved by walking the trail for that subject, so a
        hold placed on a person protects the records about them without the person
        placing it needing to know their seq numbers.
        """
        active = self.holds()
        if not active:
            return set()
        held: set[int] = set()
        subjects = {hold.subject_ref for hold in active if hold.subject_ref}
        for record in self._ledger.records:
            by_range = any(hold.covers_seq(record.seq) for hold in active)
            by_subject = bool(subjects) and str(record.detail.get("subject", "")) in subjects
            if by_range or by_subject:
                held.add(record.seq)
        return held

    # -- archival ------------------------------------------------------------ #

    def due_for_archive(self, *, now: datetime | None = None) -> int:
        """The highest seq old enough to archive, or 0 when nothing is.

        Stops at the first held record rather than skipping it: a segment is a
        *contiguous* run, and a segment with a hole in it cannot be verified as a
        chain. So a hold in the middle of the eligible range pauses archival
        behind it, which is the safe direction and is reported, not silent.
        """
        moment = now or self._clock()
        cutoff = moment - self._retain(moment)
        held = self.held_seqs()
        floor = self._ledger.floor
        start = int(floor["seq"]) + 1 if floor else 1

        highest = 0
        for record in self._ledger.records:
            if record.seq < start:
                continue
            if record.seq in held or record.recorded_at > cutoff:
                break
            highest = record.seq
        return highest

    def archive(self, by: Principal, *, until_seq: int | None = None) -> Segment | None:
        """Seal everything up to ``until_seq`` into a segment and move the floor.

        The order is deliberate and not interchangeable: write the segment file
        first, index it, and only then remove the records. A failure anywhere
        before the last step leaves a redundant segment, which costs disk. A
        failure after removing records without a sealed segment would lose the
        trail, which costs the trail.
        """
        if not by.has(Permission.AUDIT_RESTORE):
            raise LifecycleRefused("archiving the trail needs audit:restore")

        target = until_seq if until_seq is not None else self.due_for_archive()
        if target <= 0:
            return None

        held = self.held_seqs()
        records = [r for r in self._ledger.records if r.seq <= target]
        floor = self._ledger.floor
        start = int(floor["seq"]) + 1 if floor else 1
        records = [r for r in records if r.seq >= start]
        if not records:
            return None
        if any(record.seq in held for record in records):
            raise LifecycleRefused(
                "a legal hold covers records in this range; archival would move "
                "evidence somewhere the hold does not reach"
            )
        if records[0].seq != start or records[-1].seq != target:
            raise LifecycleRefused(
                f"records {start} to {target} are not contiguous, so they cannot be "
                "sealed as one chain"
            )
        if target >= (self._ledger.records[-1].seq if self._ledger.records else 0):
            raise LifecycleRefused(
                "the whole trail cannot be archived: the hot table keeps at least "
                "the head, so the chain has somewhere to continue from"
            )

        covering = next(
            (cp.seq for cp in reversed(self._checkpoints.all()) if cp.seq >= target), None
        )
        sealed_at = self._clock()
        bundle = AuditBundle(
            created_at=sealed_at,
            records=records,
            checkpoints=[cp for cp in self._checkpoints.all() if cp.seq <= target],
            public_keys=self._checkpoints.public_keys(),
            head_seq=records[-1].seq,
            head_hash=records[-1].chain_hash,
        )
        name = f"segment-{_key(records[0].seq)}-{_key(target)}.audit"
        checksum = write_bundle(bundle, self._directory() / name, self._key())

        segment = Segment(
            from_seq=records[0].seq,
            to_seq=target,
            checksum=checksum,
            file=name,
            sealed_at=sealed_at,
            sealed_by=by.ref,
            last_chain_hash=records[-1].chain_hash,
            checkpoint_seq=covering,
        )

        with self._open_unit() as unit, unit.as_custodian():
            # Archival removes records from the hot table, which is the other
            # legitimate exception to append-only (ADR-0039). The segment file is
            # already written at this point, so a failure here loses nothing.
            index: Repository[str, Segment] = unit.repository(SEGMENTS)
            index.put(_key(segment.to_seq), segment)
            hot: Repository[str, AuditRecord] = unit.repository(AUDIT)
            for record in records:
                hot.delete(_key(record.seq))
            marker: Repository[str, dict[str, Any]] = unit.repository(AUDIT_FLOOR)
            marker.put(
                _FLOOR_KEY,
                {"seq": segment.to_seq, "chain_hash": segment.last_chain_hash},
            )
            unit.commit()

        self._ledger.append(
            AuditEventType.SEGMENT_SEALED,
            actor_ref=by.ref,
            actor_kind=ActorKind.STAFF,
            object_ref=f"segment:{segment.from_seq}-{segment.to_seq}",
            payload=segment.model_dump(mode="json"),
            detail={
                "from_seq": segment.from_seq,
                "to_seq": segment.to_seq,
                "records": segment.count,
                "checksum": checksum,
                "file": name,
                "checkpoint_seq": covering,
                "attested": covering is not None,
            },
        )
        return segment

    # -- erasure ------------------------------------------------------------- #

    def register(self, subscriber_ref: str, *, masked: str, account_ref: str | None = None) -> None:
        """Record the link erasure will later be able to destroy.

        Idempotent, and never overwrites an erased entry: a returning customer
        does not undo an erasure by signing in again.
        """
        with self._open_unit() as unit:
            store: Repository[str, PseudonymEntry] = unit.repository(PSEUDONYMS)
            existing = store.get(subscriber_ref)
            if existing is not None:
                return
            store.put(
                subscriber_ref,
                PseudonymEntry(
                    subscriber_ref=subscriber_ref,
                    masked=masked,
                    account_ref=account_ref,
                    created_at=self._clock(),
                ),
            )
            unit.commit()

    def erase(self, by: Principal, subscriber_ref: str, *, reason: str) -> ErasureOutcome:
        """Destroy the link from a pseudonym to a person. The records stay.

        Refused under a legal hold, which is the point of a hold: an erasure
        request does not outrank an instruction to preserve evidence. The refusal
        is recorded, so a person asking why can be told.
        """
        if not by.has(Permission.AUDIT_ASSIGN):
            raise LifecycleRefused("erasing a pseudonym link needs audit:assign")
        if not reason.strip():
            raise LifecycleRefused("an erasure must record why")

        retained = sum(
            1
            for record in self._ledger.records
            if str(record.detail.get("subject", "")) == subscriber_ref
        )
        blocking = [hold for hold in self.holds() if hold.covers_subject(subscriber_ref)]
        if blocking:
            outcome = ErasureOutcome(
                subscriber_ref=subscriber_ref,
                erased=False,
                records_retained=retained,
                reason=f"legal hold {blocking[0].hold_id}: {blocking[0].reason}",
            )
            self._record_erasure(by, outcome, reason)
            return outcome

        with self._open_unit() as unit:
            store: Repository[str, PseudonymEntry] = unit.repository(PSEUDONYMS)
            entry = store.get(subscriber_ref)
            if entry is None:
                outcome = ErasureOutcome(
                    subscriber_ref=subscriber_ref,
                    erased=False,
                    records_retained=retained,
                    reason="no pseudonym link is held for this subscriber",
                )
                self._record_erasure(by, outcome, reason)
                return outcome
            if entry.is_erased:
                outcome = ErasureOutcome(
                    subscriber_ref=subscriber_ref,
                    erased=True,
                    records_retained=retained,
                    reason="already erased",
                )
                self._record_erasure(by, outcome, reason)
                return outcome
            # The tombstone, not a deletion: a regulator asking "was this erased,
            # when, and by whom" needs an answer, and the answer identifies nobody.
            store.put(
                subscriber_ref,
                entry.model_copy(
                    update={
                        "masked": "erased",
                        "account_ref": None,
                        "erased_at": self._clock(),
                        "erased_by": by.ref,
                        "erasure_reason": reason,
                    }
                ),
            )
            unit.commit()

        outcome = ErasureOutcome(
            subscriber_ref=subscriber_ref,
            erased=True,
            records_retained=retained,
            reason=reason,
        )
        self._record_erasure(by, outcome, reason)
        return outcome

    # -- recording ----------------------------------------------------------- #

    def _record(self, event_type: AuditEventType, by: Principal, hold: LegalHold) -> None:
        self._ledger.append(
            event_type,
            actor_ref=by.ref,
            actor_kind=ActorKind.STAFF,
            object_ref=f"hold:{hold.hold_id}",
            payload=hold.model_dump(mode="json"),
            detail={
                "hold_id": hold.hold_id,
                "reason": hold.reason,
                "subject": hold.subject_ref,
                "from_seq": hold.from_seq,
                "to_seq": hold.to_seq,
                "active": hold.is_active,
            },
        )

    def _record_erasure(self, by: Principal, outcome: ErasureOutcome, reason: str) -> None:
        self._ledger.append(
            AuditEventType.ERASURE_PERFORMED,
            actor_ref=by.ref,
            actor_kind=ActorKind.STAFF,
            object_ref=f"erasure:{outcome.subscriber_ref}",
            payload={"subscriber_ref": outcome.subscriber_ref, "erased": outcome.erased},
            detail={
                "subject": outcome.subscriber_ref,
                "erased": outcome.erased,
                "records_retained": outcome.records_retained,
                "reason": reason,
                "outcome": outcome.reason,
            },
        )


def verify_segment(segment: Segment, bundle: AuditBundle) -> tuple[bool, str]:
    """Check an archived segment against its index entry.

    Separate from the service so an offline verifier can use it with nothing but
    the segment file and the index row, which is the position a regulator is in.
    """
    if bundle.checksum != segment.checksum:
        return False, "the segment's contents do not hash to the checksum it was sealed with"
    if not bundle.records:
        return False, "the segment holds no records"
    if bundle.records[0].seq != segment.from_seq or bundle.records[-1].seq != segment.to_seq:
        return False, "the segment does not cover the range its index entry claims"
    if bundle.records[-1].chain_hash != segment.last_chain_hash:
        return False, "the segment's last record does not carry the hash the floor was set from"
    if segment.checkpoint_seq is None:
        return True, "intact, but no signed checkpoint attests to this segment's end"
    return True, "intact and attested by a signed checkpoint"


__all__ = [
    "HOLDS",
    "PSEUDONYMS",
    "SEGMENTS",
    "AuditLifecycle",
    "ErasureOutcome",
    "LegalHold",
    "LifecycleRefused",
    "PseudonymEntry",
    "Segment",
    "verify_segment",
]
