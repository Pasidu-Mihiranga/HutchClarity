"""The tool layer: the only path from a decision to a change in a HUTCH system.

Deck S7 calls this "Act - confirmed, idempotent". Its job is to make four
promises hold, whatever is calling it:

1. **Only what the decision allowed.** Actions outside ``Decision.allowed_actions``
   are refused, and amounts come from the decision, never from the caller. A
   model that hallucinates a remedy or an amount gets a typed refusal.
2. **Nothing without confirmation.** Execution requires a single-use token
   minted outside the AI path (customer tap, staff approval, or the system for
   a whitelisted AUTO_FIX).
3. **Never twice.** One idempotency key per plan; replays return the first
   result instead of acting again.
4. **All or nothing.** If a later step fails, the applied steps are
   compensated and the case goes to a human.
"""

from __future__ import annotations

import threading
from contextlib import suppress
from dataclasses import replace
from datetime import datetime
from decimal import Decimal
from time import monotonic, sleep
from typing import Any

from clarity.contracts.decision import (
    ACTION_SAFETY,
    Action,
    ActionPlan,
    ActionStatus,
    ActionType,
    Approval,
    Decision,
    Outcome,
    PlanStatus,
    PlanStep,
)
from clarity.contracts.events import (
    ActionCompletedV1,
    ActionFailedV1,
    ActionStepV1,
    ApprovalRequestedV1,
    EventPayload,
)
from clarity.integration.ports import AdapterError, Command, CommandPort, CommandResult
from clarity.kernel.common import ActionSafetyLevel, utc_now
from clarity.kernel.ids import new_id
from clarity.modules.actions.attempts import (
    AttemptLog,
    AttemptLost,
    AttemptRecord,
    AttemptState,
)
from clarity.modules.actions.budget import RefundBudget, Reservation
from clarity.modules.actions.confirmation import ConfirmationService
from clarity.modules.actions.errors import (
    ActionNotAllowed,
    ApprovalRequired,
    BudgetExhausted,
    ConfirmationInvalid,
    ConfirmationRequired,
    ExecutionFailed,
    ExecutionInProgress,
    OutcomeNotExecutable,
    PlanNotFound,
    PlanNotPending,
    ToolLayerError,
)
from clarity.modules.actions.records import FOUR_EYES_THRESHOLD_LKR, PlanRecord
from clarity.modules.actions.repository import PLANS, PlanRepository, StoredPlanRepository
from clarity.modules.actions.results import (
    EXECUTABLE_OUTCOMES,
    ConfirmationToken,
    ConfirmedBy,
    ExecutionResult,
)
from clarity.platform.messaging.envelope import Event
from clarity.platform.messaging.outbox import outbox_in
from clarity.platform.observability import span
from clarity.platform.persistence import UnitOfWorkFactory

#: Stable code -> the refusal to raise again on a replay.
#:
#: A settled attempt stores its code, not the exception object, because the
#: record outlives the process and crosses replicas. Rebuilding the same type
#: means a duplicate request gets the refusal the original caller got, rather
#: than a generic failure that a caller would handle differently.
_REFUSALS: dict[str, type[ToolLayerError]] = {
    error.code: error
    for error in (
        ActionNotAllowed,
        ApprovalRequired,
        BudgetExhausted,
        ConfirmationInvalid,
        ConfirmationRequired,
        ExecutionFailed,
        OutcomeNotExecutable,
        PlanNotFound,
        PlanNotPending,
    )
}

#: Actions whose effect can be undone if a later step in the plan fails.
_COMPENSATIONS: dict[ActionType, ActionType | None] = {
    ActionType.SET_SPEND_CAP: None,
    ActionType.ENABLE_DATA_STOP: None,
    ActionType.ENABLE_FUP_ALERTS: None,
}


