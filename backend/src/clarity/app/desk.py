"""Wiring the desk to the case service (D01, #26).

The composition root's job. `deskops` knows what a bulk fix may do and refuses
everything else; these two adapters are how it reaches the cases, and they are
deliberately thin.

**The fixer is the ordinary single-case path.** `fix` calls
`approve_and_execute`, which mints the confirmation token, enforces the tool
layer's own four-eyes, applies idempotency and issues the one receipt that plan
produces. A bulk fix is therefore N ordinary fixes: it cannot reach anything an
operator could not do one case at a time, and it does not get its own execution
code to go wrong differently.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

from clarity.contracts.decision import Outcome, PlanStatus
from clarity.contracts.receipt import TrustReceipt
from clarity.modules.actions.public import ExecutionResult
from clarity.modules.case.public import CaseNotFound
from clarity.modules.deskops.public import (
    CasePreview,
    CaseResult,
    DeskCase,
    Eligibility,
)
from clarity.modules.resolution.public import ResolutionService

#: Outcomes a bulk fix can act on.
#:
#: **`ONE_TAP_FIX` is deliberately not here, and that was a correction.** The
#: first version of this adapter included it and the tool layer refused every
#: case with "a ONE_TAP_FIX decision is not a staff approval", which is right:
#: a one-tap fix is the *customer's* tap, and executing it for them needs a
#: confirmation token minted from that tap (ADR-0007). A desk cannot mint one,
#: and a desk that could would be deciding on a customer's behalf in a case
#: whose policy said to ask them.
#:
#: So a desk may bulk-remediate the two outcomes that do not need the
#: customer: `AUTO_FIX`, which policy already whitelisted for zero contact,
#: and `STAFF_APPROVAL`, which is staff work by definition. Remediating a
#: population of one-tap cases means either getting those customers to tap or
#: changing the policy that classified them, and both are decisions somebody
#: has to make rather than a desk batch to run.
#:
#: `EXPLAIN_ONLY` has no allowed action and `HANDOFF` is a person's job.
ACTIONABLE = frozenset({Outcome.AUTO_FIX, Outcome.STAFF_APPROVAL})


class ServiceCaseFixer:
    """Previews and fixes one case through the resolution service."""

    def __init__(self, cases: ResolutionService) -> None:
        self._cases = cases

    def preview(self, case_id: str) -> CasePreview:
        """What would happen, reading only. Nothing here changes a case."""
        try:
            record = self._cases.get(case_id)
        except (CaseNotFound, KeyError):
            return CasePreview(case_id=case_id, eligibility=Eligibility.NO_CASE)

        decision = record.decision
        if decision is None:
            return CasePreview(
                case_id=case_id,
                eligibility=Eligibility.NO_PLAN,
                detail="not evaluated",
            )
        if decision.outcome not in ACTIONABLE:
            return CasePreview(
                case_id=case_id,
                eligibility=Eligibility.NOT_ALLOWED,
                outcome=decision.outcome.value,
                detail=f"{decision.outcome.value} allows no action",
            )

        pending = [
            plan for plan in record.plans.values() if plan.status is PlanStatus.PENDING_CONFIRMATION
        ]
        if record.receipts_by_plan and not pending:
            return CasePreview(
                case_id=case_id,
                eligibility=Eligibility.ALREADY_DONE,
                outcome=decision.outcome.value,
                detail="executed already; a replay returns the original receipt",
            )
        if not pending:
            return CasePreview(
                case_id=case_id,
                eligibility=Eligibility.NO_PLAN,
                outcome=decision.outcome.value,
                detail="nothing proposed; the desk cannot propose in bulk",
            )

        plan = pending[0]
        return CasePreview(
            case_id=case_id,
            eligibility=Eligibility.ELIGIBLE,
            plan_id=plan.plan_id,
            # Printed as the plan carries it. Never formatted or rounded here:
            # the figure a checker approves has to be the figure that moves.
            amount_lkr=str(plan.total_amount_lkr),
            outcome=decision.outcome.value,
            detail=plan.display_summary,
        )

    def fix(self, case_id: str, plan_id: str, *, approver_ref: str, role: str) -> CaseResult:
        """Execute one case, through the path a single fix already uses.

        Routed by the decision's outcome, because the two actionable outcomes
        are authorised differently and neither authorisation is this adapter's
        to invent:

        - `AUTO_FIX` is already whitelisted for zero contact, so it goes
          through `auto_fix`, attributed to the batch's approver rather than to
          the stream detector that usually triggers one.
        - `STAFF_APPROVAL` goes through `approve_and_execute`, which applies
          the tool layer's own four-eyes to this case as well as the batch's.
        """
        try:
            record = self._cases.get(case_id)
            outcome = record.decision.outcome if record.decision else None
            done: tuple[ExecutionResult, TrustReceipt] | None
            if outcome is Outcome.AUTO_FIX:
                done = self._cases.auto_fix(
                    case_id, plan_id, triggered_by=f"desk-bulk:{approver_ref}"
                )
            else:
                done = self._cases.approve_and_execute(
                    case_id, plan_id, approver_ref=approver_ref, role=role
                )
        except Exception as refused:
            # A refusal for one case is not the batch's failure. The tool layer
            # is the authority on whether this plan may execute, and a batch
            # that stopped on the first refusal would leave the rest of an
            # approved remediation undone with no record of why.
            return CaseResult(
                case_id=case_id,
                executed=False,
                plan_id=plan_id,
                error=f"{type(refused).__name__}: {refused}",
            )
        if done is None:
            return CaseResult(
                case_id=case_id,
                executed=False,
                plan_id=plan_id,
                error="more approval is needed for this case",
            )
        _result, receipt = done
        return CaseResult(
            case_id=case_id,
            executed=True,
            plan_id=plan_id,
            receipt_id=receipt.receipt_id,
        )


class ServiceDeskCases:
    """Flattens case records into the small, pseudonymous rows the desk reads."""

    def __init__(self, cases: ResolutionService) -> None:
        self._cases = cases

    def recent(self, since: datetime) -> Sequence[DeskCase]:
        rows: list[DeskCase] = []
        for record in self._cases.all_cases():
            opened = record.case.opened_at
            if opened < since:
                continue
            rows.append(
                DeskCase(
                    case_id=record.case_id,
                    # The HMAC pseudonym, never an MSISDN: these rows reach a
                    # regulator pack (I13).
                    subscriber_ref=record.subscriber_ref,
                    opened_at=opened,
                    outcome=record.decision.outcome.value if record.decision else None,
                    cause_ref=record.decision.top_cause_ref if record.decision else None,
                    merchant_ids=_merchants(record),
                    refunded_lkr=_moved(record.execution),
                    receipt_id=record.receipt.receipt_id if record.receipt else None,
                    handed_off=(
                        record.decision.outcome is Outcome.HANDOFF if record.decision else False
                    ),
                )
            )
        return rows


def _moved(execution: ExecutionResult | None) -> str | None:
    """What actually moved, summed from the executed actions.

    `ExecutionResult` carries no total, and inventing one from the plan would
    report what was *meant* to move. A partially compensated execution moved
    less than its plan said, and a desk view that showed the plan's figure
    would overstate the remediation. Actions with no amount (switching a
    subscription off, blocking a merchant) contribute nothing, which is right.
    """
    if execution is None:
        return None
    total = sum(
        (action.amount_lkr for action in execution.actions if action.amount_lkr is not None),
        Decimal("0.00"),
    )
    return str(total) if total else None


def _merchants(record: object) -> tuple[str, ...]:
    """Merchant ids named by the case's own evidence.

    Read from the timeline's `attributes`, which is where the adapters put
    them (plan section 9.1). Deduplicated and sorted, so a watch score counts
    a merchant once per case and two reads of one window agree.
    """
    snapshot = getattr(record, "snapshot", None)
    if snapshot is None:
        return ()
    found: set[str] = set()
    for event in getattr(snapshot, "events", ()):
        merchant = dict(getattr(event, "attributes", {})).get("merchant_id")
        if merchant:
            found.add(str(merchant))
    return tuple(sorted(found))


__all__ = ["ACTIONABLE", "ServiceCaseFixer", "ServiceDeskCases"]
