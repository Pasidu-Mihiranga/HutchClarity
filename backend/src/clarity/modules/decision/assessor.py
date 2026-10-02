"""Turns a rule evaluation into the policy's input document.

Kept separate from :mod:`clarity.modules.decision.policy` so the policy stays a
pure function of a hashable input, which is what makes replay exact.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from clarity.contracts.decision import (
    MONEY_BACK_ONLY,
    BudgetState,
    DecisionInput,
    RiskSignals,
)
from clarity.contracts.timeline import EventType, EvidenceSnapshot
from clarity.kernel.common import ZERO, money
from clarity.modules.detection.public import RuleEvaluation

#: A refund Clarity itself made, used for the repeat-refund velocity signal.
_CLARITY_REFUND_REASONS = frozenset({"clarity_refund"})


def build_risk_signals(
    snapshot: EvidenceSnapshot,
    *,
    now: datetime,
    customer_requested_human: bool = False,
) -> RiskSignals:
    """Derive risk signals from evidence rather than from a caller's claim.

    Everything here comes from the timeline, so the same case always produces
    the same signals and nobody can soften a risk flag by passing a different
    argument. In production the identity adapter supplies SIM-swap and fraud
    flags the same way (plan §9.3).
    """
    swaps = snapshot.of_type(EventType.SIM_SWAP)
    sim_swap_days = (now - swaps[-1].occurred_at).days if swaps else None

    recent_refunds = sum(
        1
        for event in snapshot.of_type(EventType.BALANCE_CREDITED)
        if str(event.attr("reason", "")) in _CLARITY_REFUND_REASONS
        and (now - event.occurred_at) <= timedelta(days=30)
    )

    return RiskSignals(
        sim_swap_days=sim_swap_days,
        fraud_flag=any(
            bool(event.attr("fraud_flag", False)) for event in snapshot.of_type(EventType.SIM_SWAP)
        ),
        refunds_last_30d=recent_refunds,
        customer_requested_human=customer_requested_human,
    )


def build_decision_input(
    *,
    case_id: str,
    snapshot: EvidenceSnapshot,
    evaluation: RuleEvaluation,
    risk: RiskSignals,
    budget: BudgetState,
    channel_supports_confirmation: bool = True,
    as_of: datetime | None = None,
) -> DecisionInput:
    """Assemble exactly what the policy is allowed to see."""
    top = evaluation.top

    amount = ZERO
    money_back_only = False
    whitelisted = False
    disclosed = False
    confidence = Decimal("0")

    if top is not None:
        amount = money(top.assessment.money_effect_lkr or ZERO)
        actions = set(top.assessment.allowed_actions)
        # "Money back only" means every permitted action just returns money;
        # anything that also changes a service needs the customer's say-so.
        money_back_only = bool(actions) and actions <= MONEY_BACK_ONLY
        whitelisted = top.pack.auto_fix_whitelisted
        disclosed = top.pack.disclosed_to_customer
        confidence = top.assessment.confidence

    return DecisionInput(
        case_id=case_id,
        snapshot_hash=snapshot.snapshot_hash,
        evidence_complete=evaluation.evidence_complete,
        top_cause_ref=top.assessment.ref if top else None,
        top_confidence=confidence,
        margin=evaluation.margin,
        amount_lkr=amount,
        money_back_only=money_back_only,
        rule_auto_whitelisted=whitelisted,
        disclosed_to_customer=disclosed,
        risk=risk,
        budget=budget,
        channel_supports_confirmation=channel_supports_confirmation,
        as_of=as_of,
    )
