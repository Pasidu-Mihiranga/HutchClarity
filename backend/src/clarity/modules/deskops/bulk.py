"""Bulk fix: one desk action across many cases (D01, #26; plan 02 section 3.5).

The most dangerous feature in the product. A desk operator deciding that forty
cases share a cause and fixing them in one action is exactly what the deck
promises, and it is also one mistake away from forty wrong refunds, so almost
everything here is a refusal.

Four rules, and each one exists because of a specific way this goes wrong.

**1. A bulk fix executes each case's own existing plan. It cannot invent one.**
The desk chooses *which cases*, never *what to do to them*: what may happen to
a case was settled by its decision, under the policy resolved as of its event
(I1, D2). A bulk action that carried its own action type would be a path from
one operator's judgement to money moving in cases whose decisions never
allowed it.

**2. The approval is of a specific dry run, not of a batch id.** A checker who
approves "refund these 40 cases" and finds 80 executed has not approved what
happened. So a dry run is fingerprinted over exactly what it said would
happen, the approval carries that fingerprint, and execution refuses if the
world has moved since. This is the rule that makes the other three meaningful:
without it, four-eyes approves a label.

**3. Maker is never checker**, at the batch level and again per case. The batch
gate is what D01 adds. The per-case gate already existed in the tool layer
(`approve_by_staff` refuses an approver who created the plan) and still
applies, so a bulk fix cannot be used to get around it.

**4. A partial failure is reported, never rolled back.** Twelve refunds that
succeeded are twelve customers who have their money. Unwinding them to make a
batch look atomic would be a second unauthorised movement. The batch reports
per case and the successes stand.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol

from clarity.kernel.canonical import hash_payload
from clarity.kernel.common import utc_now
from clarity.kernel.ids import new_id


class BulkFixRefused(PermissionError):
    """The batch may not proceed as asked. Always a decision, never a glitch."""


class Eligibility(StrEnum):
    """What a dry run found for one case."""

    ELIGIBLE = "eligible"
    """A pending plan the decision allows, ready to execute."""

    NO_PLAN = "no_plan"
    """Nothing proposed. The desk cannot propose one in bulk."""

    ALREADY_DONE = "already_done"
    """Executed already. Replaying returns the original receipt (I8)."""

    NOT_ALLOWED = "not_allowed"
    """The decision does not permit an action, for example EXPLAIN_ONLY."""

    NO_CASE = "no_case"


class BatchStatus(StrEnum):
    DRAFTED = "drafted"
    """A dry run exists. Nothing can happen in this state."""

    APPROVED = "approved"
    EXECUTED = "executed"
    REFUSED = "refused"


@dataclass(frozen=True)
class CasePreview:
    """What a dry run says would happen to one case."""

    case_id: str
    eligibility: Eligibility
    plan_id: str | None = None
    amount_lkr: str | None = None
    """Printed exactly as the plan carries it. Never computed here (I3)."""

    outcome: str | None = None
    detail: str = ""

    @property
    def would_execute(self) -> bool:
        return self.eligibility is Eligibility.ELIGIBLE

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "eligibility": self.eligibility.value,
            "plan_id": self.plan_id,
            "amount_lkr": self.amount_lkr,
            "outcome": self.outcome,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class DryRun:
    """What would happen, and a fingerprint of exactly that.

    The fingerprint covers the per-case plan ids and amounts, so it changes if
    a case gains a plan, loses one, is executed by somebody else, or has its
    amount re-decided. A checker approves this fingerprint and execution
    refuses a different one: that is what stops an approval drifting onto work
    nobody looked at.
    """

    batch_id: str
    previews: tuple[CasePreview, ...]
    at: datetime

    @property
    def eligible(self) -> tuple[CasePreview, ...]:
        return tuple(p for p in self.previews if p.would_execute)

    @property
    def fingerprint(self) -> str:
        return hash_payload(
            {
                "cases": sorted(
                    (p.case_id, p.plan_id or "", p.amount_lkr or "") for p in self.eligible
                )
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "at": self.at.isoformat(),
            "fingerprint": self.fingerprint,
            "would_execute": len(self.eligible),
            "skipped": len(self.previews) - len(self.eligible),
            "cases": [p.to_dict() for p in self.previews],
            # Said plainly, because a dry run that reads like a result is how
            # somebody believes the work is done.
            "executed": False,
        }


@dataclass(frozen=True)
class BatchApproval:
    approval_id: str
    approver_ref: str
    role: str
    fingerprint: str
    """What was approved. Not the batch id: see the module docstring."""

    at: datetime


@dataclass(frozen=True)
class CaseResult:
    """What actually happened to one case."""

    case_id: str
    executed: bool
    plan_id: str | None = None
    receipt_id: str | None = None
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "executed": self.executed,
            "plan_id": self.plan_id,
            "receipt_id": self.receipt_id,
            "error": self.error,
        }


@dataclass
class BulkFix:
    """One desk batch, from dry run to receipts."""

    batch_id: str
    reason: str
    case_ids: tuple[str, ...]
    created_by: str
    created_at: datetime
    status: BatchStatus = BatchStatus.DRAFTED
    dry_run: DryRun | None = None
    approvals: list[BatchApproval] = field(default_factory=list)
    results: list[CaseResult] = field(default_factory=list)

    @property
    def approved_by(self) -> tuple[str, ...]:
        return tuple(a.approver_ref for a in self.approvals)

    @property
    def receipts(self) -> tuple[str, ...]:
        return tuple(r.receipt_id for r in self.results if r.receipt_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "reason": self.reason,
            "status": self.status.value,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
            "case_count": len(self.case_ids),
            "approved_by": list(self.approved_by),
            "dry_run": self.dry_run.to_dict() if self.dry_run else None,
            "results": [r.to_dict() for r in self.results],
            "receipts": list(self.receipts),
        }


class CaseFixer(Protocol):
    """The one thing a bulk fix may do to a case, supplied by the composition root.

    Narrow on purpose, and it is the existing single-case path: the
    implementation the container wires calls `approve_and_execute`, which mints
    the confirmation token, enforces the per-case four-eyes and idempotency,
    and issues the one receipt that plan produces. A bulk fix is therefore N
    ordinary fixes and cannot reach anything an operator could not do one case
    at a time.
    """

    def preview(self, case_id: str) -> CasePreview: ...

    def fix(self, case_id: str, plan_id: str, *, approver_ref: str, role: str) -> CaseResult: ...


class BulkFixes:
    """Drafts, approves and executes desk batches."""

    #: The most cases one batch may touch.
    #:
    #: Not a performance limit. A batch nobody can read before approving is a
    #: batch nobody approved, and a checker scrolling 5000 rows is rubber
    #: stamping. A bigger remediation is several reviewed batches, which is
    #: slower on purpose.
    MAX_CASES = 200

    def __init__(
        self,
        fixer: CaseFixer,
        *,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._fixer = fixer
        self._clock = clock

    def draft(self, case_ids: Sequence[str], *, reason: str, created_by: str) -> BulkFix:
        """Draft a batch and dry run it. Nothing can execute from here."""
        unique = tuple(dict.fromkeys(case_ids))
        if not unique:
            raise BulkFixRefused("a batch needs at least one case")
        if len(unique) > self.MAX_CASES:
            raise BulkFixRefused(
                f"{len(unique)} cases is more than the {self.MAX_CASES} a reviewer can "
                "read; split it into batches somebody can actually check"
            )
        if not reason.strip():
            raise BulkFixRefused(
                "a batch needs a reason: it is what the checker is approving and what "
                "the audit trail will be asked about"
            )
        if not created_by.strip():
            raise BulkFixRefused("a batch needs a maker")

        batch = BulkFix(
            batch_id=new_id("BLK"),
            reason=reason.strip(),
            case_ids=unique,
            created_by=created_by.strip(),
            created_at=self._clock(),
        )
        batch.dry_run = self.dry_run(batch)
        return batch

    def dry_run(self, batch: BulkFix) -> DryRun:
        """Ask the fixer what would happen, changing nothing."""
        return DryRun(
            batch_id=batch.batch_id,
            previews=tuple(self._fixer.preview(case_id) for case_id in batch.case_ids),
            at=self._clock(),
        )

    def approve(
        self,
        batch: BulkFix,
        *,
        approver_ref: str,
        role: str,
        fingerprint: str,
    ) -> BulkFix:
        """Record a checker's approval of a specific dry run.

        The fingerprint is the argument that matters. A checker passes back the
        one they were shown, and a mismatch means the batch changed under them.
        """
        if batch.status is BatchStatus.EXECUTED:
            raise BulkFixRefused(f"{batch.batch_id} was already executed")
        if batch.dry_run is None:
            raise BulkFixRefused("approve a dry run, not a batch with none")
        if not approver_ref.strip():
            raise BulkFixRefused("an approval needs an approver")
        if approver_ref.strip() == batch.created_by:
            # Acceptance 1. The batch-level half of four-eyes.
            raise BulkFixRefused(
                f"{approver_ref} made this batch and cannot approve it; "
                "a bulk fix needs a second person"
            )
        if approver_ref.strip() in batch.approved_by:
            raise BulkFixRefused("this approver has already signed off")
        if fingerprint != batch.dry_run.fingerprint:
            raise BulkFixRefused(
                "the batch changed since that dry run, so the approval does not apply "
                "to what would now happen; dry run it again and review the difference"
            )

        batch.approvals.append(
            BatchApproval(
                approval_id=new_id("BAP"),
                approver_ref=approver_ref.strip(),
                role=role,
                fingerprint=fingerprint,
                at=self._clock(),
            )
        )
        batch.status = BatchStatus.APPROVED
        return batch

    def execute(self, batch: BulkFix) -> BulkFix:
        """Execute an approved batch, one case at a time.

        Re-running an executed batch returns it unchanged rather than executing
        again: the per-case path is idempotent (I8), and a batch that re-ran
        would still be a second authorised-looking movement in the audit trail.
        """
        if batch.status is BatchStatus.EXECUTED:
            return batch
        if not batch.approvals:
            # Acceptance 1, reached by the other route: executing with nobody
            # but the maker involved.
            raise BulkFixRefused(
                f"{batch.batch_id} has no approval; a bulk fix by its maker alone is refused"
            )
        if batch.dry_run is None:
            raise BulkFixRefused("a batch with no dry run cannot execute")

        approval = batch.approvals[-1]
        current = self.dry_run(batch)
        if current.fingerprint != approval.fingerprint:
            raise BulkFixRefused(
                "the batch changed since it was approved, so executing it would do "
                "work nobody approved; dry run it again and have it re-approved"
            )

        for preview in current.eligible:
            assert preview.plan_id is not None  # `eligible` implies a plan
            # The approver is carried through as the per-case approver, so the
            # tool layer's own four-eyes applies to every case as well.
            batch.results.append(
                self._fixer.fix(
                    preview.case_id,
                    preview.plan_id,
                    approver_ref=approval.approver_ref,
                    role=approval.role,
                )
            )
        batch.status = BatchStatus.EXECUTED
        return batch


__all__ = [
    "BatchApproval",
    "BatchStatus",
    "BulkFix",
    "BulkFixRefused",
    "BulkFixes",
    "CaseFixer",
    "CasePreview",
    "CaseResult",
    "DryRun",
    "Eligibility",
]