class ToolLayer:
    """Holds the only reference to a command port (plan §9.1 principle 2)."""

    def __init__(
        self,
        command_port: CommandPort,
        *,
        budget: RefundBudget | None = None,
        plans: PlanRepository,
        open_unit: UnitOfWorkFactory,
        confirmations: ConfirmationService | None = None,
        duplicate_wait_seconds: float = 10.0,
    ) -> None:
        self._commands = command_port
        self._budget = budget or RefundBudget()
        self._confirmations = confirmations or ConfirmationService(open_unit)
        # Plans live in the repository (B02); the layer keeps no business state.
        self._plans = plans
        # Completing a plan writes the plan and its event in one transaction
        # (I7, B04), so nobody can observe a completed plan with no event.
        self._open_unit = open_unit
        # Durable idempotency (M-ACT): one record per key, in the repository, so
        # the guarantee survives a restart and holds across replicas.
        self._attempts = AttemptLog(open_unit)
        self._lock = threading.Lock()
        self._duplicate_wait_seconds = duplicate_wait_seconds

    @property
    def budget(self) -> RefundBudget:
        return self._budget

    # ------------------------------------------------------------------ #
    # 1. Propose
    # ------------------------------------------------------------------ #

    def propose(
        self,
        decision: Decision,
        *,
        subscriber_ref: str,
        created_by: str,
        action_types: list[ActionType] | None = None,
        params: dict[ActionType, dict[str, Any]] | None = None,
        rule_id: str | None = None,
        four_eyes_threshold_lkr: Decimal | None = None,
        now: datetime | None = None,
    ) -> ActionPlan:
        """Build a plan from a decision. Creates no change by itself.

        ``action_types`` defaults to the full remedy the decision allowed. A
        caller may narrow it, never widen it. Amounts are taken from the
        decision, so a caller cannot influence how much money moves.
        """
        if decision.outcome not in EXECUTABLE_OUTCOMES:
            raise OutcomeNotExecutable(f"a {decision.outcome.value} decision authorises no action")

        wanted = list(action_types or decision.allowed_actions)
        if not wanted:
            raise ActionNotAllowed("the decision allows no actions")

        disallowed = [a for a in wanted if a not in decision.allowed_actions]
        if disallowed:
            raise ActionNotAllowed(
                f"{', '.join(a.value for a in disallowed)} "
                f"is not permitted for case {decision.case_id}"
            )

        step_params = params or {}
        steps = [
            PlanStep(
                action_type=action_type,
                safety_level=ACTION_SAFETY[action_type],
                # Only the money-moving step carries the amount, and it comes
                # from the decision record.
                amount_lkr=decision.amount_lkr if action_type is ActionType.REFUND else None,
                params=dict(step_params.get(action_type, {})) | {"subscriber_ref": subscriber_ref},
            )
            for action_type in wanted
        ]

        plan = ActionPlan(
            plan_id=new_id("PLAN"),
            case_id=decision.case_id,
            decision_id=decision.decision_id,
            outcome=decision.outcome,
            steps=steps,
            created_by=created_by,
            display_summary=self._summarise(decision, wanted),
            created_at=now or utc_now(),
        )
        self._plans.save(
            PlanRecord(
                plan=plan,
                decision=decision,
                rule_id=rule_id,
                four_eyes_threshold_lkr=(
                    four_eyes_threshold_lkr
                    if four_eyes_threshold_lkr is not None
                    else FOUR_EYES_THRESHOLD_LKR
                ),
            )
        )
        return plan

    @staticmethod
    def _summarise(decision: Decision, actions: list[ActionType]) -> str:
        parts: list[str] = []
        for action in actions:
            match action:
                case ActionType.REFUND:
                    parts.append(f"return LKR {decision.amount_lkr}")
                case ActionType.DEACTIVATE_VAS:
                    parts.append("switch the subscription off")
                case ActionType.BLOCK_MERCHANT_UNTIL_OPTIN:
                    parts.append("block the merchant until you opt in")
                case ActionType.SET_SPEND_CAP:
                    parts.append("cap your spending")
                case ActionType.ENABLE_DATA_STOP:
                    parts.append("stop data when a pack ends")
                case ActionType.ENABLE_FUP_ALERTS:
                    parts.append("alert you at 80% and 95%")
                case _:
                    parts.append(action.value.lower().replace("_", " "))
        return ", ".join(parts)

    def plan(self, plan_id: str) -> ActionPlan:
        return self._record(plan_id).plan

    def result_for(self, plan_id: str) -> ExecutionResult | None:
        """The outcome of a plan's execution, including a compensated one."""
        return self._record(plan_id).result

    # ------------------------------------------------------------------ #
    # 2. Confirm or approve - always outside the AI path
    # ------------------------------------------------------------------ #

    def confirm_by_customer(
        self, plan_id: str, *, subscriber_ref: str, now: datetime | None = None
    ) -> ConfirmationToken:
        """The customer tapped Confirm. Only valid for a one-tap decision."""
        record = self._pending(plan_id)
        if record.plan.outcome is not Outcome.ONE_TAP_FIX:
            raise ConfirmationRequired(
                f"a {record.plan.outcome.value} decision is not the customer's to confirm"
            )
        return self._confirmations.mint(
            plan_id, confirmed_by=ConfirmedBy.CUSTOMER, principal_ref=subscriber_ref, now=now
        )

    def approve_by_staff(
        self,
        plan_id: str,
        *,
        approver_ref: str,
        role: str,
        mfa_step_up: bool,
        now: datetime | None = None,
    ) -> ConfirmationToken | None:
        """Record a staff approval; mint a token once enough approvals exist.

        Returns ``None`` while more approval is still needed, so a caller
        cannot mistake a partial four-eyes approval for authority to execute.
        """
        record = self._pending(plan_id)
        if record.plan.outcome is not Outcome.STAFF_APPROVAL:
            raise ApprovalRequired(
                f"a {record.plan.outcome.value} decision is not a staff approval"
            )
        if not mfa_step_up:
            raise ApprovalRequired("approving an action requires MFA step-up")
        if approver_ref == record.plan.created_by:
            raise ApprovalRequired("the maker of a plan cannot approve it")
        if any(a.approver_ref == approver_ref for a in record.approvals):
            raise ApprovalRequired("this approver has already signed off")

        record.approvals.append(
            Approval(
                approval_id=new_id("APR"),
                action_id=plan_id,
                approver_ref=approver_ref,
                role=role,
                decision="approved",
                mfa_step_up=mfa_step_up,
                at=now or utc_now(),
            )
        )
        self._save(record)

        if len(record.approvals) < self._approvals_needed(record):
            # Still short. Say so on the bus, so a supervisor can be told
            # rather than the plan waiting for somebody to notice (M-ACT).
            self._publish_approval_requested(record)
            return None

        roles = {a.role for a in record.approvals}
        if self._approvals_needed(record) > 1 and len(roles) < 2:
            raise ApprovalRequired(
                "four-eyes approval needs two different roles, e.g. a supervisor and finance"
            )

        return self._confirmations.mint(
            plan_id, confirmed_by=ConfirmedBy.STAFF, principal_ref=approver_ref, now=now
        )

    @staticmethod
    def _approvals_needed(record: PlanRecord) -> int:
        return 2 if record.plan.total_amount_lkr > record.four_eyes_threshold_lkr else 1

    def authorise_auto_fix(
        self,
        plan_id: str,
        *,
        triggered_by: str = "clarity-stream-detector",
        now: datetime | None = None,
    ) -> ConfirmationToken:
        """System authority for a whitelisted AUTO_FIX (deck S5 zero-contact).

        This is the one path with no human in the loop, so it is deliberately
        a separate method that refuses any other outcome.
        """
        record = self._pending(plan_id)
        if record.plan.outcome is not Outcome.AUTO_FIX:
            raise ConfirmationRequired(
                f"only an AUTO_FIX decision may self-authorise, not {record.plan.outcome.value}"
            )
        return self._confirmations.mint(
            plan_id,
            confirmed_by=ConfirmedBy.SYSTEM,
            # The authority is the policy (ConfirmedBy.SYSTEM); this records
            # what asked for it: the stream detector, or the caller who opened
            # the case in the zero-contact demo.
            principal_ref=triggered_by,
            now=now,
        )

    # ------------------------------------------------------------------ #
    # 3. Execute
    # ------------------------------------------------------------------ #

    def execute(
        self,
        plan_id: str,
        *,
        confirmation: str | ConfirmationToken | None,
        idempotency_key: str,
        now: datetime | None = None,
    ) -> ExecutionResult:
        """Apply a confirmed plan. Idempotent on ``idempotency_key``.

        The key is claimed **before** the confirmation token is redeemed, so a
        duplicate that arrives while the first call is still running waits for
        it and receives the same outcome. Claiming afterwards would let the
        duplicate find the token already spent and fail with
        ``CONFIRMATION_INVALID`` even though the fix had succeeded, which is
        what a customer double-tapping Confirm would have seen.
        """
        try:
            claimed = self._attempts.claim(idempotency_key, plan_id=plan_id)
        except AttemptLost:
            # Someone else owns this key: either it is running now, or it has
            # already settled and the answer is recorded.
            return self._settled_outcome(idempotency_key)

        try:
            result = self._execute_claimed(
                plan_id, confirmation=confirmation, idempotency_key=idempotency_key, now=now
            )
        except ToolLayerError as refusal:
            # A final refusal is recorded so a duplicate gets the same answer. A
            # transient failure leaves the key claimable, so a retry after the
            # cause has passed gets a genuine new attempt rather than a replay
            # of yesterday's "budget exhausted" forever (M-ACT).
            self._record_failure(claimed, idempotency_key, plan_id, refusal)
            raise
        except BaseException as unexpected:
            # Not a typed refusal, so nothing is known about whether it is safe
            # to retry. Treated as final, which is the cautious side on a money
            # path: a stuck plan is recoverable by a person, a double refund is
            # not.
            self._attempts.refused(
                idempotency_key,
                code="UNEXPECTED",
                message=f"{type(unexpected).__name__}: {unexpected}",
            )
            raise
        else:
            self._attempts.succeeded(idempotency_key, result)
            return result

    def _record_failure(
        self,
        claimed: AttemptRecord,
        idempotency_key: str,
        plan_id: str,
        refusal: ToolLayerError,
    ) -> None:
        if refusal.transient:
            self._attempts.failed_transiently(
                idempotency_key, code=refusal.code, message=str(refusal)
            )
        else:
            self._attempts.refused(idempotency_key, code=refusal.code, message=str(refusal))
        self._publish_failure(claimed, plan_id, refusal)

    def _settled_outcome(self, idempotency_key: str) -> ExecutionResult:
        """The outcome recorded for a key somebody else claimed.

        Waits a little for an attempt that is still running, because a customer
        double-tapping Confirm should see the fix, not a race.
        """
        deadline = monotonic() + self._duplicate_wait_seconds
        while True:
            record = self._attempts.get(idempotency_key)
            if record is not None and record.is_settled:
                return self._replay_of(record, idempotency_key)
            if monotonic() >= deadline:
                raise ExecutionInProgress(
                    f"an identical request for {idempotency_key} is still running; "
                    "retry with the same idempotency key"
                )
            sleep(0.001)

    def _replay_of(self, record: AttemptRecord, idempotency_key: str) -> ExecutionResult:
        """Exactly what the original attempt returned, or the refusal it raised."""
        if record.state is AttemptState.SUCCEEDED and record.result is not None:
            return replace(record.result, replayed=True)
        raise _REFUSALS.get(record.error_code or "", ExecutionFailed)(
            record.error_message or f"{idempotency_key} failed: {record.error_code}"
        )

    def _execute_claimed(
        self,
        plan_id: str,
        *,
        confirmation: str | ConfirmationToken | None,
        idempotency_key: str,
        now: datetime | None,
    ) -> ExecutionResult:
        """Run a plan once. Only ever called by the owner of the key."""
        record = self._pending(plan_id)

        if confirmation is None:
            raise ConfirmationRequired(
                "this action needs a confirmation token minted by the customer or staff"
            )
        value = confirmation.value if isinstance(confirmation, ConfirmationToken) else confirmation

        # Budget before the token. A confirmation is single use, so consuming it
        # and then refusing for an unrelated reason burns the customer's
        # authority: the retry that M-ACT makes possible would then always fail
        # with CONFIRMATION_INVALID instead of executing. Reserving the budget
        # applies nothing outside the budget and is released if anything after
        # it refuses.
        reservation = self._reserve(record)
        try:
            token = self._confirmations.redeem(value, plan_id=plan_id, now=now)
        except BaseException:
            if reservation is not None:
                self._budget.release(reservation)
            raise

        span_scope = span(
            "actions.execute",
            plan_id=plan_id,
            case_id=record.plan.case_id,
            amount_lkr=str(record.plan.total_amount_lkr),
            idempotency_key=idempotency_key,
        )
        with span_scope:
            return self._execute_steps(record, plan_id, token, idempotency_key, reservation)

    def _execute_steps(
        self,
        record: PlanRecord,
        plan_id: str,
        token: ConfirmationToken,
        idempotency_key: str,
        reservation: Reservation | None,
    ) -> ExecutionResult:
        record.reservation = reservation
        record.idempotency_key = idempotency_key
        self._save(record)

        actions, failure = self._run_steps(record, idempotency_key)

        if failure is None:
            if reservation is not None:
                self._budget.commit(reservation)
            record.plan = record.plan.model_copy(update={"status": PlanStatus.COMPLETED})
            result = ExecutionResult(
                plan_id=plan_id,
                actions=actions,
                status=PlanStatus.COMPLETED,
                confirmed_by=token.confirmed_by,
                approver_roles=tuple(approval.role for approval in record.approvals),
            )
            record.result = result
            self._complete(record, result)
            return result

        self._compensate(record, actions, idempotency_key)
        if reservation is not None:
            self._budget.release(reservation)
        record.plan = record.plan.model_copy(update={"status": PlanStatus.COMPENSATED})
        record.result = ExecutionResult(
            plan_id=plan_id,
            actions=actions,
            status=PlanStatus.COMPENSATED,
            confirmed_by=token.confirmed_by,
        )
        self._save(record)
        raise ExecutionFailed(
            f"step {failure} could not be applied; applied steps were reversed "
            "and the case needs a person"
        )

    # -- execution internals ------------------------------------------- #

    def _reserve(self, record: PlanRecord) -> Reservation | None:
        amount = record.plan.total_amount_lkr
        if amount <= Decimal("0.00"):
            return None
        try:
            return self._budget.reserve(amount, rule_id=record.rule_id)
        except ValueError as error:
            raise BudgetExhausted(str(error)) from error

    def _run_steps(
        self, record: PlanRecord, idempotency_key: str
    ) -> tuple[list[Action], str | None]:
        actions: list[Action] = []
        for index, step in enumerate(record.plan.steps):
            key = f"{idempotency_key}:{index}:{step.action_type.value}"
            command = Command(
                action_type=step.action_type,
                subscriber_ref=str(step.params.get("subscriber_ref", "")),
                idempotency_key=key,
                amount_lkr=step.amount_lkr,
                params=step.params,
            )
            try:
                outcome = self._commands.execute(command)
            except AdapterError as error:
                actions.append(self._failed_action(record, step, key, error.code))
                return actions, step.action_type.value

            if not outcome.accepted:
                actions.append(
                    self._failed_action(record, step, key, outcome.error_code or "ADAPTER_REFUSED")
                )
                return actions, step.action_type.value

            actions.append(self._completed_action(record, step, key, outcome))
        return actions, None

    def _compensate(self, record: PlanRecord, actions: list[Action], idempotency_key: str) -> None:
        """Undo what was applied, newest first.

        A refund is never "un-refunded": taking money back from a customer
        because our own later step failed would be a second wrong. It is
        marked for the human who picks the case up.
        """
        for position, action in reversed(list(enumerate(actions))):
            if action.status is not ActionStatus.COMPLETED:
                continue
            compensation = _COMPENSATIONS.get(action.type, action.type)
            if compensation is None or action.type is ActionType.REFUND:
                continue
            reverse = Command(
                action_type=compensation,
                subscriber_ref=str(record.plan.steps[position].params.get("subscriber_ref", "")),
                idempotency_key=f"{idempotency_key}:compensate:{position}",
                params=dict(record.plan.steps[position].params) | {"reverse": True},
            )
            # Compensation is best-effort: if the reversal itself fails there
            # is nothing further to try automatically. The step is still marked
            # COMPENSATED so the human picking up the case sees what was
            # attempted, and the plan ends in a state that demands review.
            with suppress(AdapterError):
                self._commands.execute(reverse)
            actions[position] = action.model_copy(update={"status": ActionStatus.COMPENSATED})

    def _completed_action(
        self, record: PlanRecord, step: PlanStep, key: str, outcome: CommandResult
    ) -> Action:
        return Action(
            action_id=new_id("ACT"),
            decision_id=record.plan.decision_id,
            case_id=record.plan.case_id,
            type=step.action_type,
            safety_level=step.safety_level,
            amount_lkr=step.amount_lkr,
            before_state=outcome.before_state,
            after_state=outcome.after_state,
            idempotency_key=key,
            status=ActionStatus.COMPLETED,
            adapter_ref=outcome.adapter_ref,
            executed_at=utc_now(),
        )

    @staticmethod
    def _failed_action(record: PlanRecord, step: PlanStep, key: str, error_code: str) -> Action:
        return Action(
            action_id=new_id("ACT"),
            decision_id=record.plan.decision_id,
            case_id=record.plan.case_id,
            type=step.action_type,
            safety_level=step.safety_level,
            amount_lkr=step.amount_lkr,
            idempotency_key=key,
            status=ActionStatus.FAILED,
            error_code=error_code,
            executed_at=utc_now(),
        )

    # -- lookups -------------------------------------------------------- #

    def _record(self, plan_id: str) -> PlanRecord:
        record = self._plans.get(plan_id)
        if record is None:
            raise PlanNotFound(f"no such plan: {plan_id}")
        return record

    def _save(self, record: PlanRecord) -> None:
        """Write a record back after mutating it, so a storing driver sees it."""
        self._plans.save(record)

    def _publish_failure(
        self, claimed: AttemptRecord, plan_id: str, refusal: ToolLayerError
    ) -> None:
        """Say that a plan did not execute, and whether it can be tried again.

        A consumer needs the difference: a retryable failure is something to
        wait out, a final one is a case that needs a person (M-ACT).
        """
        record = self._plans.get(plan_id)
        if record is None:  # pragma: no cover - the plan was found to refuse it
            return
        # A plan is built with at least one step, so there is always one to name.
        failed_step = record.plan.steps[0].action_type
        self._publish(
            record,
            ActionFailedV1(
                case_id=record.plan.case_id,
                plan_id=plan_id,
                failed_step=failed_step,
                error_code=refusal.code,
                # Compensated means steps were applied and reversed. A refusal
                # that stopped before any step applied compensated nothing.
                compensated=record.plan.status is PlanStatus.COMPENSATED,
                retryable=refusal.transient,
                attempt=claimed.attempt,
            ),
        )

    def _publish_approval_requested(self, record: PlanRecord) -> None:
        """Ask for an approval through the bus, so a notification can follow it."""
        self._publish(
            record,
            ApprovalRequestedV1(
                case_id=record.plan.case_id,
                plan_id=record.plan.plan_id,
                decision_id=record.decision.decision_id,
                total_amount_lkr=record.plan.total_amount_lkr,
                approvals_needed=self._approvals_needed(record),
                approvals_held=len(record.approvals),
                four_eyes_threshold_lkr=record.four_eyes_threshold_lkr,
                requested_by=record.plan.created_by,
            ),
        )

    def _publish(self, record: PlanRecord, payload: EventPayload) -> None:
        """Append one event in its own unit of work.

        Separate from the plan write, unlike ``action.completed``: these events
        report that nothing changed, so there is no state change to be atomic
        with, and a failure to publish must not undo a refusal.
        """
        with self._open_unit() as unit:
            outbox_in(unit).append(Event.of(payload, subject=self._subscriber_of(record)))
            unit.commit()

    def _complete(self, record: PlanRecord, result: ExecutionResult) -> None:
        """Store the completed plan and its ``action.completed`` event atomically.

        One transaction, so there is no interleaving in which the money moved
        and no event was ever written. The relay publishes it afterwards (B04).
        """
        with self._open_unit() as unit:
            StoredPlanRepository(unit.repository(PLANS)).save(record)
            outbox_in(unit).append(
                Event.of(
                    self._completed_payload(record, result),
                    subject=self._subscriber_of(record),
                )
            )
            unit.commit()

    @staticmethod
    def _completed_payload(record: PlanRecord, result: ExecutionResult) -> ActionCompletedV1:
        return ActionCompletedV1(
            case_id=record.plan.case_id,
            plan_id=record.plan.plan_id,
            decision_id=record.decision.decision_id,
            steps=[
                ActionStepV1(
                    action_id=action.action_id,
                    action_type=action.type,
                    amount_lkr=action.amount_lkr,
                    status=action.status.value,
                    idempotency_key=action.idempotency_key,
                    adapter_ref=action.adapter_ref,
                )
                for action in result.actions
            ],
            confirmed_by=result.confirmed_by.value,
            approver_roles=list(result.approver_roles),
            total_amount_lkr=record.plan.total_amount_lkr,
            config_snapshot_hash=record.decision.input_hash,
        )

    @staticmethod
    def _subscriber_of(record: PlanRecord) -> str:
        """The partition key: everything about one customer stays in order.

        Every step carries the subscriber_ref, put there by the case module from
        evidence rather than by a caller.
        """
        for step in record.plan.steps:
            found = step.params.get("subscriber_ref")
            if isinstance(found, str) and found:
                return found
        # A plan with no subscriber would be unroutable, and the case module
        # always sets it, so this is a bug rather than a condition to handle.
        raise ExecutionFailed(f"plan {record.plan.plan_id} carries no subscriber_ref")

    def _pending(self, plan_id: str) -> PlanRecord:
        record = self._record(plan_id)
        if record.plan.status is not PlanStatus.PENDING_CONFIRMATION:
            raise PlanNotPending(
                f"plan {plan_id} is {record.plan.status.value}, so it cannot be acted on again"
            )
        return record


__all__ = [
    "FOUR_EYES_THRESHOLD_LKR",
    "ActionSafetyLevel",
    "ExecutionResult",
    "ToolLayer",
]
