"""Restore, loss reporting and reconciliation (audit assurance plan, Phase 6).

Recovery asks three questions in order, and the order matters.

**What came back?** A restored trail is verified like any other: the chain, and
the signed checkpoints in the bundle.

**What did not come back?** This is the question a backup alone cannot answer. A
bundle that is internally consistent looks complete, because it is complete *as
of when it was made*; everything after that is missing and nothing inside the
bundle knows it. So the loss report compares the restored trail against a
checkpoint held **outside** it: the copy a witness kept from the public endpoint.
A signature over ``seq`` 4210 proves the trail once reached 4210, so a restore
that stops at 3990 lost exactly 3991 to 4210, and the report says so in those
words rather than "some records may be missing".

**What happened in the gap, and what must not happen twice?** Records in the lost
window are gone, so the trail cannot say what they held. Two things can: the
restored domain state, and the HUTCH systems themselves. Reconciliation asks the
command port, for each action the restored state knows about, whether the far
side already did it, through ``status_of`` and its idempotency key. That turns
the dangerous question ("should this refund be retried?") into a read.

The one rule reconciliation never breaks: **it never executes anything.** It
sorts the world into three buckets and hands them to a person. A refund the far
side already made is re-ingested as a fact, exactly once, and never re-executed
(I8, acceptance test 3).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from enum import StrEnum

from clarity.integration.ports import CommandResult
from clarity.platform.audit.backup import AuditBundle
from clarity.platform.audit.checkpoints import (
    Checkpoint,
    CheckpointVerification,
    signature_valid,
    statement_hash,
)


@dataclass
class LossReport:
    """What a restore recovered, and exactly what it did not.

    ``lost_from`` and ``lost_to`` are inclusive and both ``None`` when nothing was
    lost. ``complete`` is deliberately not the same as ``intact``: a trail can
    verify perfectly and still be missing its last three hundred records, which
    is the failure mode this whole report exists to name.
    """

    restored_to_seq: int
    witness_seq: int | None
    intact: bool
    complete: bool
    lost_from: int | None = None
    lost_to: int | None = None
    reason: str | None = None

    @property
    def lost_count(self) -> int:
        if self.lost_from is None or self.lost_to is None:
            return 0
        return self.lost_to - self.lost_from + 1

    @property
    def summary(self) -> str:
        if not self.intact:
            return f"the restored trail failed verification: {self.reason}"
        if self.complete:
            return f"the trail was restored complete to seq {self.restored_to_seq}"
        return (
            f"the trail was restored to seq {self.restored_to_seq}; a signed checkpoint "
            f"proves it reached {self.witness_seq}, so records {self.lost_from} to "
            f"{self.lost_to} ({self.lost_count}) were lost"
        )


def loss_from(
    verification: CheckpointVerification,
    *,
    restored_to_seq: int,
    witness: Checkpoint | None,
) -> LossReport:
    """Turn a checkpoint verification into a loss report."""
    return LossReport(
        restored_to_seq=restored_to_seq,
        witness_seq=witness.seq if witness else None,
        intact=verification.intact or verification.lost_from is not None,
        complete=verification.lost_from is None,
        lost_from=verification.lost_from,
        lost_to=verification.lost_to,
        reason=verification.reason,
    )


def assess_bundle(bundle: AuditBundle, witness: Checkpoint | None = None) -> LossReport:
    """Measure a bundle against a checkpoint held outside it, before restoring.

    Run first, on the bundle rather than on the database, so an operator learns
    what a restore will and will not recover *before* overwriting what is there.
    """
    restored_to = bundle.head_seq
    if witness is None:
        return LossReport(
            restored_to_seq=restored_to,
            witness_seq=None,
            intact=True,
            complete=True,
            reason="no external checkpoint was supplied, so completeness is unknown",
        )
    keys = bundle.public_keys
    if witness.statement_hash != statement_hash(
        witness.seq, witness.chain_head, witness.recorded_at
    ) or (keys and not signature_valid(witness, keys)):
        return LossReport(
            restored_to_seq=restored_to,
            witness_seq=witness.seq,
            intact=False,
            complete=False,
            reason="the external checkpoint does not verify, so it proves nothing",
        )
    if witness.seq <= restored_to:
        return LossReport(
            restored_to_seq=restored_to, witness_seq=witness.seq, intact=True, complete=True
        )
    return LossReport(
        restored_to_seq=restored_to,
        witness_seq=witness.seq,
        intact=True,
        complete=False,
        lost_from=restored_to + 1,
        lost_to=witness.seq,
    )


# --------------------------------------------------------------------------- #
# Reconciliation
# --------------------------------------------------------------------------- #


class Standing(StrEnum):
    """Where one action stands, once the far side has been asked."""

    AGREED = "agreed"
    """Both sides did it. Nothing to do."""

    MISSING_LOCALLY = "missing_locally"
    """HUTCH did it; the restored state does not know. Re-ingest the fact,
    exactly once, and never execute it again."""

    NOT_DONE = "not_done"
    """HUTCH never did it. Safe for a person to put through the normal path,
    which is the only path that may move money."""

    UNKNOWN = "unknown"
    """The far side could not be asked. A person decides, with nothing guessed."""


@dataclass(frozen=True)
class ActionToCheck:
    """One action the restored state knows about, by the key that identifies it."""

    idempotency_key: str
    case_id: str | None = None
    known_locally: bool = True
    """Whether the restored state holds a completed record for it."""


@dataclass
class ReconciliationItem:
    action: ActionToCheck
    standing: Standing
    detail: str = ""

    @property
    def needs_a_person(self) -> bool:
        return self.standing is not Standing.AGREED


@dataclass
class ReconciliationPlan:
    """What reconciliation found. It is a plan, never an execution."""

    items: list[ReconciliationItem] = field(default_factory=list)

    def of(self, standing: Standing) -> list[ReconciliationItem]:
        return [item for item in self.items if item.standing is standing]

    @property
    def to_re_ingest(self) -> list[ReconciliationItem]:
        """Facts HUTCH holds and Clarity lost. Re-ingested, never re-executed."""
        return self.of(Standing.MISSING_LOCALLY)

    @property
    def safe_to_retry(self) -> list[ReconciliationItem]:
        return self.of(Standing.NOT_DONE)

    @property
    def needing_a_person(self) -> list[ReconciliationItem]:
        return [item for item in self.items if item.needs_a_person]

    @property
    def summary(self) -> str:
        counts = ", ".join(f"{len(self.of(standing))} {standing.value}" for standing in Standing)
        return f"{len(self.items)} action(s) checked: {counts}"


def reconcile(
    actions: Iterable[ActionToCheck],
    status_of: Callable[[str], CommandResult | None],
) -> ReconciliationPlan:
    """Ask the far side about each action. Nothing here executes anything.

    ``status_of`` is the command port's lookup, which exists for exactly this:
    "used instead of a blind retry" (``integration.ports``). A refund whose key
    the far side already knows is done, and asking is how we find that out
    without moving money to discover it.

    A lookup that raises becomes ``UNKNOWN`` rather than an exception, because a
    reconciliation that stops at the first unreachable system leaves the rest of
    the window unexamined, and the whole point is to hand a person a complete
    picture.
    """
    plan = ReconciliationPlan()
    for action in actions:
        try:
            result = status_of(action.idempotency_key)
        except Exception as error:  # the far side is down, not the reconciliation
            plan.items.append(
                ReconciliationItem(action, Standing.UNKNOWN, f"could not be asked: {error}")
            )
            continue
        if result is None:
            plan.items.append(
                ReconciliationItem(
                    action,
                    Standing.NOT_DONE,
                    "HUTCH has no record of this key, so nothing was executed",
                )
            )
        elif action.known_locally:
            plan.items.append(
                ReconciliationItem(action, Standing.AGREED, "both sides hold this execution")
            )
        else:
            plan.items.append(
                ReconciliationItem(
                    action,
                    Standing.MISSING_LOCALLY,
                    "HUTCH executed this and the restored state lost it: re-ingest the "
                    "outcome, never execute it again",
                )
            )
    return plan


def actions_in_window(
    actions: Sequence[ActionToCheck], *, lost_from: int | None, lost_to: int | None
) -> list[ActionToCheck]:
    """Everything worth checking after a loss.

    Deliberately **not** filtered to the lost window. The window names the audit
    records that went missing, not the actions: an action whose record survived
    may still have been executed after the backup point and then rolled back with
    the database, and an action with no record at all is the case this is for. So
    a loss means check everything the restored state knows about, and the window
    is in the report for the person reading it, not a filter on the work.
    """
    if lost_from is None and lost_to is None:
        return []
    return list(actions)


__all__ = [
    "ActionToCheck",
    "LossReport",
    "ReconciliationItem",
    "ReconciliationPlan",
    "Standing",
    "actions_in_window",
    "assess_bundle",
    "loss_from",
    "reconcile",
]
