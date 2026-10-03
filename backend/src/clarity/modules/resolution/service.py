"""The resolution service: the orchestration every channel shares (M-CASE).

One case file follows the customer across channels - "start on WhatsApp, finish
in the app or at a shop" (deck S5) - so the sequence of open, evidence, causes,
decision, proposal, confirmation, action and receipt lives here once rather than
in each channel.

This used to be ``CaseService``, a single class that both held the case and
called every other module. Plan 21 section 2.2 splits those two jobs: the case
aggregate keeps the record and its state machine
(``clarity.modules.case.aggregate``), and this service orchestrates. The win is
in the dependency map: orchestration points at domain logic and ``case`` becomes
a leaf, so the module holding a customer's case no longer drags five others with
it.

Channels and the API call this. They never reach the rule engine, the decision
policy or the tool layer directly, which is what keeps the money path identical
no matter where the customer started.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
from time import monotonic, sleep

from clarity.contracts.case import Case, CaseState, CaseTrigger
from clarity.contracts.decision import (
    ActionPlan,
    ActionType,
    Decision,
    Outcome,
)
from clarity.contracts.events import (
    ActionCompletedV1,
    CaseCreatedV1,
    CauseDetectedV1,
    DecisionGeneratedV1,
)
from clarity.contracts.receipt import TrustReceipt
from clarity.contracts.timeline import EvidenceSnapshot
from clarity.kernel.common import Channel, Language
from clarity.modules.actions.capability import ToolLayer
from clarity.modules.actions.public import (
    EXECUTABLE_OUTCOMES,
    ConfirmationToken,
    ExecutionResult,
    PlanNotPending,
)
from clarity.modules.case.public import (
    NO_CONFIRMATION_CHANNELS,
    CaseAggregate,
    CaseNotFound,
    CaseNotReady,
    CaseRecord,
)
from clarity.modules.decision.public import (
    DecisionPolicy,
    PolicyThresholds,
    build_decision_input,
    build_risk_signals,
)
from clarity.modules.detection.public import (
    PolicyRuleParameters,
    RuleEngine,
    RuleEvaluation,
)
from clarity.modules.receipts.public import ReceiptService
from clarity.modules.timeline.public import TimelineBuilder, TimelineRequest
from clarity.platform.config.resolver import PolicyResolver
from clarity.platform.config.switches import SwitchBoard, SwitchState
from clarity.platform.content.templates import explanation as customer_explanation
from clarity.platform.messaging.envelope import Event
from clarity.platform.messaging.outbox import outbox_in
from clarity.platform.observability import span
from clarity.platform.persistence import UnitOfWorkFactory

#: Kept for callers that imported it from the old module path.
_NO_CONFIRMATION_CHANNELS = NO_CONFIRMATION_CHANNELS


#: States that mean execution of this case has already begun. A plan stays
#: PENDING until ``execute`` runs, so two taps can both mint a confirmation
#: token, and the slower one can arrive here after the faster one has finished.
#: Testing only for EXECUTING made that caller try ACTIONED -> EXECUTING, which
#: the state machine refuses: one tap in a concurrent pair raised
#: IllegalTransition instead of joining the original outcome (D1).
#:
#: Skipping the advance is safe rather than lenient. The idempotency key below
#: still makes the tool layer report the duplicate as a replay, so this caller
#: takes the replay path and joins the winner's receipt.
_EXECUTION_BEGUN: frozenset[CaseState] = frozenset(
    {
        CaseState.EXECUTING,
        CaseState.ACTIONED,
        CaseState.RECEIPTED,
        CaseState.COMPENSATING,
    }
)


class ResolutionService:
    """Drives a case through its lifecycle, calling one module per step."""

    def __init__(
        self,
        *,
        aggregate: CaseAggregate,
        timeline: TimelineBuilder,
        rules: RuleEngine,
        policy: DecisionPolicy,
        tools: ToolLayer,
        receipts: ReceiptService,
        open_unit: UnitOfWorkFactory,
        deliver_events: Callable[[], None],
        policies: PolicyResolver | None = None,
        switches: SwitchBoard | None = None,
        clock: datetime | None = None,
    ) -> None:
        self._aggregate = aggregate
        self._timeline = timeline
        self._rules = rules
        self._policy = policy
        self._tools = tools
        self._receipts = receipts
        self._open_unit = open_unit
        # Runs the relay and the bus, so an event this call produced is acted on
        # before the call returns. The composition root binds it; this module
        # does not know which bus is behind it.
        self._deliver_events = deliver_events
        self._policies = policies
        self._switches = switches or SwitchBoard()
        self._clock = clock

    # -- the aggregate, delegated --------------------------------------- #
    #
    # The orchestration below reads and writes the case through these, exactly
    # as it did when both lived in one class. They are one line each on purpose:
    # the aggregate owns the state machine, and this service must not reach past
    # it to change a state directly.

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
        case = self._aggregate.open_case(
            subscriber_ref=subscriber_ref,
            msisdn_masked=msisdn_masked,
            channel=channel,
            trigger=trigger,
            language=language,
            charge_ref=charge_ref,
        )
        self._publish_case_created(case, subscriber_ref)
        return case

    def get(self, case_id: str) -> CaseRecord:
        return self._aggregate.get(case_id)

    def save(self, record: CaseRecord) -> None:
        self._aggregate.save(record)

    def all_cases(self) -> list[CaseRecord]:
        return self._aggregate.all_cases()

    def _cache_outcome(self, record: CaseRecord) -> None:
        self._aggregate._cache_outcome(record)

    def _advance(self, record: CaseRecord, target: CaseState) -> None:
        self._aggregate._advance(record, target)

    def _now(self) -> datetime:
        return self._aggregate._now()

    @staticmethod
    def _state_for(outcome: Outcome) -> CaseState:
        return CaseAggregate._state_for(outcome)

    @staticmethod
    def _require_decision(record: CaseRecord) -> Decision:
        return CaseAggregate._require_decision(record)

    def _safeguard_params(self, record: CaseRecord) -> dict[ActionType, dict[str, object]]:
        return self._aggregate._safeguard_params(record)

    @staticmethod
    def _flat_safeguard_params(record: CaseRecord) -> dict[str, object]:
        return CaseAggregate._flat_safeguard_params(record)

    def _publish_case_created(self, case: Case, subscriber_ref: str) -> None:
        """Say a case exists, so insights and autopsy can follow it (ADR-0029)."""
        with self._open_unit() as unit:
            outbox_in(unit).append(
                Event.of(
                    CaseCreatedV1(
                        case_id=case.case_id,
                        case_no=case.case_no,
                        channel=case.origin_channel,
                        trigger=case.trigger.value,
                        language=case.language,
                        money_at_stake_lkr=case.money_at_stake_lkr,
                    ),
                    subject=subscriber_ref,
                )
            )
            unit.commit()

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

    @property
    def executable_outcomes(self) -> frozenset[Outcome]:
        return EXECUTABLE_OUTCOMES

    def build_timeline(self, case_id: str) -> EvidenceSnapshot:
        record = self.get(case_id)
        snapshot = self._collect_evidence(record)
        self.save(record)
        return snapshot

    def _collect_evidence(self, record: CaseRecord) -> EvidenceSnapshot:
        """Collect evidence onto a record the caller holds and will save.

        Separate from ``build_timeline`` so a caller that already has the record
        works on that instance. Calling the public method instead would load a
        second copy, and on a driver that stores copies (B05) the caller's
        instance would then be stale: it would still be OPEN while the stored
        one had moved on.
        """
        self._advance(record, CaseState.COLLECTING_EVIDENCE)
        snapshot = self._timeline.build(
            TimelineRequest.for_case(record.case_id, record.subscriber_ref, now=self._now())
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
        with span("case.evaluate", case_id=case_id):
            return self._evaluate(case_id, customer_requested_human=customer_requested_human)

    def _evaluate(self, case_id: str, *, customer_requested_human: bool = False) -> Decision:
        record = self.get(case_id)
        if record.decision is not None and record.case.state in self._DECIDED_STATES:
            return record.decision

        snapshot = record.snapshot or self._collect_evidence(record)

        # Rule parameters are resolved for the moment the disputed event
        # happened, not for now, so a confidence Risk changed this morning does
        # not change what last week's case looks like (D5).
        evaluation = self._rules.evaluate(
            snapshot, parameters=self._rule_parameters(record, snapshot)
        )
        record.evaluation = evaluation

        top = evaluation.top
        rule_id = top.assessment.rule_id if top else None

        # Policy is resolved for the moment the disputed event happened, not
        # for now, so a customer is judged by the caps that applied then.
        as_of = self._as_of(record, evaluation)
        thresholds, snapshot_hash = self._thresholds_for(rule_id, record, as_of)
        record.thresholds = thresholds or self._policy.thresholds

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
        self.save(record)
        self._publish_evaluation(record)
        return decision

    def _publish_evaluation(self, record: CaseRecord) -> None:
        """Publish the detected cause and generated decision as immutable facts."""
        decision = self._require_decision(record)
        evaluation = record.evaluation
        snapshot = record.snapshot
        if evaluation is None or snapshot is None:  # pragma: no cover - evaluate builds both
            return
        with self._open_unit() as unit:
            outbox = outbox_in(unit)
            if evaluation.top is not None:
                assessment = evaluation.top.assessment
                outbox.append(
                    Event.of(
                        CauseDetectedV1(
                            case_id=record.case_id,
                            rule_id=assessment.rule_id,
                            rule_version=assessment.rule_version,
                            confidence=float(assessment.confidence),
                            snapshot_hash=snapshot.snapshot_hash,
                            ruled_out=[
                                f"{item.rule_id}@{item.rule_version}"
                                for item in evaluation.ruled_out
                            ],
                        ),
                        subject=record.subscriber_ref,
                    )
                )
            outbox.append(
                Event.of(
                    DecisionGeneratedV1(
                        case_id=record.case_id,
                        decision_id=decision.decision_id,
                        outcome=decision.outcome,
                        amount_lkr=decision.amount_lkr,
                        policy_version=decision.policy_version,
                        input_hash=decision.input_hash,
                        config_snapshot_hash=decision.config_snapshot_hash,
                    ),
                    subject=record.subscriber_ref,
                )
            )
            unit.commit()

    def _rule_parameters(
        self, record: CaseRecord, snapshot: EvidenceSnapshot
    ) -> PolicyRuleParameters | None:
        """Parameters for this evaluation, or ``None`` when no policy is loaded.

        ``as_of`` is taken from the evidence rather than from the matched cause,
        because the parameters are needed to score the match in the first place.
        The latest event in the snapshot is the disputed moment: the snapshot was
        built for this case and ends at the charge being complained about.
        """
        if self._policies is None:
            return None
        moments = [event.occurred_at for event in snapshot.events]
        return PolicyRuleParameters(
            self._policies,
            as_of=max(moments) if moments else self._now(),
        )

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
            four_eyes_threshold_lkr=record.thresholds.four_eyes_threshold_lkr
            if record.thresholds
            else None,
            now=self._now(),
        )
        record.plans[plan.plan_id] = plan
        self.save(record)
        return plan

    def confirm_and_execute(
        self, case_id: str, plan_id: str
    ) -> tuple[ExecutionResult, TrustReceipt]:
        """The customer tapped Confirm.

        The confirmation token is minted and spent inside this call, so it
        never travels to a client - and therefore can never be replayed, or
        obtained by anything on the AI path (plan §10.5). A second tap, at the
        same moment or later, returns the original result and receipt.
        """
        record = self.get(case_id)
        with span("case.confirm_and_execute", case_id=case_id, plan_id=plan_id):
            done = self._already_done(record, plan_id)
            if done is not None:
                return done
            try:
                token = self._tools.confirm_by_customer(
                    plan_id, subscriber_ref=record.subscriber_ref, now=self._now()
                )
            except PlanNotPending:
                return self._join_original(record, plan_id)
            return self._execute(record, plan_id, token)

    def approve_and_execute(
        self, case_id: str, plan_id: str, *, approver_ref: str, role: str, mfa_step_up: bool = True
    ) -> tuple[ExecutionResult, TrustReceipt] | None:
        """A staff member approved. Returns ``None`` if more approval is needed."""
        record = self.get(case_id)
        done = self._already_done(record, plan_id)
        if done is not None:
            return done
        try:
            token = self._tools.approve_by_staff(
                plan_id,
                approver_ref=approver_ref,
                role=role,
                mfa_step_up=mfa_step_up,
                now=self._now(),
            )
        except PlanNotPending:
            return self._join_original(record, plan_id)
        if token is None:
            return None
        return self._execute(record, plan_id, token)

    def auto_fix(
        self, case_id: str, plan_id: str, *, triggered_by: str = "clarity-stream-detector"
    ) -> tuple[ExecutionResult, TrustReceipt]:
        """Zero-contact execution of a whitelisted AUTO_FIX (deck S5)."""
        record = self.get(case_id)
        done = self._already_done(record, plan_id)
        if done is not None:
            return done
        try:
            token = self._tools.authorise_auto_fix(
                plan_id, triggered_by=triggered_by, now=self._now()
            )
        except PlanNotPending:
            return self._join_original(record, plan_id)
        return self._execute(record, plan_id, token)

    def on_action_completed(self, event: Event) -> None:
        """Issue the receipt for a plan the tool layer completed.

        The consumer for ``action.completed`` (B06). Registered by the
        composition root, which is also what makes this the first flow where a
        side effect is the consequence of a fact rather than a second call
        inside the money path.

        Idempotent by plan id: delivery is at-least-once, so this runs again on
        a redelivery and must not chain a second receipt (D1).
        """
        payload = event.payload()
        if not isinstance(payload, ActionCompletedV1):  # pragma: no cover - type guard
            return
        with span(
            "receipts.on_action_completed",
            case_id=payload.case_id,
            plan_id=payload.plan_id,
            event_id=event.id,
        ):
            if self._receipts.for_plan(payload.plan_id) is not None:
                return
            try:
                record = self._aggregate.get(payload.case_id)
            except CaseNotFound:
                raise
            receipt = self._issue_receipt(record, plan_id=payload.plan_id)
            record.receipts_by_plan[payload.plan_id] = receipt
            self._cache_outcome(record)

    def _join_original(
        self, record: CaseRecord, plan_id: str, *, timeout_seconds: float = 10.0
    ) -> tuple[ExecutionResult, TrustReceipt]:
        """Return the outcome of a plan another caller is already executing.

        This is what replaced the per-plan lock (D1, B06). Two taps on one plan
        no longer queue behind a lock: the first one wins the plan, and the
        second finds it is no longer pending and joins that outcome instead of
        failing or acting again. One tap, one refund, one receipt.

        Draining blocks on the partition the event is on, so in the common case
        this returns as soon as the winner's receipt is issued rather than
        polling. The wait exists because the winner may not have committed its
        event yet when this call arrives. A durable claim that removes the wait
        entirely needs database row locks, which is M-ACT.
        """
        deadline = monotonic() + timeout_seconds
        while True:
            self._drain()
            done = self._already_done(record, plan_id)
            if done is not None:
                return done
            if monotonic() >= deadline:
                raise CaseNotReady(
                    f"plan {plan_id} is being executed by another request and its "
                    f"outcome did not arrive within {timeout_seconds:.0f}s"
                )
            sleep(0.001)

    def _drain(self) -> None:
        """Let the relay publish and the consumers run."""
        self._deliver_events()

    def _receipt_for_plan(self, plan_id: str) -> TrustReceipt | None:
        """The one receipt a completed plan produced, from the receipts module."""
        return self._receipts.for_plan(plan_id)

    def _already_done(
        self, record: CaseRecord, plan_id: str
    ) -> tuple[ExecutionResult, TrustReceipt] | None:
        """The original outcome of a plan that has already run, marked as a replay.

        The receipt comes from the receipts module rather than this record,
        because that index is what makes one plan have one receipt.
        """
        receipt = self._receipt_for_plan(plan_id)
        result = self._tools.result_for(plan_id)
        if receipt is None or result is None:
            return None
        return replace(result, replayed=True), receipt

    def _execute(
        self, record: CaseRecord, plan_id: str, token: ConfirmationToken
    ) -> tuple[ExecutionResult, TrustReceipt]:
        if record.case.state not in _EXECUTION_BEGUN:
            self._advance(record, CaseState.EXECUTING)
            # Tolerant, like the other outcome writes: two confirmations of one
            # plan both move the case to EXECUTING, so a conflict here is the
            # other request having written the identical state.
            self._cache_outcome(record)

        result = self._tools.execute(
            plan_id,
            confirmation=token,
            idempotency_key=f"{record.case_id}:{plan_id}",
            now=self._now(),
        )
        if result.replayed:
            # The tool layer recognised this as a duplicate of a request it had
            # already run (M-ACT). Nothing happened, so nothing may move: the
            # original call advanced the case and issued the receipt, and
            # advancing again would be an illegal transition out of RECEIPTED.
            return result, self._join_original(record, plan_id)[1]

        record.execution = result
        self._advance(record, CaseState.ACTIONED)
        # Saved before the drain: the consumer reads this record to build the
        # receipt, and a driver that stores a copy would otherwise show it the
        # state from before the execution.
        self._cache_outcome(record)

        # The tool layer wrote action.completed in the same transaction as the
        # plan (B04). Draining it here is what turns the receipt into the
        # consequence of the event rather than a second call on the money path:
        # if this process dies first, the relay issues the receipt on restart.
        self._drain()
        receipt = self._receipt_for_plan(plan_id)
        if receipt is None:
            raise CaseNotReady(
                f"plan {plan_id} completed but its receipt has not been issued; "
                "the relay or the receipts consumer is not running"
            )
        record.receipts_by_plan[plan_id] = receipt
        self._cache_outcome(record)
        return result, receipt

    # ------------------------------------------------------------------ #
    # Prove
    # ------------------------------------------------------------------ #

    def issue_explanation_receipt(self, case_id: str) -> TrustReceipt:
        """A receipt for an explain-only outcome: nothing moved, and that is the proof."""
        record = self.get(case_id)
        self._require_decision(record)
        return self._issue_receipt(record, plan_id=None)

    def _issue_receipt(self, record: CaseRecord, *, plan_id: str | None) -> TrustReceipt:
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
            plan_id=plan_id,
            now=self._now(),
        )
        record.receipt = receipt
        self._advance(record, CaseState.RECEIPTED)
        self.save(record)
        return receipt

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #


__all__ = ["ResolutionService"]
