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

from collections.abc import Callable
from datetime import datetime

from clarity.contracts.events import PolicyPublishedV1
from clarity.kernel.common import utc_now
from clarity.kernel.ids import new_id
from clarity.modules.governance.artefacts import (
    Approval,
    ChangeRefused,
    ChangeState,
    PolicyActivation,
    PolicyChange,
)
from clarity.modules.governance.replay import ImpactReport
from clarity.modules.governance.repository import (
    CHANGES,
    PolicyChangeRepository,
    StoredPolicyChangeRepository,
)
from clarity.platform.config.artefacts import ChangeClass, PolicyValue
from clarity.platform.config.resolver import PolicyResolver
from clarity.platform.messaging.envelope import Event
from clarity.platform.messaging.outbox import outbox_in
from clarity.platform.persistence import UnitOfWorkFactory


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

    def __init__(
        self,
        changes: PolicyChangeRepository,
        *,
        policies: PolicyResolver | None = None,
        audit: object | None = None,
        clock: Callable[[], datetime] = utc_now,
        publish: Callable[[PolicyPublishedV1], None] | None = None,
        open_unit: UnitOfWorkFactory | None = None,
        deliver_events: Callable[[], None] | None = None,
    ) -> None:
        # Policy changes live in the repository (B02); the gate keeps none.
        self._changes = changes
        self._policies = policies
        self._audit = audit
        self._clock = clock
        self._publish = publish
        self._open_unit = open_unit
        self._deliver_events = deliver_events

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
                at=now or self._clock(),
                mfa_step_up=mfa_step_up,
            )
        )
        change.state = ChangeState.APPROVED if change.is_approved else ChangeState.IN_REVIEW
        self._changes.save(change)
        return change

    def schedule(
        self,
        change_id: str,
        *,
        effective_from: datetime,
    ) -> PolicyChange:
        """Schedule an approved version for its effective date."""
        change = self.get(change_id)
        if not change.is_approved:
            raise ChangeRefused("NOT_APPROVED", f"{change.key} is not approved")
        change.scheduled_for = effective_from
        change.candidate = change.candidate.model_copy(update={"effective_from": effective_from})
        change.state = ChangeState.SCHEDULED
        self._changes.save(change)
        return change

    def activate_due(self, *, now: datetime | None = None) -> list[PolicyChange]:
        """Activate scheduled changes whose injected clock has reached them."""
        moment = now or self._clock()
        activated: list[PolicyChange] = []
        for change in self._changes.all_changes():
            if (
                change.state is ChangeState.SCHEDULED
                and change.scheduled_for is not None
                and change.scheduled_for <= moment
            ):
                activated.append(self.activate(change.change_id, now=moment))
        return activated

    def activate(self, change_id: str, *, now: datetime | None = None) -> PolicyChange:
        """Publish an approved change."""
        moment = now or self._clock()
        # Validate the resolver update before committing lifecycle state.
        preview = self.get(change_id)
        if self._policies is not None:
            self._policies.with_override(preview.key, preview.candidate)

        if self._open_unit is not None:
            with self._open_unit() as unit:
                changes = StoredPolicyChangeRepository(unit.repository(CHANGES))
                change = self._activate_in(changes, change_id, moment)
                outbox_in(unit).append(Event.of(self._published(change), subject="policy"))
                unit.commit()
        else:
            change = self._activate_in(self._changes, change_id, moment)

        if self._policies is not None:
            self._policies.publish(change.key, change.candidate)
        self._record(change)
        if self._open_unit is None and self._publish is not None:
            self._publish(self._published(change))
        if self._deliver_events is not None:
            self._deliver_events()
        return change

    def _activate_in(
        self,
        changes: PolicyChangeRepository,
        change_id: str,
        moment: datetime,
    ) -> PolicyChange:
        change = changes.get(change_id)
        if change is None:
            raise ChangeRefused("UNKNOWN_CHANGE", f"no change {change_id}")
        if not change.is_approved:
            raise ChangeRefused(
                "NOT_APPROVED",
                f"{change.key} needs {change.approvals_needed} approvals, "
                f"has {len(change.approvals)}",
            )
        if change.scheduled_for is not None and moment < change.scheduled_for:
            raise ChangeRefused(
                "NOT_EFFECTIVE_YET",
                f"{change.key} is scheduled for {change.scheduled_for.isoformat()}",
            )
        for previous in changes.all_changes():
            if (
                previous.change_id != change.change_id
                and previous.key == change.key
                and previous.state is ChangeState.ACTIVE
                and previous.candidate.scope == change.candidate.scope
            ):
                previous.state = ChangeState.SUPERSEDED
                changes.save(previous)
                change.supersedes = previous.change_id
        change.state = ChangeState.ACTIVE
        change.activated_at = moment
        change.activations.append(
            PolicyActivation(
                activated_at=moment,
                reason="scheduled" if change.scheduled_for else "publish",
                actor_ref=change.maker_ref,
            )
        )
        changes.save(change)
        return change

    @staticmethod
    def _published(change: PolicyChange) -> PolicyPublishedV1:
        return PolicyPublishedV1(
            change_id=change.change_id,
            key=change.key,
            policy_version=change.candidate.version,
            change_class=change.change_class.value,
            effective_from=change.candidate.effective_from,
        )

    def rollback(
        self,
        change_id: str,
        *,
        maker_ref: str,
        reason: str,
    ) -> PolicyChange:
        """Draft a governed reactivation of the version this change replaced."""
        current = self.get(change_id)
        if current.supersedes is None:
            raise ChangeRefused("NO_PREVIOUS_VERSION", f"{change_id} supersedes no version")
        previous = self.get(current.supersedes)
        return self.draft(
            key=previous.key,
            candidate=previous.candidate.model_copy(
                update={
                    "version": current.candidate.version + 1,
                    "effective_from": None,
                    "effective_to": None,
                }
            ),
            computed_class=current.change_class,
            maker_ref=maker_ref,
            reason=reason,
        )

    def get(self, change_id: str) -> PolicyChange:
        change = self._changes.get(change_id)
        if change is None:
            raise ChangeRefused("UNKNOWN_CHANGE", f"no change {change_id}")
        return change

    def pending(self) -> list[PolicyChange]:
        return [
            c
            for c in self._changes.all_changes()
            if c.state not in {ChangeState.ACTIVE, ChangeState.SUPERSEDED}
        ]

    def all_changes(self) -> list[PolicyChange]:
        return self._changes.all_changes()

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
