"""Approving a policy change (plan §19 3-4, ADR-0011).

A cap is a number anyone could type. What stops a wrong one reaching
production is not the editor but the lifecycle around it:

- the **class** is computed from what the change touches and can be raised but
  never lowered, so nobody downgrades their own change to skip an approver;
- **maker is never checker**, and a money change needs a second, different
  approver;
- a money- or outcome-affecting change needs an **impact report** attached
  before anyone may approve it;
- activation is explicit, and the whole thing is audited.
"""

from __future__ import annotations

from datetime import datetime

from clarity.kernel.common import utc_now
from clarity.kernel.ids import new_id
from clarity.modules.governance.artefacts import (
    Approval,
    ChangeRefused,
    ChangeState,
    PolicyChange,
)
from clarity.modules.governance.replay import ImpactReport
from clarity.modules.governance.repository import PolicyChangeRepository
from clarity.platform.config.artefacts import ChangeClass, PolicyValue


class PolicyGovernance:
    """The approval gate in front of every policy change."""

    #: Classes that may not be approved without a replay impact report.
    _NEEDS_IMPACT = frozenset(
        {
            ChangeClass.C2_OUTCOME_AFFECTING,
            ChangeClass.C3_MONEY_AFFECTING,
            ChangeClass.C4_REGULATORY,
        }
    )

    def __init__(self, changes: PolicyChangeRepository, *, audit: object | None = None) -> None:
        # Policy changes live in the repository (B02); the gate keeps none.
        self._changes = changes
        self._audit = audit

    def draft(
        self,
        *,
        key: str,
        candidate: PolicyValue,
        computed_class: ChangeClass,
        maker_ref: str,
        reason: str,
        raise_to: ChangeClass | None = None,
    ) -> PolicyChange:
        """Open a change. The class comes from the artefact's tags.

        ``raise_to`` lets a maker treat a change as riskier than its tags
        suggest. There is deliberately no way to lower it.
        """
        change_class = computed_class
        if raise_to is not None:
            if raise_to.needs_second_approver and not computed_class.needs_second_approver:
                change_class = raise_to
            elif raise_to is not computed_class:
                raise ChangeRefused(
                    "CLASS_CANNOT_BE_LOWERED",
                    f"{key}: the class of a {computed_class.value} change cannot be lowered "
                    f"to {raise_to.value}",
                )
        if not reason.strip():
            raise ChangeRefused("REASON_REQUIRED", "a policy change must record why")

        change = PolicyChange(
            change_id=new_id("CHG"),
            key=key,
            candidate=candidate,
            change_class=change_class,
            maker_ref=maker_ref,
            reason=reason,
        )
        self._changes.save(change)
        return change

    def attach_impact(self, change_id: str, report: ImpactReport) -> PolicyChange:
        change = self.get(change_id)
        change.impact = report
        change.state = ChangeState.IN_REVIEW
        self._changes.save(change)
        return change

    def approve(
        self,
        change_id: str,
        *,
        approver_ref: str,
        role: str,
        mfa_step_up: bool = True,
        now: datetime | None = None,
    ) -> PolicyChange:
        """Record one approval, enforcing separation of duties."""
        change = self.get(change_id)
        if change.state is ChangeState.ACTIVE:
            raise ChangeRefused("ALREADY_ACTIVE", f"{change_id} is already active")
        if approver_ref == change.maker_ref:
            raise ChangeRefused(
                "MAKER_CANNOT_APPROVE", "the person who drafted a change cannot approve it"
            )
        if any(a.approver_ref == approver_ref for a in change.approvals):
            raise ChangeRefused("ALREADY_APPROVED", "this approver has already signed off")
        if change.change_class.needs_second_approver and not mfa_step_up:
            raise ChangeRefused("STEP_UP_REQUIRED", "this change needs MFA step-up")
        if change.change_class in self._NEEDS_IMPACT and change.impact is None:
            raise ChangeRefused(
                "IMPACT_REPORT_REQUIRED",
                f"a {change.change_class.value} change needs a replay impact report "
                "before it can be approved",
            )

        change.approvals.append(
            Approval(
                approver_ref=approver_ref,
                role=role,
                at=now or utc_now(),
                mfa_step_up=mfa_step_up,
            )
        )
        change.state = ChangeState.APPROVED if change.is_approved else ChangeState.IN_REVIEW
        self._changes.save(change)
        return change

    def activate(self, change_id: str, *, now: datetime | None = None) -> PolicyChange:
        """Publish an approved change."""
        change = self.get(change_id)
        if not change.is_approved:
            raise ChangeRefused(
                "NOT_APPROVED",
                f"{change.key} needs {change.approvals_needed} approvals, "
                f"has {len(change.approvals)}",
            )
        change.state = ChangeState.ACTIVE
        change.activated_at = now or utc_now()
        self._changes.save(change)
        self._record(change)
        return change

    def get(self, change_id: str) -> PolicyChange:
        change = self._changes.get(change_id)
        if change is None:
            raise ChangeRefused("UNKNOWN_CHANGE", f"no change {change_id}")
        return change

    def pending(self) -> list[PolicyChange]:
        return [c for c in self._changes.all_changes() if c.state is not ChangeState.ACTIVE]

    def _record(self, change: PolicyChange) -> None:
        if self._audit is None:
            return
        from clarity.platform.audit.ledger import AuditEventType, AuditLedger

        if isinstance(self._audit, AuditLedger):
            self._audit.append(
                AuditEventType.RULE_PUBLISHED,
                actor_ref=change.maker_ref,
                object_ref=f"policy:{change.key}",
                payload={
                    "key": change.key,
                    "value": str(change.candidate.value),
                    "scope": change.candidate.scope.label(),
                    "class": change.change_class.value,
                    "approvers": [a.approver_ref for a in change.approvals],
                },
                detail={"reason": change.reason, "class": change.change_class.value},
                now=change.activated_at,
            )
