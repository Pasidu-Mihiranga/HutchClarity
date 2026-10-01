"""Case service: the orchestration every channel shares (plan §3.1, §16.2).

One case file follows the customer across channels — "start on WhatsApp,
finish in the app or at a shop" (deck S5) — so the sequence of
open → evidence → causes → decision → proposal → confirmation → action →
receipt lives here once, not in each channel.

Channels and the API call this. They never reach into the rule engine, the
decision policy or the tool layer directly, which is what keeps the money path
identical no matter where the customer started.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime

from clarity.core.content.templates import explanation as customer_explanation
from clarity.core.decision.assessor import build_decision_input, build_risk_signals
from clarity.core.decision.policy import DecisionPolicy, PolicyThresholds
from clarity.core.policy.resolver import PolicyResolver
from clarity.core.policy.switches import SwitchBoard, SwitchState
from clarity.core.receipts.service import ReceiptService
from clarity.core.rules.engine import RuleEngine, RuleEvaluation
from clarity.core.timeline.builder import TimelineBuilder, TimelineRequest
from clarity.core.tools.confirmation import ConfirmationToken
from clarity.core.tools.layer import EXECUTABLE_OUTCOMES, ExecutionResult, ToolLayer
from clarity.schemas.case import Case, CaseState, CaseTrigger, CustomerReference
from clarity.schemas.common import Channel, Language, utc_now
from clarity.schemas.decision import (
    ActionPlan,
    ActionType,
    Decision,
    DecisionInput,
    Outcome,
)
from clarity.schemas.ids import case_no as make_case_no
from clarity.schemas.ids import new_id
from clarity.schemas.receipt import TrustReceipt
from clarity.schemas.timeline import EvidenceSnapshot

#: Channels that cannot capture a reliable confirmation for a service change
#: (plan §9.7). The decision policy uses this to route them to staff.
_NO_CONFIRMATION_CHANNELS = frozenset({Channel.SMS, Channel.USSD})


class CaseNotFound(KeyError):
    pass


class CaseNotReady(RuntimeError):
    """An operation was attempted before the case reached the needed state."""


@dataclass
class CaseRecord:
    """Everything known about one case, in one place."""

    case: Case
    subscriber_ref: str
    snapshot: EvidenceSnapshot | None = None
    evaluation: RuleEvaluation | None = None
    decision: Decision | None = None
    decision_input: DecisionInput | None = None
    """Kept so the case can be re-decided under a candidate policy (§19 4.1)."""
    plans: dict[str, ActionPlan] = field(default_factory=dict)
    execution: ExecutionResult | None = None
    receipt: TrustReceipt | None = None

    @property
    def case_id(self) -> str:
        return self.case.case_id


class CaseService:
    """Drives a case through its lifecycle."""

    def __init__(
        self,
        *,
        timeline: TimelineBuilder,
        rules: RuleEngine,
        policy: DecisionPolicy,
        tools: ToolLayer,
        receipts: ReceiptService,
        policies: PolicyResolver | None = None,
        switches: SwitchBoard | None = None,
        clock: datetime | None = None,
    ) -> None:
        self._timeline = timeline
        self._rules = rules
        self._policy = policy
        self._tools = tools
        self._receipts = receipts
        self._policies = policies
        self._switches = switches or SwitchBoard()
        self._clock = clock
        self._cases: dict[str, CaseRecord] = {}
        self._sequence = 0
        self._lock = threading.Lock()

    @property
    def switches(self) -> SwitchBoard:
        return self._switches

    @property
    def policies(self) -> PolicyResolver | None:
        return self._policies

    @property
    def rules(self) -> RuleEngine:
        return self._rules

    @property
    def receipts(self) -> ReceiptService:
        return self._receipts

    def _now(self) -> datetime:
        """Fixed clock in the demo, wall clock otherwise."""
        return self._clock or utc_now()

    # ------------------------------------------------------------------ #
    # Open
    # ------------------------------------------------------------------ #

    def open_case(
        self,
        *,
        subscriber_ref: str,
        msisdn_masked: str,
        channel: Channel,
        trigger: CaseTrigger = CaseTrigger.CUSTOMER,
        language: Language = Language.EN,
        charge_ref: str | None = None,
    ) -> Case:
        with self._lock:
            self._sequence += 1
            case = Case(
                case_id=new_id("CASE"),
                case_no=make_case_no(self._sequence, year=self._now().year),
                customer=CustomerReference(
                    subscriber_ref=subscriber_ref,
                    msisdn_masked=msisdn_masked,
                    preferred_language=language,
                ),
                trigger=trigger,
                origin_channel=channel,
                language=language,
                charge_ref=charge_ref,
                opened_at=self._now(),
            )
            self._cases[case.case_id] = CaseRecord(case=case, subscriber_ref=subscriber_ref)
            return case

    def get(self, case_id: str) -> CaseRecord:
        record = self._cases.get(case_id)
        if record is None:
            raise CaseNotFound(case_id)
        return record

    def all_cases(self) -> list[CaseRecord]:
        return list(self._cases.values())

    # ------------------------------------------------------------------ #
    # Evidence and decision
    # ------------------------------------------------------------------ #

    def build_timeline(self, case_id: str) -> EvidenceSnapshot:
        record = self.get(case_id)
        self._advance(record, CaseState.COLLECTING_EVIDENCE)
        snapshot = self._timeline.build(
            TimelineRequest.for_case(case_id, record.subscriber_ref, now=self._now())
        )
        record.snapshot = snapshot
        return snapshot

    #: Once a case has been decided, re-reading it must not re-decide it.
    _DECIDED_STATES = frozenset(
        {
            CaseState.AWAITING_CUSTOMER,
            CaseState.AWAITING_APPROVAL,
            CaseState.EXPLAINED,
            CaseState.HANDED_OFF,
            CaseState.EXECUTING,
            CaseState.ACTIONED,
            CaseState.RECEIPTED,
            CaseState.CLOSED,
        }
    )

    def evaluate(self, case_id: str, *, customer_requested_human: bool = False) -> Decision:
        """Run the rules and the decision policy. No side effects on the account.

        Idempotent: opening a case that has already been decided returns the
        decision that was made, rather than deciding it again. An agent reading
        a case in the Desk must not change its outcome by looking at it, and a
        receipt already references the original decision.
        """
        record = self.get(case_id)
        if record.decision is not None and record.case.state in self._DECIDED_STATES:
            return record.decision

        snapshot = record.snapshot or self.build_timeline(case_id)

        evaluation = self._rules.evaluate(snapshot)
        record.evaluation = evaluation

        top = evaluation.top
        rule_id = top.assessment.rule_id if top else None

        # Policy is resolved for the moment the disputed event happened, not
        # for now, so a customer is judged by the caps that applied then.
        as_of = self._as_of(record, evaluation)
        thresholds, snapshot_hash = self._thresholds_for(rule_id, record, as_of)

        decision_input = build_decision_input(
            case_id=case_id,
            snapshot=snapshot,
            evaluation=evaluation,
            risk=build_risk_signals(
                snapshot,
                now=self._now(),
                customer_requested_human=customer_requested_human,
            ),
            budget=self._tools.budget.state_for(rule_id),
            channel_supports_confirmation=record.case.origin_channel
            not in _NO_CONFIRMATION_CHANNELS,
            as_of=as_of,
        )
        decision = self._policy.decide(
            decision_input,
            allowed_actions=top.assessment.allowed_actions if top else [],
            ruled_out=evaluation.ruled_out,
            thresholds=thresholds,
            switches=SwitchState.of(self._switches, rule_id=rule_id),
            config_snapshot_hash=snapshot_hash,
        )
        record.decision = decision
        record.decision_input = decision_input

        if top is not None:
            record.case = record.case.model_copy(
                update={"money_at_stake_lkr": top.assessment.money_effect_lkr}
            )

        self._advance(record, CaseState.EVALUATED)
        self._advance(record, self._state_for(decision.outcome))
        return decision

    def _as_of(self, record: CaseRecord, evaluation: RuleEvaluation) -> datetime:
        """When the disputed event happened.

        The matched cause's own evidence is the best answer; falling back to
        the case opening time, and then to now.
        """
        top = evaluation.top
        if top is not None and top.bindings:
            return min(event.occurred_at for event in top.bindings.values())
        return record.case.opened_at or self._now()

    def _thresholds_for(
        self, rule_id: str | None, record: CaseRecord, as_of: datetime
    ) -> tuple[PolicyThresholds | None, str | None]:
        """Resolve the decision thresholds that applied at ``as_of``.

        Without a resolver the policy keeps its own defaults, so the core works
        with no policy files present.
        """
        if self._policies is None:
            return None, None

        context = {
            "rule": rule_id,
            "channel": record.case.origin_channel.value,
            "subscriber": record.subscriber_ref,
        }
        snapshot = self._policies.snapshot_for(
            list(PolicyThresholds.KEYS.values()), as_of=as_of, context=context
        )
        return (
            PolicyThresholds.from_snapshot(snapshot, version=self._policy.thresholds.version),
            snapshot.hash,
        )

    @staticmethod
    def _state_for(outcome: Outcome) -> CaseState:
        match outcome:
            case Outcome.AUTO_FIX:
                return CaseState.EXECUTING
            case Outcome.ONE_TAP_FIX:
                return CaseState.AWAITING_CUSTOMER
            case Outcome.STAFF_APPROVAL:
                return CaseState.AWAITING_APPROVAL
            case Outcome.EXPLAIN_ONLY:
                return CaseState.EXPLAINED
            case _:
                return CaseState.HANDED_OFF

    # ------------------------------------------------------------------ #
    # Act
    # ------------------------------------------------------------------ #

    def propose(
        self,
        case_id: str,
        *,
        created_by: str,
        action_types: list[ActionType] | None = None,
    ) -> ActionPlan:
        """Build a plan. Still changes nothing on the account."""
        record = self.get(case_id)
        decision = self._require_decision(record)

        plan = self._tools.propose(
            decision,
            subscriber_ref=record.subscriber_ref,
            created_by=created_by,
            action_types=action_types,
            params=self._safeguard_params(record),
            rule_id=record.evaluation.top.assessment.rule_id
            if record.evaluation and record.evaluation.top
            else None,
            now=self._now(),
        )
        record.plans[plan.plan_id] = plan
        return plan

    def confirm_and_execute(
        self, case_id: str, plan_id: str
    ) -> tuple[ExecutionResult, TrustReceipt]:
        """The customer tapped Confirm.

        The confirmation token is minted and spent inside this call, so it
        never travels to a client — and therefore can never be replayed, or
        obtained by anything on the AI path (plan §10.5).
        """
        record = self.get(case_id)
        token = self._tools.confirm_by_customer(
            plan_id, subscriber_ref=record.subscriber_ref, now=self._now()
        )
        return self._execute(record, plan_id, token)

    def approve_and_execute(
        self, case_id: str, plan_id: str, *, approver_ref: str, role: str, mfa_step_up: bool = True
    ) -> tuple[ExecutionResult, TrustReceipt] | None:
        """A staff member approved. Returns ``None`` if more approval is needed."""
        record = self.get(case_id)
        token = self._tools.approve_by_staff(
            plan_id,
            approver_ref=approver_ref,
            role=role,
            mfa_step_up=mfa_step_up,
            now=self._now(),
        )
        if token is None:
            return None
        return self._execute(record, plan_id, token)

    def auto_fix(self, case_id: str, plan_id: str) -> tuple[ExecutionResult, TrustReceipt]:
        """Zero-contact execution of a whitelisted AUTO_FIX (deck S5)."""
        record = self.get(case_id)
        token = self._tools.authorise_auto_fix(plan_id, now=self._now())
        return self._execute(record, plan_id, token)

    def _execute(
        self, record: CaseRecord, plan_id: str, token: ConfirmationToken
    ) -> tuple[ExecutionResult, TrustReceipt]:
        if record.case.state is not CaseState.EXECUTING:
            self._advance(record, CaseState.EXECUTING)

        result = self._tools.execute(
            plan_id,
            confirmation=token,
            idempotency_key=f"{record.case_id}:{plan_id}",
            now=self._now(),
        )
        record.execution = result
        self._advance(record, CaseState.ACTIONED)

        receipt = self._issue_receipt(record, self._tools.plan(plan_id))
        return result, receipt

    # ------------------------------------------------------------------ #
    # Prove
    # ------------------------------------------------------------------ #

    def issue_explanation_receipt(self, case_id: str) -> TrustReceipt:
        """A receipt for an explain-only outcome: nothing moved, and that is the proof."""
        record = self.get(case_id)
        self._require_decision(record)
        return self._issue_receipt(record, None)

    def _issue_receipt(self, record: CaseRecord, plan: ActionPlan | None) -> TrustReceipt:
        decision = self._require_decision(record)
        cause = (
            record.evaluation.top.assessment
            if record.evaluation and record.evaluation.top
            else None
        )
        snapshot = record.snapshot
        if snapshot is None:  # pragma: no cover - evaluate() always builds one
            raise CaseNotReady("a receipt needs the evidence the decision was made on")

        receipt = self._receipts.issue(
            case=record.case,
            decision=decision,
            cause=cause,
            snapshot=snapshot,
            execution=record.execution,
            # The receipt is read by the customer, so its summary is in their
            # language. The rule id and version are already structured fields
            # on the payload for audit, so nothing is lost by not repeating
            # them in English here.
            summary=customer_explanation(
                rule_id=cause.rule_id if cause else None,
                outcome=decision.outcome,
                amount=decision.amount_lkr,
                language=record.case.language,
            ),
            subscriber_ref=record.subscriber_ref,
            safeguard_params=self._flat_safeguard_params(record),
            now=self._now(),
        )
        record.receipt = receipt
        self._advance(record, CaseState.RECEIPTED)
        return receipt

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    @staticmethod
    def _require_decision(record: CaseRecord) -> Decision:
        if record.decision is None:
            raise CaseNotReady(f"case {record.case_id} has not been evaluated yet")
        return record.decision

    def _safeguard_params(self, record: CaseRecord) -> dict[ActionType, dict[str, object]]:
        """Fill action parameters from evidence, not from the caller.

        The subscription and merchant a remedy applies to come from the events
        the rule matched, so a caller cannot redirect a block onto a different
        merchant.
        """
        flat = self._flat_safeguard_params(record)
        return {
            ActionType.DEACTIVATE_VAS: {k: v for k, v in flat.items() if k == "subscription_id"},
            ActionType.BLOCK_MERCHANT_UNTIL_OPTIN: {
                k: v for k, v in flat.items() if k == "merchant_id"
            },
        }

    @staticmethod
    def _flat_safeguard_params(record: CaseRecord) -> dict[str, object]:
        evaluation, snapshot = record.evaluation, record.snapshot
        if evaluation is None or evaluation.top is None or snapshot is None:
            return {}

        params: dict[str, object] = {}
        for event in evaluation.top.bindings.values():
            for key in ("subscription_id", "merchant_id", "bucket", "offering_id"):
                value = event.attr(key)
                if value is not None and key not in params:
                    params[key] = value
        return params

    def _advance(self, record: CaseRecord, target: CaseState) -> None:
        """Move the case on, tolerating a no-op when it is already there."""
        if record.case.state is target:
            return
        record.case = record.case.with_state(target)

    @property
    def executable_outcomes(self) -> frozenset[Outcome]:
        return EXECUTABLE_OUTCOMES
