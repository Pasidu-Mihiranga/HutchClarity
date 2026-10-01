"""Decision policy tests (plan §14.2).

These encode the promise that separates Clarity from a chatbot: money only
moves through a narrow, stated set of conditions, and anything outside them
reaches a human.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from clarity.core.decision.policy import DecisionPolicy, PolicyThresholds
from clarity.schemas.common import money
from clarity.schemas.decision import (
    ActionType,
    BudgetState,
    DecisionInput,
    HandoffReason,
    Outcome,
    RiskSignals,
)


def an_input(**overrides) -> DecisionInput:
    """A clean, high-confidence, money-back-only case: the auto-fix candidate."""
    defaults = {
        "case_id": "CASE-T",
        "snapshot_hash": "sha256:test",
        "evidence_complete": True,
        "top_cause_ref": "DUPLICATE_RELOAD@2",
        "top_confidence": Decimal("0.97"),
        "margin": Decimal("1.0"),
        "amount_lkr": money("3500.00"),
        "money_back_only": True,
        "rule_auto_whitelisted": True,
        "disclosed_to_customer": False,
        "risk": RiskSignals(),
        "budget": BudgetState(global_remaining_lkr=money("100000")),
    }
    return DecisionInput(**(defaults | overrides))


@pytest.fixture
def policy() -> DecisionPolicy:
    """The policy under the caps that apply to DUPLICATE_RELOAD.

    In production these are resolved per decision from config/policy, where
    the global auto-fix cap is LKR 1,000 and this rule carries a scoped
    ceiling of LKR 3,500 (the deck's zero-contact example). Stating them here
    keeps the unit tests honest about which cap they are exercising.
    """
    return DecisionPolicy(
        PolicyThresholds(auto_cap_lkr=money("3500.00"), one_tap_cap_lkr=money("10000.00"))
    )


@pytest.fixture
def global_policy() -> DecisionPolicy:
    """The policy with no rule-scoped override: the global caps only."""
    return DecisionPolicy()


# --------------------------------------------------------------------------- #
# Auto-fix: the narrowest door
# --------------------------------------------------------------------------- #


def test_clean_duplicate_reload_is_auto_fixed(policy: DecisionPolicy):
    """Deck S5: a double reload is refunded before the customer notices."""
    assert policy.decide(an_input()).outcome is Outcome.AUTO_FIX


def test_service_changing_cause_needs_the_customer_tap(policy: DecisionPolicy):
    """A refund plus switching a subscription off is never silent."""
    decision = policy.decide(
        an_input(
            top_cause_ref="VAS_NO_CONSENT@4",
            money_back_only=False,
            rule_auto_whitelisted=False,
            amount_lkr=money("49.00"),
            top_confidence=Decimal("0.96"),
        )
    )

    assert decision.outcome is Outcome.ONE_TAP_FIX


def test_rule_not_whitelisted_never_auto_fixes(policy: DecisionPolicy):
    """Whitelisting is a governance act; high confidence alone is not enough."""
    decision = policy.decide(an_input(rule_auto_whitelisted=False))

    assert decision.outcome is Outcome.ONE_TAP_FIX


def test_amount_above_the_auto_cap_is_not_auto_fixed(policy: DecisionPolicy):
    decision = policy.decide(an_input(amount_lkr=money("3500.01")))

    assert decision.outcome is Outcome.ONE_TAP_FIX


def test_a_rule_without_its_own_ceiling_uses_the_low_global_cap(
    global_policy: DecisionPolicy,
):
    """The point of A5: raising one rule's cap must not raise every rule's.

    The same LKR 3,500 that auto-fixes for DUPLICATE_RELOAD needs a human for
    a rule that has not earned a scoped ceiling.
    """
    decision = global_policy.decide(an_input(top_cause_ref="DUPLICATE_VAS_CHARGE@1"))

    assert decision.outcome is Outcome.ONE_TAP_FIX
    assert any("auto-fix" in line or "cap" in line for line in decision.rationale)


def test_confidence_below_the_auto_threshold_is_not_auto_fixed(policy: DecisionPolicy):
    decision = policy.decide(an_input(top_confidence=Decimal("0.94")))

    assert decision.outcome is Outcome.ONE_TAP_FIX


# --------------------------------------------------------------------------- #
# Risk routes to a human before money moves
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("risk", "why"),
    [
        (RiskSignals(fraud_flag=True), "fraud flag"),
        (RiskSignals(sim_swap_days=2), "recent SIM swap"),
        (RiskSignals(refunds_last_30d=9), "repeat refunds"),
    ],
)
def test_risk_signals_force_staff_approval(policy: DecisionPolicy, risk, why):
    decision = policy.decide(an_input(risk=risk))

    assert decision.outcome is Outcome.STAFF_APPROVAL, why
    assert decision.rationale, "staff must be told why this reached them"


def test_sim_swap_outside_the_window_does_not_block(policy: DecisionPolicy):
    """Boundary: the window is 7 days, so day 8 is clear."""
    assert policy.decide(an_input(risk=RiskSignals(sim_swap_days=8))).outcome is Outcome.AUTO_FIX


def test_sim_swap_on_the_boundary_day_still_blocks(policy: DecisionPolicy):
    decision = policy.decide(an_input(risk=RiskSignals(sim_swap_days=7)))

    assert decision.outcome is Outcome.STAFF_APPROVAL


def test_customer_asking_for_a_person_always_wins(policy: DecisionPolicy):
    """Deck S7: hand off when the customer asks, whatever the rules say."""
    decision = policy.decide(an_input(risk=RiskSignals(customer_requested_human=True)))

    assert decision.outcome is Outcome.HANDOFF
    assert decision.handoff_reason is HandoffReason.CUSTOMER_REQUESTED
    assert decision.allowed_actions == []


# --------------------------------------------------------------------------- #
# Evidence and confidence
# --------------------------------------------------------------------------- #


def test_incomplete_evidence_hands_off_rather_than_guessing(policy: DecisionPolicy):
    """Deck S7: missing log -> a human, never a guess."""
    decision = policy.decide(an_input(evidence_complete=False))

    assert decision.outcome is Outcome.HANDOFF
    assert decision.handoff_reason is HandoffReason.EVIDENCE_INCOMPLETE


def test_no_matching_cause_hands_off(policy: DecisionPolicy):
    decision = policy.decide(an_input(top_cause_ref=None, top_confidence=Decimal("0")))

    assert decision.handoff_reason is HandoffReason.NO_CAUSE_FOUND


def test_low_confidence_hands_off(policy: DecisionPolicy):
    decision = policy.decide(an_input(top_confidence=Decimal("0.60")))

    assert decision.handoff_reason is HandoffReason.LOW_CONFIDENCE


def test_middling_confidence_goes_to_staff_not_the_customer(policy: DecisionPolicy):
    decision = policy.decide(an_input(top_confidence=Decimal("0.85")))

    assert decision.outcome is Outcome.STAFF_APPROVAL


def test_close_second_cause_is_treated_as_a_conflict(policy: DecisionPolicy):
    """Deck S7: 'two causes close' is a staff case."""
    decision = policy.decide(an_input(margin=Decimal("0.05")))

    assert decision.outcome is Outcome.STAFF_APPROVAL


# --------------------------------------------------------------------------- #
# Explain-only, caps and budget
# --------------------------------------------------------------------------- #


def test_disclosed_terms_are_explained_not_refunded(policy: DecisionPolicy):
    """Deck S7: 'Rule the customer saw: explained, not refunded'."""
    decision = policy.decide(
        an_input(top_cause_ref="FUP_CAP_REACHED@3", disclosed_to_customer=True)
    )

    assert decision.outcome is Outcome.EXPLAIN_ONLY


def test_large_amount_goes_to_staff(policy: DecisionPolicy):
    decision = policy.decide(an_input(amount_lkr=money("12000.00")))

    assert decision.outcome is Outcome.STAFF_APPROVAL


def test_very_large_amount_demands_two_approvers(policy: DecisionPolicy):
    decision = policy.decide(an_input(amount_lkr=money("30000.00")))

    assert decision.outcome is Outcome.STAFF_APPROVAL
    assert any("two approvers" in line for line in decision.rationale)


def test_exhausted_budget_degrades_to_staff_rather_than_failing(policy: DecisionPolicy):
    """Plan §14.4: when the budget runs out, fixes degrade, they do not stop."""
    decision = policy.decide(an_input(budget=BudgetState(global_remaining_lkr=money("100.00"))))

    assert decision.outcome is Outcome.STAFF_APPROVAL
    assert any("budget" in line for line in decision.rationale)


def test_per_rule_budget_is_enforced_too(policy: DecisionPolicy):
    decision = policy.decide(
        an_input(
            budget=BudgetState(
                global_remaining_lkr=money("100000"), rule_remaining_lkr=money("10.00")
            )
        )
    )

    assert decision.outcome is Outcome.STAFF_APPROVAL


def test_channel_without_confirmation_routes_to_staff(policy: DecisionPolicy):
    """USSD/SMS cannot capture a reliable confirmation for a service change."""
    decision = policy.decide(
        an_input(
            money_back_only=False,
            rule_auto_whitelisted=False,
            channel_supports_confirmation=False,
        )
    )

    assert decision.outcome is Outcome.STAFF_APPROVAL


# --------------------------------------------------------------------------- #
# Reproducibility and configuration
# --------------------------------------------------------------------------- #


def test_same_input_always_gives_the_same_outcome(policy: DecisionPolicy):
    """Determinism is what makes replay and 'policy what-if' meaningful."""
    case_input = an_input()

    outcomes = {policy.decide(case_input).outcome for _ in range(25)}

    assert outcomes == {Outcome.AUTO_FIX}


def test_input_hash_is_stable_and_recorded(policy: DecisionPolicy):
    case_input = an_input()

    decision = policy.decide(case_input)

    assert decision.input_hash == case_input.input_hash
    assert decision.policy_version == policy.thresholds.version


def test_thresholds_are_configurable(policy: DecisionPolicy):
    """Deck S7: 'Thresholds configurable'. Tightening them must bind."""
    strict = DecisionPolicy(PolicyThresholds(version="test.strict", auto_cap_lkr=money("100.00")))

    assert strict.decide(an_input()).outcome is Outcome.ONE_TAP_FIX


def test_actions_are_only_those_the_rule_allows(policy: DecisionPolicy):
    decision = policy.decide(
        an_input(money_back_only=False, rule_auto_whitelisted=False),
        allowed_actions=[ActionType.REFUND, ActionType.DEACTIVATE_VAS],
    )

    assert decision.allowed_actions == [ActionType.REFUND, ActionType.DEACTIVATE_VAS]
