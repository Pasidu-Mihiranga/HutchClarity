"""Tool layer tests (plan §10.5, §14.4).

This is the component that makes "rules decide, the LLM explains" structural
rather than aspirational, so the adversarial cases matter most: a caller that
asks for an action nobody authorised, an amount nobody calculated, or
execution without anyone confirming.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest

from clarity.contracts.decision import (
    ActionStatus,
    ActionType,
    Decision,
    Outcome,
    PlanStatus,
)
from clarity.integration.drivers.mock.world import build_demo_world, ref_for
from clarity.integration.ports import AdapterUnavailable, Command, CommandPort, CommandResult
from clarity.integration.registry import AdapterRegistry
from clarity.kernel.common import EventSource, utc_now
from clarity.kernel.ids import new_id
from clarity.modules.actions.budget import RefundBudget
from clarity.modules.actions.confirmation import ConfirmedBy
from clarity.modules.actions.errors import (
    ActionNotAllowed,
    ApprovalRequired,
    BudgetExhausted,
    ConfirmationInvalid,
    ConfirmationRequired,
    ExecutionFailed,
    OutcomeNotExecutable,
    PlanNotPending,
)
from clarity.modules.actions.layer import ToolLayer

from ..support.repositories import confirmations, tool_layer

DILANI = "+94771234567"
SUBSCRIBER = ref_for(DILANI)


def a_decision(
    *,
    outcome: Outcome = Outcome.ONE_TAP_FIX,
    actions: list[ActionType] | None = None,
    amount: str | None = "49.00",
) -> Decision:
    return Decision(
        decision_id=new_id("DEC"),
        case_id="CASE-T",
        outcome=outcome,
        policy_version="test.1",
        input_hash="sha256:test",
        allowed_actions=actions
        if actions is not None
        else [
            ActionType.REFUND,
            ActionType.DEACTIVATE_VAS,
            ActionType.BLOCK_MERCHANT_UNTIL_OPTIN,
        ],
        amount_lkr=amount,
        top_cause_ref="VAS_NO_CONSENT@4",
        handoff_reason=None,
    )


@pytest.fixture
def tools(registry) -> ToolLayer:
    return tool_layer(
        registry.command_port,
        budget=RefundBudget(daily_limit_lkr="100000"),
    )


def vas_params() -> dict[ActionType, dict]:
    return {
        ActionType.DEACTIVATE_VAS: {"subscription_id": "SUB-GAME-1"},
        ActionType.BLOCK_MERCHANT_UNTIL_OPTIN: {"merchant_id": "MER-GAMEHUB"},
    }


def propose(tools: ToolLayer, decision: Decision, **kwargs):
    return tools.propose(
        decision,
        subscriber_ref=SUBSCRIBER,
        created_by=kwargs.pop("created_by", "mcp:customer-assist"),
        params=vas_params(),
        **kwargs,
    )


# --------------------------------------------------------------------------- #
# Proposing cannot widen what was decided
# --------------------------------------------------------------------------- #


def test_proposing_an_unauthorised_action_is_refused(tools: ToolLayer):
    """The main guard against a model inventing a remedy."""
    decision = a_decision(actions=[ActionType.REFUND])

    with pytest.raises(ActionNotAllowed, match="not permitted"):
        propose(tools, decision, action_types=[ActionType.DEACTIVATE_VAS])


def test_a_caller_may_narrow_the_remedy_but_not_widen_it(tools: ToolLayer):
    plan = propose(tools, a_decision(), action_types=[ActionType.REFUND])

    assert plan.action_types == [ActionType.REFUND]


def test_amount_comes_from_the_decision_not_the_caller(tools: ToolLayer):
    """A caller has no field through which to influence how much money moves."""
    plan = propose(tools, a_decision(amount="49.00"))

    refund = next(s for s in plan.steps if s.action_type is ActionType.REFUND)
    assert refund.amount_lkr == Decimal("49.00")
    assert plan.total_amount_lkr == Decimal("49.00")


def test_explain_only_decisions_authorise_nothing(tools: ToolLayer):
    with pytest.raises(OutcomeNotExecutable):
        propose(tools, a_decision(outcome=Outcome.EXPLAIN_ONLY, actions=[ActionType.REFUND]))


def test_handoff_decisions_authorise_nothing(tools: ToolLayer):
    decision = Decision(
        decision_id=new_id("DEC"),
        case_id="CASE-T",
        outcome=Outcome.HANDOFF,
        policy_version="test.1",
        input_hash="sha256:test",
        handoff_reason="low_confidence",
    )

    with pytest.raises(OutcomeNotExecutable):
        propose(tools, decision)


def test_proposing_changes_nothing_on_its_own(tools: ToolLayer, world):
    opening = world.account(SUBSCRIBER).balance_lkr

    propose(tools, a_decision())

    assert world.account(SUBSCRIBER).balance_lkr == opening
    assert world.account(SUBSCRIBER).subscriptions[0].active


# --------------------------------------------------------------------------- #
# Execution requires confirmation the model cannot mint
# --------------------------------------------------------------------------- #


def test_execution_without_confirmation_is_refused(tools: ToolLayer, world):
    plan = propose(tools, a_decision())
    opening = world.account(SUBSCRIBER).balance_lkr

    with pytest.raises(ConfirmationRequired):
        tools.execute(plan.plan_id, confirmation=None, idempotency_key="k1")

    assert world.account(SUBSCRIBER).balance_lkr == opening, "nothing moved"


def test_a_guessed_token_is_refused(tools: ToolLayer):
    plan = propose(tools, a_decision())

    with pytest.raises(ConfirmationInvalid):
        tools.execute(plan.plan_id, confirmation="not-a-real-token", idempotency_key="k2")


def test_a_token_for_another_plan_is_refused(tools: ToolLayer):
    first = propose(tools, a_decision())
    second = propose(tools, a_decision())
    token = tools.confirm_by_customer(first.plan_id, subscriber_ref=SUBSCRIBER)

    with pytest.raises(ConfirmationInvalid):
        tools.execute(second.plan_id, confirmation=token.value, idempotency_key="k3")


def test_a_token_is_single_use(tools: ToolLayer):
    plan = propose(tools, a_decision())
    token = tools.confirm_by_customer(plan.plan_id, subscriber_ref=SUBSCRIBER)
    tools.execute(plan.plan_id, confirmation=token, idempotency_key="k4")

    second_plan = propose(tools, a_decision())
    with pytest.raises(ConfirmationInvalid):
        tools.execute(second_plan.plan_id, confirmation=token, idempotency_key="k5")


def test_an_expired_token_is_refused(registry):
    tools = tool_layer(
        registry.command_port,
        confirmations=confirmations(ttl=timedelta(minutes=15)),
    )
    plan = propose(tools, a_decision())
    token = tools.confirm_by_customer(plan.plan_id, subscriber_ref=SUBSCRIBER)

    with pytest.raises(ConfirmationInvalid):
        tools.execute(
            plan.plan_id,
            confirmation=token,
            idempotency_key="k6",
            now=utc_now() + timedelta(minutes=16),
        )


def test_customer_cannot_confirm_a_staff_decision(tools: ToolLayer):
    plan = propose(tools, a_decision(outcome=Outcome.STAFF_APPROVAL))

    with pytest.raises(ConfirmationRequired, match="not the customer's"):
        tools.confirm_by_customer(plan.plan_id, subscriber_ref=SUBSCRIBER)


def test_only_auto_fix_may_self_authorise(tools: ToolLayer):
    plan = propose(tools, a_decision(outcome=Outcome.ONE_TAP_FIX))

    with pytest.raises(ConfirmationRequired, match="only an AUTO_FIX"):
        tools.authorise_auto_fix(plan.plan_id)


# --------------------------------------------------------------------------- #
# The happy paths
# --------------------------------------------------------------------------- #


def test_one_tap_fix_applies_the_whole_remedy(tools: ToolLayer, world):
    """Deck S6: refund, switch off, and block the merchant - in one tap."""
    plan = propose(tools, a_decision())
    token = tools.confirm_by_customer(plan.plan_id, subscriber_ref=SUBSCRIBER)

    result = tools.execute(plan.plan_id, confirmation=token, idempotency_key="k7")

    account = world.account(SUBSCRIBER)
    assert result.succeeded
    assert result.confirmed_by is ConfirmedBy.CUSTOMER
    assert account.balance_lkr == Decimal("500.00"), "451.00 + 49.00"
    assert not account.subscriptions[0].active
    assert world.is_merchant_blocked(SUBSCRIBER, "MER-GAMEHUB")


def test_executed_actions_record_before_and_after_for_the_receipt(tools: ToolLayer):
    plan = propose(tools, a_decision())
    token = tools.confirm_by_customer(plan.plan_id, subscriber_ref=SUBSCRIBER)

    result = tools.execute(plan.plan_id, confirmation=token, idempotency_key="k8")

    refund = next(a for a in result.actions if a.type is ActionType.REFUND)
    assert refund.before_state == {"balance_lkr": "451.00"}
    assert refund.after_state == {"balance_lkr": "500.00"}
    assert refund.adapter_ref, "an action must cite the upstream reference"


def test_auto_fix_runs_with_no_human_in_the_loop(registry, world):
    """Deck S5: refunded before the customer even notices."""
    tools = tool_layer(registry.command_port)
    plan = tools.propose(
        a_decision(outcome=Outcome.AUTO_FIX, actions=[ActionType.REFUND], amount="3500.00"),
        subscriber_ref=SUBSCRIBER,
        created_by="clarity-stream-detector",
    )
    token = tools.authorise_auto_fix(plan.plan_id)

    result = tools.execute(plan.plan_id, confirmation=token, idempotency_key="k9")

    assert result.succeeded
    assert result.confirmed_by is ConfirmedBy.SYSTEM
    assert world.account(SUBSCRIBER).balance_lkr == Decimal("3951.00")


# --------------------------------------------------------------------------- #
# Staff approval and four eyes
# --------------------------------------------------------------------------- #


def test_staff_approval_requires_mfa_step_up(tools: ToolLayer):
    plan = propose(tools, a_decision(outcome=Outcome.STAFF_APPROVAL))

    with pytest.raises(ApprovalRequired, match="MFA"):
        tools.approve_by_staff(
            plan.plan_id, approver_ref="agent-1", role="supervisor", mfa_step_up=False
        )


def test_the_maker_cannot_approve_their_own_plan(tools: ToolLayer):
    """Separation of duties (plan §14.4)."""
    plan = propose(tools, a_decision(outcome=Outcome.STAFF_APPROVAL), created_by="agent-1")

    with pytest.raises(ApprovalRequired, match="maker"):
        tools.approve_by_staff(
            plan.plan_id, approver_ref="agent-1", role="supervisor", mfa_step_up=True
        )


def test_one_approval_is_enough_below_the_four_eyes_threshold(tools: ToolLayer):
    plan = propose(tools, a_decision(outcome=Outcome.STAFF_APPROVAL, amount="5000.00"))

    token = tools.approve_by_staff(
        plan.plan_id, approver_ref="sup-1", role="supervisor", mfa_step_up=True
    )

    assert token is not None
    assert tools.execute(plan.plan_id, confirmation=token, idempotency_key="k10").succeeded


def test_large_amounts_need_two_approvers(tools: ToolLayer):
    plan = propose(
        tools,
        a_decision(outcome=Outcome.STAFF_APPROVAL, actions=[ActionType.REFUND], amount="30000.00"),
    )

    first = tools.approve_by_staff(
        plan.plan_id, approver_ref="sup-1", role="supervisor", mfa_step_up=True
    )
    assert first is None, "one approval must not yet authorise execution"

    with pytest.raises(ConfirmationRequired):
        tools.execute(plan.plan_id, confirmation=None, idempotency_key="k11")

    second = tools.approve_by_staff(
        plan.plan_id, approver_ref="fin-1", role="finance", mfa_step_up=True
    )
    assert second is not None


def test_the_same_approver_cannot_sign_twice_to_make_four_eyes(tools: ToolLayer):
    plan = propose(
        tools,
        a_decision(outcome=Outcome.STAFF_APPROVAL, actions=[ActionType.REFUND], amount="30000.00"),
    )
    tools.approve_by_staff(plan.plan_id, approver_ref="sup-1", role="supervisor", mfa_step_up=True)

    with pytest.raises(ApprovalRequired, match="already signed"):
        tools.approve_by_staff(
            plan.plan_id, approver_ref="sup-1", role="supervisor", mfa_step_up=True
        )


def test_four_eyes_needs_two_different_roles(tools: ToolLayer):
    plan = propose(
        tools,
        a_decision(outcome=Outcome.STAFF_APPROVAL, actions=[ActionType.REFUND], amount="30000.00"),
    )
    tools.approve_by_staff(plan.plan_id, approver_ref="sup-1", role="supervisor", mfa_step_up=True)

    with pytest.raises(ApprovalRequired, match="two different roles"):
        tools.approve_by_staff(
            plan.plan_id, approver_ref="sup-2", role="supervisor", mfa_step_up=True
        )


# --------------------------------------------------------------------------- #
# Idempotency, budget and replay
# --------------------------------------------------------------------------- #


def test_replaying_an_idempotency_key_does_not_move_money_twice(tools: ToolLayer, world):
    plan = propose(tools, a_decision())
    token = tools.confirm_by_customer(plan.plan_id, subscriber_ref=SUBSCRIBER)
    first = tools.execute(plan.plan_id, confirmation=token, idempotency_key="same-key")

    second = tools.execute(plan.plan_id, confirmation=token, idempotency_key="same-key")

    assert second.replayed and not first.replayed
    assert world.account(SUBSCRIBER).balance_lkr == Decimal("500.00"), "credited once"


def test_a_completed_plan_cannot_be_run_again(tools: ToolLayer):
    plan = propose(tools, a_decision())
    token = tools.confirm_by_customer(plan.plan_id, subscriber_ref=SUBSCRIBER)
    tools.execute(plan.plan_id, confirmation=token, idempotency_key="k12")

    with pytest.raises(PlanNotPending):
        tools.confirm_by_customer(plan.plan_id, subscriber_ref=SUBSCRIBER)


def test_budget_blocks_execution_it_cannot_cover(registry, world):
    tools = tool_layer(registry.command_port, budget=RefundBudget(daily_limit_lkr="10.00"))
    plan = propose(tools, a_decision())
    token = tools.confirm_by_customer(plan.plan_id, subscriber_ref=SUBSCRIBER)
    opening = world.account(SUBSCRIBER).balance_lkr

    with pytest.raises(BudgetExhausted):
        tools.execute(plan.plan_id, confirmation=token, idempotency_key="k13")

    assert world.account(SUBSCRIBER).balance_lkr == opening


def test_budget_is_consumed_only_by_successful_execution(tools: ToolLayer):
    plan = propose(tools, a_decision())
    token = tools.confirm_by_customer(plan.plan_id, subscriber_ref=SUBSCRIBER)

    tools.execute(plan.plan_id, confirmation=token, idempotency_key="k14")

    assert tools.budget.spent_lkr == Decimal("49.00")


def test_budget_state_feeds_the_decision_policy():
    budget = RefundBudget(daily_limit_lkr="1000.00", per_rule_limit_lkr={"VAS_NO_CONSENT": "100"})

    state = budget.state_for("VAS_NO_CONSENT")

    assert state.global_remaining_lkr == Decimal("1000.00")
    assert state.rule_remaining_lkr == Decimal("100.00")
    assert state.allows(Decimal("50.00"))
    assert not state.allows(Decimal("500.00")), "the per-rule ceiling binds"


# --------------------------------------------------------------------------- #
# Failure and compensation
# --------------------------------------------------------------------------- #


class _FailingPort(CommandPort):
    """Applies the first step, then fails - the partial-failure case."""

    source = EventSource.CHARGING

    def __init__(self, inner: CommandPort, fail_on: ActionType) -> None:
        self._inner = inner
        self._fail_on = fail_on

    def supports(self, action_type: ActionType) -> bool:
        return self._inner.supports(action_type)

    def status_of(self, idempotency_key: str) -> CommandResult | None:
        return self._inner.status_of(idempotency_key)

    def execute(self, command: Command) -> CommandResult:
        if command.action_type is self._fail_on:
            raise AdapterUnavailable(self.source, "UPSTREAM_TIMEOUT", "simulated outage")
        return self._inner.execute(command)


def test_a_failed_step_compensates_and_escalates(registry, world):
    tools = tool_layer(
        _FailingPort(registry.command_port, ActionType.BLOCK_MERCHANT_UNTIL_OPTIN),
    )
    plan = propose(tools, a_decision())
    token = tools.confirm_by_customer(plan.plan_id, subscriber_ref=SUBSCRIBER)

    with pytest.raises(ExecutionFailed, match="needs a person"):
        tools.execute(plan.plan_id, confirmation=token, idempotency_key="k15")

    assert tools.plan(plan.plan_id).status is PlanStatus.COMPENSATED


def test_a_refund_is_never_clawed_back_to_tidy_up(registry, world):
    """Reversing our own refund would be a second wrong against the customer."""
    tools = tool_layer(
        _FailingPort(registry.command_port, ActionType.BLOCK_MERCHANT_UNTIL_OPTIN),
    )
    plan = propose(tools, a_decision())
    token = tools.confirm_by_customer(plan.plan_id, subscriber_ref=SUBSCRIBER)

    with pytest.raises(ExecutionFailed):
        tools.execute(plan.plan_id, confirmation=token, idempotency_key="k16")

    assert world.account(SUBSCRIBER).balance_lkr == Decimal("500.00"), "the refund stands"


def test_a_failed_execution_releases_the_budget_it_reserved(registry):
    tools = tool_layer(
        _FailingPort(registry.command_port, ActionType.BLOCK_MERCHANT_UNTIL_OPTIN),
        budget=RefundBudget(daily_limit_lkr="1000.00"),
    )
    plan = propose(tools, a_decision())
    token = tools.confirm_by_customer(plan.plan_id, subscriber_ref=SUBSCRIBER)

    with pytest.raises(ExecutionFailed):
        tools.execute(plan.plan_id, confirmation=token, idempotency_key="k17")

    assert tools.budget.state_for().global_remaining_lkr == Decimal("1000.00")


def test_failed_steps_are_recorded_with_their_error_code(registry):
    tools = tool_layer(_FailingPort(registry.command_port, ActionType.DEACTIVATE_VAS))
    plan = propose(tools, a_decision())
    token = tools.confirm_by_customer(plan.plan_id, subscriber_ref=SUBSCRIBER)

    with pytest.raises(ExecutionFailed):
        tools.execute(plan.plan_id, confirmation=token, idempotency_key="k18")

    result = tools.result_for(plan.plan_id)
    assert result is not None
    failed = [a for a in result.actions if a.status is ActionStatus.FAILED]
    assert failed and failed[0].error_code == "UPSTREAM_TIMEOUT"


# --------------------------------------------------------------------------- #
# Concurrency (improvement plan Phase 0, defect F1)
# --------------------------------------------------------------------------- #


def _hammer(tools: ToolLayer, plan_id: str, token, key: str, threads: int = 50):
    """Fire `threads` identical execute calls at the same instant."""
    import sys
    import threading

    fresh, replayed, errors = [], [], []
    barrier = threading.Barrier(threads)

    def go() -> None:
        barrier.wait()
        try:
            result = tools.execute(plan_id, confirmation=token, idempotency_key=key)
            (replayed if result.replayed else fresh).append(result)
        except Exception as error:
            errors.append(type(error).__name__)

    original = sys.getswitchinterval()
    sys.setswitchinterval(1e-7)  # force frequent switches so a race cannot hide
    try:
        workers = [threading.Thread(target=go) for _ in range(threads)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()
    finally:
        sys.setswitchinterval(original)
    return fresh, replayed, errors


def test_fifty_concurrent_identical_calls_execute_exactly_once(registry, world):
    """The gate: 50 concurrent identical POSTs -> exactly one execution.

    Money was already safe before this fix, but duplicates received
    CONFIRMATION_INVALID instead of the original result: what a customer
    double-tapping Confirm would have seen after a successful refund.
    """
    for _ in range(12):
        fresh_registry = AdapterRegistry(world=build_demo_world())
        tools = tool_layer(fresh_registry.command_port)
        subscriber = ref_for(DILANI)
        opening = fresh_registry.world.account(subscriber).balance_lkr

        plan = tools.propose(
            a_decision(outcome=Outcome.AUTO_FIX, actions=[ActionType.REFUND]),
            subscriber_ref=subscriber,
            created_by="stream",
        )
        token = tools.authorise_auto_fix(plan.plan_id)

        fresh, replayed, errors = _hammer(tools, plan.plan_id, token, "same-key")

        assert errors == [], f"a duplicate must never error: {set(errors)}"
        assert len(fresh) == 1, "exactly one execution"
        assert len(replayed) == 49, "every duplicate replays the original result"
        assert fresh_registry.world.account(subscriber).balance_lkr == opening + Decimal("49.00")


def test_concurrent_duplicates_all_see_the_same_failure(registry):
    """A failing call must not hand duplicates a different, confusing error."""
    tools = tool_layer(_FailingPort(registry.command_port, ActionType.REFUND))
    plan = tools.propose(
        a_decision(outcome=Outcome.AUTO_FIX, actions=[ActionType.REFUND]),
        subscriber_ref=ref_for(DILANI),
        created_by="stream",
    )
    token = tools.authorise_auto_fix(plan.plan_id)

    fresh, replayed, errors = _hammer(tools, plan.plan_id, token, "failing-key", threads=20)

    assert not fresh and not replayed
    assert set(errors) == {"ExecutionFailed"}, "one outcome, delivered to everyone"


def test_a_token_cannot_be_redeemed_twice_under_concurrency(registry):
    """Single use must come from a lock, not from the GIL (defect F1, part 2)."""
    import sys
    import threading

    service = confirmations()
    token = service.mint("PLAN-1", confirmed_by=ConfirmedBy.CUSTOMER, principal_ref="sub")
    accepted, refused = [], []
    barrier = threading.Barrier(40)

    def go() -> None:
        barrier.wait()
        try:
            service.redeem(token.value, plan_id="PLAN-1")
            accepted.append(1)
        except ConfirmationInvalid:
            refused.append(1)

    original = sys.getswitchinterval()
    sys.setswitchinterval(1e-7)
    try:
        workers = [threading.Thread(target=go) for _ in range(40)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()
    finally:
        sys.setswitchinterval(original)

    assert len(accepted) == 1, "exactly one redemption"
    assert len(refused) == 39


def test_a_final_refusal_is_replayed_for_the_same_key(registry, world):
    """One key, one answer, when the refusal was a decision.

    A caller must not get a different outcome for the same request by asking
    twice, so a refusal the policy made is recorded and replayed.
    """
    tools = tool_layer(registry.command_port)
    plan = tools.propose(
        a_decision(), subscriber_ref=SUBSCRIBER, created_by="agent-1", params=vas_params()
    )

    with pytest.raises(ConfirmationInvalid):
        tools.execute(plan.plan_id, confirmation="not-a-real-token", idempotency_key="final-key")
    with pytest.raises(ConfirmationInvalid):
        tools.execute(plan.plan_id, confirmation="not-a-real-token", idempotency_key="final-key")


def test_a_budget_exhausted_plan_executes_once_after_the_budget_resets(registry, world):
    """M-ACT acceptance 1, and the stuck-plan defect it fixes.

    The prototype recorded the first failure against the idempotency key and
    replayed it forever, so a plan refused because the day's refund allowance
    was spent could never execute, even after midnight. The refusal is now
    transient: the key stays claimable and the retry is a real attempt.

    It also has to execute exactly **once**, not once per attempt.
    """
    # Exactly one refund fits in the day.
    budget = RefundBudget(daily_limit_lkr="49.00")
    tools = tool_layer(registry.command_port, budget=budget)

    spent_today = propose(tools, a_decision())
    tools.execute(
        spent_today.plan_id,
        confirmation=tools.confirm_by_customer(spent_today.plan_id, subscriber_ref=SUBSCRIBER),
        idempotency_key="first-plan",
    )

    refused = propose(tools, a_decision())
    token = tools.confirm_by_customer(refused.plan_id, subscriber_ref=SUBSCRIBER)
    before = world.account(SUBSCRIBER).balance_lkr

    with pytest.raises(BudgetExhausted):
        tools.execute(refused.plan_id, confirmation=token, idempotency_key="retry-key")
    assert world.account(SUBSCRIBER).balance_lkr == before, "a refusal moves no money"

    budget.start_new_day()

    # The same key and the same token: the refusal was about the budget, so the
    # customer's single-use authority must not have been spent on it.
    result = tools.execute(refused.plan_id, confirmation=token, idempotency_key="retry-key")

    assert result.status is PlanStatus.COMPLETED
    assert not result.replayed, "this was a new attempt, not a replay"
    assert world.account(SUBSCRIBER).balance_lkr - before == Decimal("49.00")

    # And a third call on the settled key replays rather than refunding again.
    again = tools.execute(refused.plan_id, confirmation=token, idempotency_key="retry-key")
    assert again.replayed
    assert world.account(SUBSCRIBER).balance_lkr - before == Decimal("49.00")
