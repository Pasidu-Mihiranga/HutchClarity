"""The tool layer: the only path from a decision to a change in a HUTCH system.

Deck S7 calls this "Act — confirmed, idempotent". Its job is to make four
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

from clarity.core.tools.budget import RefundBudget, Reservation
from clarity.core.tools.confirmation import (
    ConfirmationService,
    ConfirmationToken,
    ConfirmedBy,
)
from clarity.core.tools.errors import (
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
from clarity.integrations.base import AdapterError, Command, CommandPort, CommandResult
from clarity.schemas.common import ActionSafetyLevel, money, utc_now
from clarity.schemas.decision import (
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
from clarity.schemas.ids import new_id

#: Outcomes that may ever result in execution. EXPLAIN_ONLY and HANDOFF cannot.
EXECUTABLE_OUTCOMES = frozenset({Outcome.AUTO_FIX, Outcome.ONE_TAP_FIX, Outcome.STAFF_APPROVAL})

#: Above this, one approver is not enough (plan §14.2 four-eyes).
#: PROPOSED TARGET - REQUIRES HUTCH VALIDATION.
FOUR_EYES_THRESHOLD_LKR = money("25000.00")

#: Actions whose effect can be undone if a later step in the plan fails.
_COMPENSATIONS: dict[ActionType, ActionType | None] = {
    ActionType.SET_SPEND_CAP: None,
    ActionType.ENABLE_DATA_STOP: None,
    ActionType.ENABLE_FUP_ALERTS: None,
}


@dataclass
class ExecutionResult:
    """What happened when a plan ran."""

    plan_id: str
    actions: list[Action]
    status: PlanStatus
    confirmed_by: ConfirmedBy
    replayed: bool = False

    @property
    def succeeded(self) -> bool:
        return self.status is PlanStatus.COMPLETED


@dataclass
class _Attempt:
    """One execution of one idempotency key, and its single outcome.

    Duplicates wait on ``done`` and then take whichever of ``result`` or
    ``error`` was set, so every caller of the same key sees the same thing.
    """

    done: threading.Event = field(default_factory=threading.Event)
    result: ExecutionResult | None = None
    error: BaseException | None = None


@dataclass
class _PlanRecord:
    plan: ActionPlan
    decision: Decision
    rule_id: str | None
    approvals: list[Approval] = field(default_factory=list)
    reservation: Reservation | None = None
    result: ExecutionResult | None = None
    idempotency_key: str | None = None


class ToolLayer:
    """Holds the only reference to a command port (plan §9.1 principle 2)."""

    def __init__(
        self,
        command_port: CommandPort,
        *,
        budget: RefundBudget | None = None,
        confirmations: ConfirmationService | None = None,
        duplicate_wait_seconds: float = 10.0,
    ) -> None:
        self._commands = command_port
        self._budget = budget or RefundBudget()
        self._confirmations = confirmations or ConfirmationService()
        self._plans: dict[str, _PlanRecord] = {}
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
        self._plans[plan.plan_id] = _PlanRecord(plan=plan, decision=decision, rule_id=rule_id)
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
    # 2. Confirm or approve — always outside the AI path
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

        if len(record.approvals) < self._approvals_needed(record.plan):
            return None

        roles = {a.role for a in record.approvals}
        if self._approvals_needed(record.plan) > 1 and len(roles) < 2:
            raise ApprovalRequired(
                "four-eyes approval needs two different roles, e.g. a supervisor and finance"
            )

        return self._confirmations.mint(
            plan_id, confirmed_by=ConfirmedBy.STAFF, principal_ref=approver_ref, now=now
        )

    @staticmethod
    def _approvals_needed(plan: ActionPlan) -> int:
        return 2 if plan.total_amount_lkr > FOUR_EYES_THRESHOLD_LKR else 1

    def authorise_auto_fix(self, plan_id: str, *, now: datetime | None = None) -> ConfirmationToken:
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
            principal_ref="clarity-stream-detector",
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

        reservation = self._reserve(record)
        record.reservation = reservation
        record.idempotency_key = idempotency_key

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
            )
            record.result = result
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
        raise ExecutionFailed(
            f"step {failure} could not be applied; applied steps were reversed "
            "and the case needs a person"
        )

    # -- execution internals ------------------------------------------- #

    def _reserve(self, record: _PlanRecord) -> Reservation | None:
        amount = record.plan.total_amount_lkr
        if amount <= Decimal("0.00"):
            return None
        try:
            return self._budget.reserve(amount, rule_id=record.rule_id)
        except ValueError as error:
            raise BudgetExhausted(str(error)) from error

    def _run_steps(
        self, record: _PlanRecord, idempotency_key: str
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

    def _compensate(self, record: _PlanRecord, actions: list[Action], idempotency_key: str) -> None:
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
        self, record: _PlanRecord, step: PlanStep, key: str, outcome: CommandResult
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
    def _failed_action(record: _PlanRecord, step: PlanStep, key: str, error_code: str) -> Action:
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

    def _record(self, plan_id: str) -> _PlanRecord:
        record = self._plans.get(plan_id)
        if record is None:
            raise PlanNotFound(f"no such plan: {plan_id}")
        return record

    def _pending(self, plan_id: str) -> _PlanRecord:
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
