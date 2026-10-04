"""Append-only, hash-chained audit ledger (deck S8, plan §20.3-20.4).

"Every decision affecting customers or money must be auditable." The ledger is
what makes that checkable rather than asserted: each record is hashed, and each
hash includes its predecessor's, so altering or removing an old record breaks
every record after it. Verification needs nothing but the ledger itself.

**Record hash version 2 (ADR-0033).** Version 1 hashed only the payload hash
and the previous hash, so the fields an investigation depends on sat outside
the chain: rewriting a record's approver, event type, case, timestamp or
displayed detail left ``verify()`` reporting the chain intact. Version 2 hashes
the canonical form of the **whole** record, with the human-readable ``detail``
bound through ``detail_hash``. No version 1 record was ever persisted, so there
is nothing to migrate.

**One persisted trail (ADR-0034).** Records live behind the persistence port
(B02), so the ``full`` profile keeps them in PostgreSQL and every process that
writes, the API, the MCP server and the workers, appends to the same chain. An
append reads the head pointer and writes a fresh key in one unit of work, so
two writers racing for the same sequence number cannot both commit: the loser
gets ``ConcurrentUpdate`` and retries on the new head. Nothing updates or
deletes a record.

What gets recorded is listed in plan §20.4 and in the audit assurance plan
(``docs/audit-assurance-plan.md`` section 5.5).
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field

from clarity.kernel.canonical import hash_payload
from clarity.kernel.common import ClarityModel, utc_now
from clarity.platform.persistence import ConcurrentUpdate, Repository, UnitOfWorkFactory
from clarity.platform.persistence.memory import MemoryStore, MemoryUnitOfWork

#: Collections the trail lives in. One collection is one table in B05.
AUDIT = "platform.audit"
AUDIT_HEAD = "platform.audit_head"

#: The rule ``record_hash`` follows. Bumped, never edited (ADR-0033).
HASH_VERSION = 2

_HEAD_KEY = "head"
#: Zero-padded so the store's insertion order and key order agree.
_KEY_WIDTH = 12
#: Retries when another writer took the sequence number first.
_APPEND_ATTEMPTS = 8


class AuditEventType(StrEnum):
    """The auditable moments (plan §20.4)."""

    EVIDENCE_COLLECTED = "evidence.collected"
    CAUSE_ASSESSED = "cause.assessed"
    DECISION_MADE = "decision.made"
    PLAN_PROPOSED = "plan.proposed"
    APPROVAL_RECORDED = "approval.recorded"
    ACTION_EXECUTED = "action.executed"
    ACTION_COMPENSATED = "action.compensated"
    RECEIPT_ISSUED = "receipt.issued"
    MCP_INVOKED = "mcp.invoked"
    STAFF_ACTION = "staff.action"
    OVERRIDE_RECORDED = "override.recorded"
    RULE_PUBLISHED = "rule.published"
    TURN_RECORDED = "turn.recorded"
    """One assistant turn: flow state, tools, chunks, model and verifier
    result (C01, plan 22 section 4 step 11). Never the message text."""

    EVENT_PUBLISHED = "event.published"
    """A domain event with no more specific audit type. ``object_ref`` names
    the event type, so nothing published on the bus goes unrecorded."""

    DEMO_RESET = "demo.reset"
    """The synthetic world was reset. The trail itself is carried across."""

    LEDGER_OPENED = "ledger.opened"
    """A process opened the trail and verified it, or started under break-glass."""

    # -- identity and access (audit assurance plan W2) ------------------- #

    OTP_REQUESTED = "otp.requested"
    """A sign-in code was asked for, including for a number with no account."""

    OTP_VERIFIED = "otp.verified"
    """A correct code: a customer session began."""

    OTP_FAILED = "otp.failed"
    """A wrong, expired or reused code. The raw material of brute force."""

    STAFF_SESSION_STARTED = "staff.session_started"
    """A staff session began, with the roles and step-up it asserted."""

    TOKEN_REFRESHED = "token.refreshed"
    TOKEN_REJECTED = "token.rejected"
    """A presented token or refresh token was refused: forged, expired, reused
    or revoked. An anonymous request with no token is not recorded."""

    ACCESS_DENIED = "access.denied"
    """A signed-in caller was refused (403): who, what route, and why."""

    # -- audit access (audit assurance plan Phase 3) ---------------------- #

    GRANT_REQUESTED = "grant.requested"
    GRANT_APPROVED = "grant.approved"
    GRANT_REVOKED = "grant.revoked"
    GRANT_RECERTIFIED = "grant.recertified"
    GRANT_EXPIRED = "grant.expired"
    """An active grant reached its expiry. ``occurred_at`` is that moment."""
    GRANT_LAPSED = "grant.lapsed"
    """An active grant nobody recertified in time. ``occurred_at`` is its review deadline."""
    BREAK_GLASS_USED = "grant.break_glass"
    """An admin self-granted an audit duty for an incident. Always a signal."""

    AUDIT_READ = "audit.read"
    """Someone read the trail: who watched the watchers (rule 5)."""

    CHECKPOINT_ISSUED = "checkpoint.issued"
    """The head was signed with the checkpoint key (Phase 2, ADR-0035)."""

    REQUEST_PERFORMED = "request.performed"
    """A state-changing request reached its route: who made it, with which
    session, on which route and case, and the status it got. Domain events say
    what happened; this says who asked for it, which events cannot (an
    approval's event names a mode, ``staff_approved``, not the approver)."""


class ActorKind(StrEnum):
    """Who did it, at the level an investigation filters on first."""

    CUSTOMER = "customer"
    STAFF = "staff"
    SYSTEM = "system"
    AGENT = "agent"


class AuditRecord(ClarityModel):
    """One immutable entry. ``chain_hash`` binds every field to everything before it."""

    seq: int
    hash_version: int = HASH_VERSION
    event_type: AuditEventType
    actor_ref: str
    actor_kind: ActorKind = ActorKind.SYSTEM
    session_ref: str | None = None
    object_ref: str
    case_id: str | None = None
    payload_hash: str

    #: Masked detail for a human reading the trail. Never raw PII.
    detail: dict[str, Any] = Field(default_factory=dict)
    detail_hash: str

    occurred_at: datetime
    """When the thing happened, as the caller states it."""

    recorded_at: datetime
    """When the ledger recorded it, from the ledger's own clock. Non-decreasing
    along the chain, so a backdated record shows."""

    prev_hash: str | None
    chain_hash: str

    @property
    def at(self) -> datetime:
        """When the record was written. Kept for readers written against v1."""
        return self.recorded_at


def record_hash(record: AuditRecord) -> str:
    """The version 2 hash: every field except the hash itself (ADR-0033).

    ``detail`` is represented by ``detail_hash`` so the hash input stays a
    fixed shape; ``verify`` separately checks that the two agree.
    """
    return hash_payload(
        {
            "hash_version": record.hash_version,
            "seq": record.seq,
            # ``str()`` rather than ``.value``: a row edited in the database
            # holds a plain string, and verification must judge it, not crash.
            "event_type": str(record.event_type),
            "actor_ref": record.actor_ref,
            "actor_kind": str(record.actor_kind),
            "session_ref": record.session_ref,
            "object_ref": record.object_ref,
            "case_id": record.case_id,
            "payload_hash": record.payload_hash,
            "detail_hash": record.detail_hash,
            "occurred_at": record.occurred_at.isoformat(),
            "recorded_at": record.recorded_at.isoformat(),
            "prev_hash": record.prev_hash or "genesis",
        }
    )


@dataclass
class ChainVerification:
    intact: bool
    length: int
    broken_at: int | None = None
    reason: str | None = None


class AppendOnlyViolation(RuntimeError):
    """Something tried to change or remove an existing record."""


class AuditUnavailable(RuntimeError):
    """The trail could not be written after every retry.

    Raised rather than swallowed: a state change that cannot be audited must
    not happen (ADR-0034), so the caller's operation fails with it.
    """


def hashable(value: Any) -> Any:
    """Render floats as exact decimal strings so a value hashes canonically.

    The canonical hasher refuses floats on purpose: money is never a float (I3).
    Audit payloads and details still carry measurements that are, such as a
    confidence score, so the ledger renders them with ``repr`` (exact and
    round-trippable) instead of weakening the guard for everyone. The detail is
    *stored* in this rendered form, so verification recomputes the same hash.
    """
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, dict):
        return {key: hashable(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [hashable(item) for item in value]
    return value


def _key(seq: int) -> str:
    return str(seq).zfill(_KEY_WIDTH)


def _private_store() -> UnitOfWorkFactory:
    store = MemoryStore()
    return lambda: MemoryUnitOfWork(store)


class AuditLedger:
    """Append-only ledger with a verifiable hash chain.

    ``open_unit`` is the persistence seam: the composition root passes the
    profile's driver. With none, the ledger keeps a private in-memory store,
    which is what unit tests use.
    """

    def __init__(
        self,
        open_unit: UnitOfWorkFactory | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._open_unit = open_unit or _private_store()
        self._clock = clock or utc_now
        self._after_append: list[Callable[[AuditRecord], object]] = []
        # Serialises appends inside one process, so the common case never
        # needs the retry. Across processes the head pointer does that job.
        self._lock = threading.Lock()

    def append(
        self,
        event_type: AuditEventType,
        *,
        actor_ref: str,
        object_ref: str,
        payload: dict[str, Any],
        case_id: str | None = None,
        detail: dict[str, Any] | None = None,
        now: datetime | None = None,
        actor_kind: ActorKind = ActorKind.SYSTEM,
        session_ref: str | None = None,
    ) -> AuditRecord:
        """Add a record. The payload is hashed, not stored in the clear.

        Hooks run after the lock is released, so a hook may append (a
        checkpoint records itself) without deadlocking.
        """
        detail = hashable(detail or {})
        payload_hash = hash_payload(hashable(payload))
        detail_hash = hash_payload(detail)
        occurred_at = now or self._clock()

        record = self._append_with_retry(
            event_type=event_type,
            actor_ref=actor_ref,
            actor_kind=actor_kind,
            session_ref=session_ref,
            object_ref=object_ref,
            case_id=case_id,
            payload_hash=payload_hash,
            detail=detail,
            detail_hash=detail_hash,
            occurred_at=occurred_at,
        )
        for hook in list(self._after_append):
            hook(record)
        return record

    def after_append(self, hook: Callable[[AuditRecord], object]) -> None:
        """Run ``hook`` after every append, such as a checkpoint schedule."""
        self._after_append.append(hook)

    @property
    def open_unit(self) -> UnitOfWorkFactory:
        """The store the trail lives in, for state that must live beside it."""
        return self._open_unit

    def _append_with_retry(self, **fields: Any) -> AuditRecord:
        event_type: AuditEventType = fields["event_type"]
        with self._lock:
            for _ in range(_APPEND_ATTEMPTS):
                try:
                    return self._append_once(**fields)
                except ConcurrentUpdate:
                    # Another process took this sequence number. Read the new
                    # head and try again; the chain stays one line.
                    continue
        raise AuditUnavailable(
            f"could not append {event_type.value} after {_APPEND_ATTEMPTS} attempts"
        )

    def _append_once(self, **fields: Any) -> AuditRecord:
        with self._open_unit() as unit:
            heads: Repository[str, dict[str, Any]] = unit.repository(AUDIT_HEAD)
            records: Repository[str, AuditRecord] = unit.repository(AUDIT)
            head: dict[str, Any] | None = heads.get(_HEAD_KEY)
            seq = (head["seq"] if head else 0) + 1
            prev_hash = head["chain_hash"] if head else None
            previous = records.get(_key(seq - 1)) if head else None

            if records.get(_key(seq)) is not None:
                # The head says seq is free and the table says otherwise: two
                # writers forked the chain, or someone wrote around the ledger.
                raise AppendOnlyViolation(f"sequence {seq} already holds a record")

            recorded_at = self._clock()
            if previous is not None and recorded_at < previous.recorded_at:
                # A clock that runs backwards would make honest records look
                # backdated. Hold the line at the previous record's time.
                recorded_at = previous.recorded_at

            draft = AuditRecord(
                seq=seq,
                prev_hash=prev_hash,
                recorded_at=recorded_at,
                chain_hash="",
                **fields,
            )
            record = draft.model_copy(update={"chain_hash": record_hash(draft)})
            records.put(_key(seq), record)
            heads.put(_HEAD_KEY, {"seq": seq, "chain_hash": record.chain_hash})
            unit.commit()
            return record

    # ------------------------------------------------------------------ #
    # Reading
    # ------------------------------------------------------------------ #

    def _all(self) -> list[AuditRecord]:
        with self._open_unit() as unit:
            records: Repository[str, AuditRecord] = unit.repository(AUDIT)
            found: list[AuditRecord] = [
                value for key in sorted(records.keys()) if (value := records.get(key)) is not None
            ]
            return found

    def __len__(self) -> int:
        with self._open_unit() as unit:
            return len(unit.repository(AUDIT).keys())

    @property
    def records(self) -> list[AuditRecord]:
        """A copy: callers cannot reach in and alter the ledger."""
        return self._all()

    @property
    def head(self) -> str | None:
        """Current chain head, which signed checkpoints anchor (Phase 2)."""
        with self._open_unit() as unit:
            heads: Repository[str, dict[str, Any]] = unit.repository(AUDIT_HEAD)
            head = heads.get(_HEAD_KEY)
            return str(head["chain_hash"]) if head else None

    def for_case(self, case_id: str) -> list[AuditRecord]:
        """The full trail for one case - what a regulator pack exports."""
        return [r for r in self._all() if r.case_id == case_id]

    def of_type(self, event_type: AuditEventType) -> list[AuditRecord]:
        return [r for r in self._all() if r.event_type is event_type]

    # ------------------------------------------------------------------ #
    # Verifying
    # ------------------------------------------------------------------ #

    def verify(self) -> ChainVerification:
        """Recompute the whole chain. Any edit, deletion or reordering shows up here."""
        records = self._all()
        previous: AuditRecord | None = None
        for index, record in enumerate(records):
            seq = record.seq

            def broken(reason: str, at: int = seq) -> ChainVerification:
                return ChainVerification(False, len(records), at, reason)

            if seq != index + 1:
                return broken("sequence numbers are not contiguous", index + 1)
            if record.hash_version != HASH_VERSION:
                return broken(f"unknown record hash version {record.hash_version}")
            if record.prev_hash != (previous.chain_hash if previous else None):
                return broken("record does not follow its predecessor")
            if hash_payload(record.detail) != record.detail_hash:
                return broken("detail does not match its hash")
            if record.chain_hash != record_hash(record):
                return broken("record hash does not match its contents")
            if previous is not None and record.recorded_at < previous.recorded_at:
                return broken("recorded earlier than its predecessor")
            previous = record

        head = self.head
        last = records[-1].chain_hash if records else None
        if head != last:
            # The head pointer and the table disagree: records were removed
            # from the end, or added around the ledger.
            return ChainVerification(
                False,
                len(records),
                len(records) + 1 if head else 1,
                "head does not match the chain",
            )
        return ChainVerification(True, len(records))

    def proves(self, record: AuditRecord, payload: dict[str, Any]) -> bool:
        """Does ``payload`` match what this record attests to?

        Lets an auditor confirm that a document they were handed is the one the
        ledger recorded, without the ledger holding the document.
        """
        return record.payload_hash == hash_payload(hashable(payload))


__all__ = [
    "AUDIT",
    "AUDIT_HEAD",
    "HASH_VERSION",
    "ActorKind",
    "AppendOnlyViolation",
    "AuditEventType",
    "AuditLedger",
    "AuditRecord",
    "AuditUnavailable",
    "ChainVerification",
    "hashable",
    "record_hash",
]
