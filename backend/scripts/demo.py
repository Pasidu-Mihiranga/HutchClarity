#!/usr/bin/env python
"""Walk the four prototype journeys through the deterministic core.

    .venv/bin/python scripts/demo.py

Everything printed comes from synthetic data and mock HUTCH systems. No HUTCH
API, credential or production record is involved.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from clarity.contracts.case import Case, CaseTrigger, CustomerReference  # noqa: E402
from clarity.contracts.decision import (  # noqa: E402
    ActionType,
    BudgetState,
    Decision,
    Outcome,
    RiskSignals,
)
from clarity.contracts.timeline import EvidenceSnapshot  # noqa: E402
from clarity.integration.drivers.mock.recurrence import MockRecurrenceProbe  # noqa: E402
from clarity.integration.drivers.mock.world import DEMO_NOW, Account, ref_for  # noqa: E402
from clarity.integration.registry import AdapterRegistry  # noqa: E402
from clarity.kernel.common import Channel, money  # noqa: E402
from clarity.modules.actions.budget import RefundBudget  # noqa: E402
from clarity.modules.actions.layer import EXECUTABLE_OUTCOMES, ToolLayer  # noqa: E402
from clarity.modules.decision.assessor import build_decision_input  # noqa: E402
from clarity.modules.decision.policy import DecisionPolicy  # noqa: E402
from clarity.modules.detection.engine import RuleEngine, RuleEvaluation  # noqa: E402
from clarity.modules.detection.pack import load_packs  # noqa: E402
from clarity.modules.receipts.service import ReceiptService, explain_summary  # noqa: E402
from clarity.modules.receipts.signing import DevSigningService  # noqa: E402
from clarity.modules.timeline.builder import TimelineBuilder, TimelineRequest  # noqa: E402

JOURNEYS = [
    ("1. VAS charged with no consent", "+94771234567", "Dilani · Sinhala · app"),
    ("2. Reload taken twice", "+94772223333", "Nimal · English · no contact"),
    ("3. 'Unlimited' hit a fair-use cap", "+94773334444", "Kumar · Tamil · WhatsApp"),
    ("4. Large reload not credited", "+94774445555", "Priya · English · recent SIM swap"),
]

OUTCOME_NOTE = {
    Outcome.AUTO_FIX: "refunded with no contact at all",
    Outcome.ONE_TAP_FIX: "the customer confirms in one tap",
    Outcome.STAFF_APPROVAL: "a staff member approves before anything moves",
    Outcome.EXPLAIN_ONLY: "explained; nothing was wrongly charged",
    Outcome.HANDOFF: "handed to a person with the full trail",
}


def main() -> int:
    registry = AdapterRegistry()
    builder = TimelineBuilder(registry.read_ports())
    engine = RuleEngine(load_packs(ROOT.parent / "rules" / "packs"))
    policy = DecisionPolicy()
    tools = ToolLayer(registry.command_port, budget=RefundBudget(daily_limit_lkr="250000"))
    receipts = ReceiptService(DevSigningService(), probe=MockRecurrenceProbe(registry.world))
    budget = BudgetState(global_remaining_lkr=money("250000"))

    print("\nHUTCH CLARITY - deterministic core")
    print("Explain every rupee. Fix it by rule. Prove it won't happen again.")
    print(f"\nRules loaded : {', '.join(p.ref for p in engine.packs)}")
    print(f"Policy       : {policy.thresholds.version}")
    print("Data         : SYNTHETIC. HUTCH systems are mocked.\n")

    for title, msisdn, who in JOURNEYS:
        account = registry.world.account(ref_for(msisdn))
        assert account is not None
        snapshot = builder.build(TimelineRequest.for_case("CASE-DEMO", account.ref, now=DEMO_NOW))
        evaluation = engine.evaluate(snapshot)
        risk = RiskSignals(
            sim_swap_days=(DEMO_NOW - account.sim_swap_at).days if account.sim_swap_at else None
        )
        decision = policy.decide(
            build_decision_input(
                case_id="CASE-DEMO",
                snapshot=snapshot,
                evaluation=evaluation,
                risk=risk,
                budget=budget,
            ),
            allowed_actions=evaluation.top.assessment.allowed_actions if evaluation.top else [],
            ruled_out=evaluation.ruled_out,
        )

        print("=" * 78)
        print(f"{title}\n   {who} · {account.masked} · balance LKR {account.balance_lkr}")
        print(
            f"   evidence : {len(snapshot.events)} events from "
            f"{sum(1 for s in snapshot.sources if s.event_count)} of 8 sources"
        )

        if evaluation.top is not None:
            cause = evaluation.top.assessment
            print(f"   cause    : {cause.ref}  (confidence {cause.confidence})")
            if cause.money_effect_lkr:
                print(f"   money    : LKR {cause.money_effect_lkr}")
        else:
            print("   cause    : none matched")

        ruled_out = [c.rule_id for c in evaluation.ruled_out][:3]
        if ruled_out:
            print(f"   ruled out: {', '.join(ruled_out)}")
        if evaluation.indeterminate:
            print(f"   unknown  : {', '.join(c.rule_id for c in evaluation.indeterminate)}")

        print(f"   DECISION : {decision.outcome.value} - {OUTCOME_NOTE[decision.outcome]}")
        for line in decision.rationale:
            print(f"              · {line}")
        if decision.allowed_actions:
            print(f"   actions  : {', '.join(a.value for a in decision.allowed_actions)}")
        print(
            f"   replay   : snapshot {snapshot.snapshot_hash[7:19]} "
            f"· input {decision.input_hash[7:19]}"
        )

        _act(tools, receipts, decision, account, evaluation, snapshot)

    print("=" * 78)
    print("\nRules decided every outcome above. No language model was involved.\n")
    return 0


def _act(
    tools: ToolLayer,
    receipts: ReceiptService,
    decision: Decision,
    account: Account,
    evaluation: RuleEvaluation,
    snapshot: EvidenceSnapshot,
) -> None:
    """Carry the decision through propose -> confirm -> execute."""
    if decision.outcome not in EXECUTABLE_OUTCOMES:
        print("   acted    : nothing to execute for this outcome")
        return

    rule_id = evaluation.top.assessment.rule_id if evaluation.top else None
    plan = tools.propose(
        decision,
        subscriber_ref=account.ref,
        created_by="mcp:customer-assist",
        rule_id=rule_id,
        params={
            ActionType.DEACTIVATE_VAS: {"subscription_id": "SUB-GAME-1"},
            ActionType.BLOCK_MERCHANT_UNTIL_OPTIN: {"merchant_id": "MER-GAMEHUB"},
        },
    )
    print(f"   proposed : {plan.display_summary}")
    print(f"              (proposed by {plan.created_by}, which cannot execute it)")

    # Each outcome needs a different authority, and the AI path has none of them.
    if decision.outcome is Outcome.AUTO_FIX:
        token = tools.authorise_auto_fix(plan.plan_id)
        authority = "system (whitelisted zero-contact refund)"
    elif decision.outcome is Outcome.ONE_TAP_FIX:
        token = tools.confirm_by_customer(plan.plan_id, subscriber_ref=account.ref)
        authority = "customer tapped Confirm"
    else:
        token = tools.approve_by_staff(
            plan.plan_id, approver_ref="sup-1", role="supervisor", mfa_step_up=True
        )
        authority = "supervisor approved with MFA step-up"
        if token is None:
            print("   acted    : held - a second approver is required")
            return

    result = tools.execute(plan.plan_id, confirmation=token, idempotency_key=f"demo:{plan.plan_id}")
    print(f"   authority: {authority}")
    for action in result.actions:
        change = ""
        if action.before_state and action.after_state:
            before = action.before_state.get("balance_lkr")
            after = action.after_state.get("balance_lkr")
            if before and after:
                change = f"  balance {before} -> {after}"
        print(f"   applied  : {action.type.value}{change}")
    print(f"   balance  : LKR {account.balance_lkr} (after)")

    cause = evaluation.top.assessment if evaluation.top else None
    receipt = receipts.issue(
        case=_demo_case(account),
        decision=decision,
        cause=cause,
        snapshot=snapshot,
        execution=result,
        summary=explain_summary(cause, decision, plan.action_types),
        subscriber_ref=account.ref,
        safeguard_params={"merchant_id": "MER-GAMEHUB", "subscription_id": "SUB-GAME-1"},
    )
    check = receipts.verify(receipt.receipt_id)
    print(f"   receipt  : {receipt.receipt_id} · {receipt.verify_url}")
    if receipt.payload.recurrence_test is not None:
        print(
            f"   recurrence: {receipt.payload.recurrence_test.check} = "
            f"{receipt.payload.recurrence_test.result.value}"
        )
    print(f"   verified : {check.display} (signed {check.kid}, chain ok: {check.chain_ok})")


def _demo_case(account: Account) -> Case:
    return Case(
        case_id="CASE-DEMO",
        case_no="CASE-2027-000001",
        customer=CustomerReference(
            subscriber_ref=account.ref,
            msisdn_masked=account.masked,
            preferred_language=account.language,
        ),
        trigger=CaseTrigger.CUSTOMER,
        origin_channel=Channel.APP,
    )


if __name__ == "__main__":
    raise SystemExit(main())
