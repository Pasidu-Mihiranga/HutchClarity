"""End-to-end acceptance tests for the four prototype journeys (plan §1.9, §6).

Each test runs the full deterministic path - adapters, timeline, rules,
decision policy - against the synthetic world, and asserts the outcome the
deck promises for that journey.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from clarity.contracts.decision import ActionType, BudgetState, HandoffReason, Outcome, RiskSignals
from clarity.integration.drivers.mock.world import DEMO_NOW, SyntheticWorld, ref_for
from clarity.kernel.common import EventSource
from clarity.modules.decision.assessor import build_decision_input
from clarity.modules.decision.policy import DecisionPolicy, PolicyThresholds
from clarity.modules.detection.engine import RuleEngine
from clarity.modules.timeline.builder import TimelineBuilder
from clarity.platform.config.resolver import PolicyResolver
from tests.conftest import snapshot_for

DILANI = "+94771234567"  # VAS charged with no consent
NIMAL = "+94772223333"  # reload taken twice
KUMAR = "+94773334444"  # "unlimited" hit a disclosed FUP cap
PRIYA = "+94774445555"  # large reload not credited, recent SIM swap


def run(
    *,
    policies: PolicyResolver,
    builder: TimelineBuilder,
    engine: RuleEngine,
    policy: DecisionPolicy,
    world: SyntheticWorld,
    msisdn: str,
    budget: BudgetState,
    customer_requested_human: bool = False,
):
    """Drive one case through the whole deterministic path."""
    account = world.account(ref_for(msisdn))
    assert account is not None
    snapshot = snapshot_for(builder, msisdn)
    evaluation = engine.evaluate(snapshot)
    risk = RiskSignals(
        sim_swap_days=(DEMO_NOW - account.sim_swap_at).days if account.sim_swap_at else None,
        fraud_flag=account.fraud_flag,
        refunds_last_30d=account.refunds_last_30d,
        customer_requested_human=customer_requested_human,
    )
    decision_input = build_decision_input(
        case_id="CASE-T",
        snapshot=snapshot,
        evaluation=evaluation,
        risk=risk,
        budget=budget,
    )
    # Resolve thresholds the way production does: as_of the disputed event,
    # scoped to the cause, so a rule-scoped cap applies here too.
    rule_id = evaluation.top.assessment.rule_id if evaluation.top else None
    as_of = (
        min(e.occurred_at for e in evaluation.top.bindings.values())
        if evaluation.top and evaluation.top.bindings
        else DEMO_NOW
    )
    config = policies.snapshot_for(
        list(PolicyThresholds.KEYS.values()), as_of=as_of, context={"rule": rule_id}
    )

    decision = policy.decide(
        decision_input,
        allowed_actions=evaluation.top.assessment.allowed_actions if evaluation.top else [],
        ruled_out=evaluation.ruled_out,
        thresholds=PolicyThresholds.from_snapshot(config, version=policy.thresholds.version),
        config_snapshot_hash=config.hash,
    )
    return snapshot, evaluation, decision


@pytest.fixture
def journey(builder, engine, policy, policies, world, ample_budget):
    def _run(msisdn: str, **kwargs):
        return run(
            policies=policies,
            builder=builder,
            engine=engine,
            policy=policy,
            world=world,
            msisdn=msisdn,
            budget=ample_budget,
            **kwargs,
        )

    return _run


# --------------------------------------------------------------------------- #
# Journey 1 - VAS without consent (deck S6, S7)
# --------------------------------------------------------------------------- #


def test_vas_without_consent_offers_a_one_tap_fix(journey):
    _, evaluation, decision = journey(DILANI)

    assert evaluation.top is not None
    assert evaluation.top.assessment.rule_id == "VAS_NO_CONSENT"
    assert decision.outcome is Outcome.ONE_TAP_FIX
    assert decision.amount_lkr == Decimal("49.00")
    assert set(decision.allowed_actions) == {
        ActionType.REFUND,
        ActionType.DEACTIVATE_VAS,
        ActionType.BLOCK_MERCHANT_UNTIL_OPTIN,
    }


def test_vas_case_reports_what_was_ruled_out(journey):
    """Deck S7 shows the customer what was excluded, not just what matched."""
    _, _evaluation, decision = journey(DILANI)

    ruled_out = {cause.rule_id for cause in decision.ruled_out}

    assert {"PACK_EXPIRY_BURN", "RELOAD_NOT_CREDITED"} <= ruled_out
    assert all(cause.reason for cause in decision.ruled_out), "each exclusion needs a reason"


def test_vas_case_cites_the_charge_as_evidence(journey):
    snapshot, evaluation, _ = journey(DILANI)

    cited = evaluation.top.assessment.evidence_refs
    assert cited, "a cause must point at the evidence behind it"
    for event_id in cited:
        assert snapshot.by_id(event_id) is not None, "every citation resolves to real evidence"


# --------------------------------------------------------------------------- #
# Journey 2 - duplicate reload, zero contact (deck S2, S5)
# --------------------------------------------------------------------------- #


def test_duplicate_reload_is_auto_fixed_without_contact(journey):
    _, evaluation, decision = journey(NIMAL)

    assert evaluation.top.assessment.rule_id == "DUPLICATE_RELOAD"
    assert decision.outcome is Outcome.AUTO_FIX, "the deck's zero-contact promise"
    assert decision.amount_lkr == Decimal("3500.00")
    assert decision.allowed_actions == [ActionType.REFUND], "money back only, nothing else"


def test_duplicate_reload_needs_a_human_when_payments_cannot_be_read(
    journey, world: SyntheticWorld
):
    """Degradation: an unreadable source must never become a silent refund."""
    world.unavailable.add(EventSource.PAYMENTS)

    _, _, decision = journey(NIMAL)

    assert decision.outcome is Outcome.HANDOFF
    assert decision.handoff_reason is HandoffReason.EVIDENCE_INCOMPLETE


# --------------------------------------------------------------------------- #
# Journey 3 - disclosed fair-use cap (deck S2, S7)
# --------------------------------------------------------------------------- #


def test_disclosed_fup_cap_is_explained_not_refunded(journey):
    _, evaluation, decision = journey(KUMAR)

    assert evaluation.top.assessment.rule_id == "FUP_CAP_REACHED"
    assert decision.outcome is Outcome.EXPLAIN_ONLY
    assert decision.amount_lkr == Decimal("0.00"), "nothing was wrongly charged"


# --------------------------------------------------------------------------- #
# Journey 4 - high-risk disputed reload (deck S7)
# --------------------------------------------------------------------------- #


def test_large_reload_with_recent_sim_swap_goes_to_staff(journey):
    _, evaluation, decision = journey(PRIYA)

    assert evaluation.top.assessment.rule_id == "RELOAD_NOT_CREDITED"
    assert decision.outcome is Outcome.STAFF_APPROVAL
    assert decision.amount_lkr == Decimal("12000.00")
    assert any("SIM swap" in line for line in decision.rationale)


# --------------------------------------------------------------------------- #
# Cross-cutting guarantees
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("msisdn", [DILANI, NIMAL, KUMAR, PRIYA])
def test_any_customer_can_always_reach_a_person(journey, msisdn):
    """Deck S7 guardrail: asking for a human overrides every other outcome."""
    _, _, decision = journey(msisdn, customer_requested_human=True)

    assert decision.outcome is Outcome.HANDOFF
    assert decision.handoff_reason is HandoffReason.CUSTOMER_REQUESTED


@pytest.mark.parametrize("msisdn", [DILANI, NIMAL, KUMAR, PRIYA])
def test_every_decision_is_reproducible_from_its_evidence(journey, msisdn):
    """Same evidence and same rules must give the same verdict, every time."""
    first_snapshot, _, first = journey(msisdn)
    second_snapshot, _, second = journey(msisdn)

    assert first_snapshot.snapshot_hash == second_snapshot.snapshot_hash
    assert first.input_hash == second.input_hash
    assert first.outcome is second.outcome
    assert first.amount_lkr == second.amount_lkr


@pytest.mark.parametrize("msisdn", [DILANI, NIMAL, KUMAR, PRIYA])
def test_every_decision_names_its_rule_version_and_policy_version(journey, msisdn):
    """Deck S7: 'each decision logs its rule version'."""
    _, _, decision = journey(msisdn)

    assert decision.policy_version
    assert decision.top_cause_ref and "@" in decision.top_cause_ref
    assert decision.rationale, "a decision with no stated reason is not auditable"


def test_exhausted_budget_never_blocks_an_explanation(builder, engine, policy, policies, world):
    """A dry refund budget must not stop Clarity from explaining a charge."""
    from clarity.kernel.common import money

    _, _, decision = run(
        policies=policies,
        builder=builder,
        engine=engine,
        policy=policy,
        world=world,
        msisdn=KUMAR,
        budget=BudgetState(global_remaining_lkr=money("0")),
    )

    assert decision.outcome is Outcome.EXPLAIN_ONLY
