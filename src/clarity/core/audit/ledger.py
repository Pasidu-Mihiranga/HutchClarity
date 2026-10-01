"""Append-only, hash-chained audit ledger (deck S8, plan §20.3-20.4).

"Every decision affecting customers or money must be auditable." The ledger is
what makes that checkable rather than asserted: each record is hashed, and each
hash includes its predecessor's, so altering or removing an old record breaks
every record after it. Verification needs nothing but the ledger itself.

What gets recorded is listed in plan §20.4: input evidence, rule version,
decision, approval, MCP tool call, staff action, system action, response,
receipt and override.

**Prototype note.** Append-only is enforced in code here. Production also
removes UPDATE and DELETE grants from the writing role and anchors the chain
head to WORM storage, so the guarantee survives a privileged insider
(plan §7.2 T4).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field

from clarity.schemas.canonical import chain_hash, hash_payload
from clarity.schemas.common import ClarityModel, utc_now


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


class AuditRecord(ClarityModel):
    """One immutable entry. ``chain_hash`` binds it to everything before it."""

    seq: int
    event_type: AuditEventType
    actor_ref: str
    object_ref: str
    case_id: str | None = None
    payload_hash: str
    prev_hash: str | None
    chain_hash: str
    at: datetime

    #: Masked detail for a human reading the trail. Never raw PII.
    detail: dict[str, Any] = Field(default_factory=dict)


@dataclass
class ChainVerification:
    intact: bool
    length: int
    broken_at: int | None = None
    reason: str | None = None


class AppendOnlyViolation(RuntimeError):
    """Something tried to change or remove an existing record."""


class AuditLedger:
    """Append-only ledger with a verifiable hash chain."""

    def __init__(self) -> None:
        self._records: list[AuditRecord] = []
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
    ) -> AuditRecord:
        """Add a record. The payload is hashed, not stored in the clear."""
        with self._lock:
            previous = self._records[-1] if self._records else None
            payload_hash = hash_payload(payload)
            record = AuditRecord(
                seq=len(self._records) + 1,
                event_type=event_type,
                actor_ref=actor_ref,
                object_ref=object_ref,
                case_id=case_id,
                payload_hash=payload_hash,
                prev_hash=previous.chain_hash if previous else None,
                chain_hash=chain_hash(payload_hash, previous.chain_hash if previous else None),
                at=now or utc_now(),
                detail=detail or {},
            )
            self._records.append(record)
            return record

    # ------------------------------------------------------------------ #
    # Reading
    # ------------------------------------------------------------------ #

    def __len__(self) -> int:
        return len(self._records)

    @property
    def records(self) -> list[AuditRecord]:
        """A copy: callers cannot reach in and alter the ledger."""
        return list(self._records)

    @property
    def head(self) -> str | None:
        """Current chain head, anchored to WORM storage in production."""
        return self._records[-1].chain_hash if self._records else None

    def for_case(self, case_id: str) -> list[AuditRecord]:
        """The full trail for one case — what a regulator pack exports."""
        return [r for r in self._records if r.case_id == case_id]

    def of_type(self, event_type: AuditEventType) -> list[AuditRecord]:
        return [r for r in self._records if r.event_type is event_type]

    # ------------------------------------------------------------------ #
    # Verifying
    # ------------------------------------------------------------------ #

    def verify(self) -> ChainVerification:
        """Recompute the whole chain. Any edit or deletion shows up here."""
        previous_hash: str | None = None
        for index, record in enumerate(self._records):
            if record.seq != index + 1:
                return ChainVerification(
                    False, len(self._records), record.seq, "sequence numbers are not contiguous"
                )
            if record.prev_hash != previous_hash:
                return ChainVerification(
                    False, len(self._records), record.seq, "record does not follow its predecessor"
                )
            expected = chain_hash(record.payload_hash, previous_hash)
            if record.chain_hash != expected:
                return ChainVerification(
                    False, len(self._records), record.seq, "chain hash does not match its contents"
                )
            previous_hash = record.chain_hash
        return ChainVerification(True, len(self._records))

    def proves(self, record: AuditRecord, payload: dict[str, Any]) -> bool:
        """Does ``payload`` match what this record attests to?

        Lets an auditor confirm that a document they were handed is the one the
        ledger recorded, without the ledger holding the document.
        """
        return record.payload_hash == hash_payload(payload)
