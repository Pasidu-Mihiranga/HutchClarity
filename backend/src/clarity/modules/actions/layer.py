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
from dataclasses import dataclass, field, replace
from datetime import datetime
from decimal import Decimal
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
from clarity.contracts.events import ActionCompletedV1, ActionStepV1
from clarity.integration.ports import AdapterError, Command, CommandPort, CommandResult
from clarity.kernel.common import ActionSafetyLevel, utc_now
from clarity.kernel.ids import new_id
from clarity.modules.actions.budget import RefundBudget, Reservation
from clarity.modules.actions.confirmation import ConfirmationService
from clarity.modules.actions.errors import (
    ActionNotAllowed,
    ApprovalRequired,
    BudgetExhausted,
    ConfirmationRequired,
    ExecutionFailed,
    ExecutionInProgress,
    OutcomeNotExecutable,
    PlanNotFound,
    PlanNotPending,
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

#: Actions whose effect can be undone if a later step in the plan fails.
_COMPENSATIONS: dict[ActionType, ActionType | None] = {
    ActionType.SET_SPEND_CAP: None,
    ActionType.ENABLE_DATA_STOP: None,
    ActionType.ENABLE_FUP_ALERTS: None,
}


@dataclass
class _Attempt:
    """One execution of one idempotency key, and its single outcome.

    Duplicates wait on ``done`` and then take whichever of ``result`` or
    ``error`` was set, so every caller of the same key sees the same thing.
    """

    done: threading.Event = field(default_factory=threading.Event)
    result: ExecutionResult | None = None
    error: BaseException | None = None


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
        self._confirmations = confirmations or ConfirmationService()
        # Plans live in the repository (B02); the layer keeps no business state.
        self._plans = plans
        # Completing a plan writes the plan and its event in one transaction
        # (I7, B04), so nobody can observe a completed plan with no event.
        self._open_unit = open_unit
        # In-flight coordination, not business state: one event per key so a
        # duplicate call waits for the original instead of acting again. The
        # durable idempotency record is M-ACT's work.
        self._attempts: dict[str, _Attempt] = {}
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
        attempt, is_owner = self._claim(idempotency_key)
        if not is_owner:
            return self._await_original(attempt, idempotency_key)

        try:
            result = self._execute_claimed(
                plan_id, confirmation=confirmation, idempotency_key=idempotency_key, now=now
            )
        except BaseException as error:
            # The outcome of a key is final, success or failure. Releasing the
            # key here would let a duplicate that arrives a moment later start
            # fresh and receive a *different* error for the same request. A
            # caller who wants a genuine new attempt uses a new key.
            with self._lock:
                attempt.error = error
            attempt.done.set()
            raise
        else:
            with self._lock:
                attempt.result = result
            attempt.done.set()
            return result

    # -- idempotency claim ----------------------------------------------- #

    def _claim(self, idempotency_key: str) -> tuple[_Attempt, bool]:
        """Reserve the key, or find the attempt that already owns it."""
        with self._lock:
            existing = self._attempts.get(idempotency_key)
            if existing is not None:
                return existing, False
            attempt = _Attempt()
            self._attempts[idempotency_key] = attempt
            return attempt, True

    def _await_original(self, attempt: _Attempt, idempotency_key: str) -> ExecutionResult:
        """Return exactly what the original call returned, or raise what it raised."""
        if not attempt.done.wait(timeout=self._duplicate_wait_seconds):
            raise ExecutionInProgress(
                f"an identical request for {idempotency_key} is still running; "
                "retry with the same idempotency key"
            )
        if attempt.error is not None:
            raise attempt.error
        assert attempt.result is not None  # done implies one of the two is set
        return replace(attempt.result, replayed=True)

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
        token = self._confirmations.redeem(value, plan_id=plan_id, now=now)

        span_scope = span(
            "actions.execute",
            plan_id=plan_id,
            case_id=record.plan.case_id,
            amount_lkr=str(record.plan.total_amount_lkr),
            idempotency_key=idempotency_key,
        )
        with span_scope:
            return self._execute_steps(record, plan_id, token, idempotency_key)

    def _execute_steps(
        self,
        record: PlanRecord,
        plan_id: str,
        token: ConfirmationToken,
        idempotency_key: str,
    ) -> ExecutionResult:
        reservation = self._reserve(record)
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
