"""Replay impact report: what a policy change would have done.

The deck promises "Policy what-if: replay past cases before a rule change"
(S9). We already had the ingredients - evidence snapshots and hashed decision
inputs make every decision reproducible - but no tool that used them.

This answers the question an approver actually has: *if I raise this cap, what
changes, and how much more money goes out?* No money-affecting change should be
approved without it (plan §19 4.1).

The candidate policy is never applied to the live resolver. The report builds a
copy, re-decides historic cases against it, and reports the differences.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from clarity.contracts.decision import Decision, DecisionInput, Outcome
from clarity.kernel.common import ZERO, money
from clarity.modules.decision.public import DecisionPolicy, PolicyThresholds
from clarity.platform.config.artefacts import ChangeClass, PolicyValue
from clarity.platform.config.resolver import PolicyResolver


@dataclass(frozen=True)
class ReplayCase:
    """One historic decision, with everything needed to re-decide it."""

    case_id: str
    decision_input: DecisionInput
    rule_id: str | None
    outcome: Outcome
    amount_lkr: Decimal
    channel: str | None = None


@dataclass
class OutcomeChange:
    case_id: str
    rule_id: str | None
    before: Outcome
    after: Outcome
    amount_lkr: Decimal

    @property
    def money_delta_lkr(self) -> Decimal:
        """How much more (or less) money moves without a human deciding.

        Only automatic outcomes count: a case that moves to staff approval has
        not spent anything until a person says so.
        """
        return money(self._weight(self.after) - self._weight(self.before))

    def _weight(self, outcome: Outcome) -> Decimal:
        return self.amount_lkr if outcome is Outcome.AUTO_FIX else ZERO


@dataclass
class ImpactReport:
    """What an approver sees before saying yes."""

    key: str
    change_class: ChangeClass
    cases_evaluated: int
    changes: list[OutcomeChange] = field(default_factory=list)
    generated_at: datetime | None = None
    candidate_summary: str = ""

    @property
    def changed(self) -> int:
        return len(self.changes)

    @property
    def unchanged(self) -> int:
        return self.cases_evaluated - self.changed

    @property
    def money_delta_lkr(self) -> Decimal:
        """Net change in money moved with no human in the loop."""
        return money(sum((c.money_delta_lkr for c in self.changes), ZERO))

    @property
    def newly_automatic(self) -> list[OutcomeChange]:
        """Cases that would stop needing a person. The ones to look at hardest."""
        return [c for c in self.changes if c.after is Outcome.AUTO_FIX]

    @property
    def newly_manual(self) -> list[OutcomeChange]:
        return [
            c
            for c in self.changes
            if c.before is Outcome.AUTO_FIX and c.after is not Outcome.AUTO_FIX
        ]

    @property
    def transitions(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for change in self.changes:
            label = f"{change.before.value} -> {change.after.value}"
            counts[label] = counts.get(label, 0) + 1
        return counts

    def samples(self, limit: int = 5) -> list[OutcomeChange]:
        """A few concrete cases, biggest money first."""
        return sorted(self.changes, key=lambda c: abs(c.money_delta_lkr), reverse=True)[:limit]

    def headline(self) -> str:
        if not self.changes:
            return f"No case out of {self.cases_evaluated} would decide differently."
        direction = "more" if self.money_delta_lkr >= 0 else "less"
        return (
            f"{self.changed} of {self.cases_evaluated} cases decide differently; "
            f"LKR {abs(self.money_delta_lkr)} {direction} would move automatically."
        )


class PolicyReplay:
    """Re-decides historic cases under a candidate policy."""

    def __init__(self, policy: DecisionPolicy, resolver: PolicyResolver) -> None:
        self._policy = policy
        self._resolver = resolver

    def preview(
        self,
        key: str,
        candidate: PolicyValue,
        cases: list[ReplayCase],
        *,
        now: datetime | None = None,
    ) -> ImpactReport:
        """Report what ``candidate`` would change across ``cases``.

        Raises if the candidate breaks its guardrail, so an impossible change
        is rejected at preview rather than after approval.
        """
        proposed = self._resolver.with_override(key, candidate)
        artefact = self._resolver.key(key)

        changes: list[OutcomeChange] = []
        for case in cases:
            after = self._decide(case, proposed)
            if after.outcome is not case.outcome:
                changes.append(
                    OutcomeChange(
                        case_id=case.case_id,
                        rule_id=case.rule_id,
                        before=case.outcome,
                        after=after.outcome,
                        amount_lkr=case.amount_lkr,
                    )
                )

        return ImpactReport(
            key=key,
            change_class=artefact.change_class,
            cases_evaluated=len(cases),
            changes=changes,
            generated_at=now,
            candidate_summary=f"{key} = {candidate.value} for {candidate.scope.label()}",
        )

    def preview_table(
        self,
        candidate: DecisionPolicy,
        cases: list[ReplayCase],
        *,
        version: str,
        now: datetime | None = None,
    ) -> ImpactReport:
        """Compare a candidate ZEN table with the currently active policy."""
        changes: list[OutcomeChange] = []
        for case in cases:
            after = self._decide(case, self._resolver, policy=candidate)
            if after.outcome is not case.outcome:
                changes.append(
                    OutcomeChange(
                        case_id=case.case_id,
                        rule_id=case.rule_id,
                        before=case.outcome,
                        after=after.outcome,
                        amount_lkr=case.amount_lkr,
                    )
                )
        return ImpactReport(
            key="decision.outcome_table",
            change_class=ChangeClass.C2_OUTCOME_AFFECTING,
            cases_evaluated=len(cases),
            changes=changes,
            generated_at=now,
            candidate_summary=f"decision table version {version}",
        )

    def _decide(
        self,
        case: ReplayCase,
        resolver: PolicyResolver,
        *,
        policy: DecisionPolicy | None = None,
    ) -> Decision:
        """Re-decide one case under a given resolver, at its original time."""
        as_of = case.decision_input.as_of
        context = {"rule": case.rule_id, "channel": case.channel}
        snapshot = resolver.snapshot_for(
            list(PolicyThresholds.KEYS.values()),
            as_of=as_of or (self._fallback_time(case)),
            context=context,
        )
        return (policy or self._policy).decide(
            case.decision_input,
            thresholds=PolicyThresholds.from_snapshot(
                snapshot, version=self._policy.thresholds.version
            ),
            config_snapshot_hash=snapshot.hash,
        )

    @staticmethod
    def _fallback_time(case: ReplayCase) -> datetime:
        raise ValueError(
            f"case {case.case_id} has no as_of, so it cannot be replayed "
            "point-in-time; re-evaluate it first"
        )


def cases_from(records: list[object]) -> list[ReplayCase]:
    """Build replay inputs from case records that have been decided.

    Cases without a stored decision input are skipped rather than guessed at:
    a replay that invents its inputs proves nothing.
    """
    cases: list[ReplayCase] = []
    for record in records:
        decision = getattr(record, "decision", None)
        decision_input = getattr(record, "decision_input", None)
        if decision is None or decision_input is None:
            continue
        evaluation = getattr(record, "evaluation", None)
        top = getattr(evaluation, "top", None) if evaluation else None
        cases.append(
            ReplayCase(
                case_id=getattr(record, "case_id", ""),
                decision_input=decision_input,
                rule_id=top.assessment.rule_id if top else None,
                outcome=decision.outcome,
                amount_lkr=decision.amount_lkr or ZERO,
                channel=record.case.origin_channel.value if hasattr(record, "case") else None,
            )
        )
    return cases
