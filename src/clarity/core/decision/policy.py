"""Decision policy: the gate between a detected cause and money moving.

This implements the outcome matrix from deck S7 and plan §14.2 in the order of
plan Diagram 4. Every branch records a rationale string, so a staff member or
an auditor can read why a case went where it went without re-running anything.

**Prototype note.** The plan runs this as OPA/Rego bundles (§14.3). Here it is
Python over the same input document, and :meth:`DecisionPolicy.decide` takes a
:class:`~clarity.schemas.decision.DecisionInput` that is hashed and stored, so
swapping in OPA later does not change the recorded contract.

Every threshold is a **PROPOSED TARGET - REQUIRES HUTCH VALIDATION**
(Finance/CX/Risk own these numbers, deck S7: "Thresholds configurable").
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, ClassVar

from pydantic import Field

from clarity.core.policy.resolver import ConfigSnapshot
from clarity.core.policy.switches import SwitchState
from clarity.schemas.common import ClarityModel, Money, money
from clarity.schemas.decision import (
    ActionType,
    CauseAssessment,
    Decision,
    DecisionInput,
    HandoffReason,
    Outcome,
)
from clarity.schemas.ids import new_id


class PolicyThresholds(ClarityModel):
    """Versioned, configurable decision thresholds.

    The version string is recorded on every decision so "policy what-if" can
    replay historic cases under a candidate version (deck S9).
    """

    version: str = "2027.09.1"

    auto_min_confidence: Decimal = Decimal("0.95")
    auto_cap_lkr: Money = Field(
        default=money("1000.00"),
        description="Low by default. A rule whose evidence justifies more carries a "
        "scoped override instead, so raising one rule's ceiling does not raise "
        "every rule's (config/policy/decision.yaml).",
    )
    one_tap_min_confidence: Decimal = Decimal("0.90")
    one_tap_cap_lkr: Money = money("5000.00")
    staff_min_confidence: Decimal = Field(
        default=Decimal("0.70"),
        description="Below this nothing is proposed to staff; the case is handed off.",
    )
    four_eyes_threshold_lkr: Money = money("25000.00")
    conflict_margin: Decimal = Field(
        default=Decimal("0.20"),
        description="Two causes closer than this are treated as conflicting.",
    )
    sim_swap_window_days: int = 7
    repeat_refund_limit_30d: int = Field(
        default=3, description="More refunds than this in 30 days routes to staff."
    )

    #: The policy keys these thresholds come from, when a resolver is in use.
    KEYS: ClassVar[dict[str, str]] = {
        "auto_min_confidence": "decision.auto_fix.min_confidence",
        "auto_cap_lkr": "decision.auto_fix.cap_lkr",
        "one_tap_min_confidence": "decision.one_tap.min_confidence",
        "one_tap_cap_lkr": "decision.one_tap.cap_lkr",
        "staff_min_confidence": "decision.staff.min_confidence",
        "four_eyes_threshold_lkr": "decision.four_eyes.threshold_lkr",
        "conflict_margin": "decision.conflict_margin",
        "sim_swap_window_days": "decision.risk.sim_swap_window_days",
        "repeat_refund_limit_30d": "decision.risk.repeat_refund_limit_30d",
    }

    @classmethod
    def from_snapshot(cls, snapshot: ConfigSnapshot, *, version: str) -> PolicyThresholds:
        """Build thresholds from resolved policy values.

        The snapshot is what the decision records, so the thresholds a decision
        used can always be reconstructed exactly - including for a charge from
        months ago, under the caps that applied then.
        """
        values: dict[str, Any] = {"version": version}
        for field_name, key in cls.KEYS.items():
            if key in snapshot.resolved:
                values[field_name] = snapshot.resolved[key].value
        return cls.model_validate(values)


class DecisionPolicy:
    """Deterministic. Same input and thresholds always give the same outcome."""

    def __init__(self, thresholds: PolicyThresholds | None = None) -> None:
        self.thresholds = thresholds or PolicyThresholds()

    def decide(
        self,
        case_input: DecisionInput,
        *,
        allowed_actions: list[ActionType] | None = None,
        ruled_out: list[CauseAssessment] | None = None,
        thresholds: PolicyThresholds | None = None,
        switches: SwitchState | None = None,
        config_snapshot_hash: str | None = None,
    ) -> Decision:
        # Thresholds may be supplied per decision (resolved as_of the event
        # time), which is what makes a point-in-time replay possible.
        t = thresholds or self.thresholds
        flags = switches or SwitchState()
        why: list[str] = []
        actions = list(allowed_actions or [])

        def verdict(
            outcome: Outcome,
            *,
            handoff: HandoffReason | None = None,
            acts: list[ActionType] | None = None,
        ) -> Decision:
            return Decision(
                decision_id=new_id("DEC"),
                case_id=case_input.case_id,
                outcome=outcome,
                policy_version=t.version,
                input_hash=case_input.input_hash,
                allowed_actions=acts if acts is not None else actions,
                amount_lkr=case_input.amount_lkr,
                top_cause_ref=case_input.top_cause_ref,
                ruled_out=list(ruled_out or []),
                handoff_reason=handoff,
                rationale=why,
                config_snapshot_hash=config_snapshot_hash,
                as_of=case_input.as_of,
            )

        # 1. The customer asked for a person. Always honoured (deck S7).
        if case_input.risk.customer_requested_human:
            why.append("customer asked for a person")
            return verdict(Outcome.HANDOFF, handoff=HandoffReason.CUSTOMER_REQUESTED, acts=[])

        # 2. Missing evidence is not weak evidence: never guess (deck S7).
        if not case_input.evidence_complete:
            why.append("required evidence could not be read, so no cause can be confirmed")
            return verdict(Outcome.HANDOFF, handoff=HandoffReason.EVIDENCE_INCOMPLETE, acts=[])

        # 3. No rule matched.
        if case_input.top_cause_ref is None:
            why.append("no cause rule matched this evidence")
            return verdict(Outcome.HANDOFF, handoff=HandoffReason.NO_CAUSE_FOUND, acts=[])

        # 4. Risk signals send a case to a human before any money moves.
        sim_swap = case_input.risk.sim_swap_days
        if case_input.risk.fraud_flag:
            why.append("a fraud flag is set on this account")
            return verdict(Outcome.STAFF_APPROVAL)
        if sim_swap is not None and sim_swap <= t.sim_swap_window_days:
            why.append(f"SIM swap {sim_swap} days ago (within {t.sim_swap_window_days})")
            return verdict(Outcome.STAFF_APPROVAL)
        if case_input.risk.refunds_last_30d > t.repeat_refund_limit_30d:
            why.append(
                f"{case_input.risk.refunds_last_30d} refunds in 30 days "
                f"exceeds the limit of {t.repeat_refund_limit_30d}"
            )
            return verdict(Outcome.STAFF_APPROVAL)

        # 5. Two plausible causes: a human decides which (deck S7).
        if case_input.margin < t.conflict_margin:
            why.append(
                f"top two causes are {case_input.margin} apart, "
                f"under the {t.conflict_margin} conflict margin"
            )
            return verdict(Outcome.STAFF_APPROVAL)

        # 6. A rule the customer saw at purchase is explained, not refunded.
        if case_input.disclosed_to_customer:
            why.append("the cause is a term disclosed to the customer at purchase")
            return verdict(Outcome.EXPLAIN_ONLY)

        # 7. Confidence bands.
        confidence = case_input.top_confidence
        if confidence < t.staff_min_confidence:
            why.append(f"confidence {confidence} is below {t.staff_min_confidence}")
            return verdict(Outcome.HANDOFF, handoff=HandoffReason.LOW_CONFIDENCE, acts=[])
        if confidence < t.one_tap_min_confidence:
            why.append(
                f"confidence {confidence} is below the {t.one_tap_min_confidence} "
                "needed to offer a fix directly"
            )
            return verdict(Outcome.STAFF_APPROVAL)

        # 8. Amount caps.
        amount = case_input.amount_lkr
        if amount > t.one_tap_cap_lkr:
            why.append(f"LKR {amount} is above the one-tap cap of LKR {t.one_tap_cap_lkr}")
            if amount > t.four_eyes_threshold_lkr:
                why.append(
                    f"LKR {amount} is above LKR {t.four_eyes_threshold_lkr}, "
                    "so two approvers are required"
                )
            return verdict(Outcome.STAFF_APPROVAL)

        # 9. Budget. When it runs out, fixes degrade to staff rather than stop.
        if amount > 0 and not case_input.budget.allows(amount):
            why.append("the refund budget for today is exhausted")
            return verdict(Outcome.STAFF_APPROVAL)

        # 10. Auto-fix is the narrowest door: money back only, nothing switched
        #     off, high confidence, small amount, the rule whitelisted - and no
        #     kill switch pulled.
        if not flags.auto_fix_allowed and case_input.money_back_only:
            why.append(
                "auto-fix is switched off"
                + ("" if flags.auto_fix_global else " globally")
                + ", so a person confirms this"
            )
            return verdict(Outcome.STAFF_APPROVAL)

        if (
            case_input.money_back_only
            and case_input.rule_auto_whitelisted
            and confidence >= t.auto_min_confidence
            and amount <= t.auto_cap_lkr
        ):
            why.append(
                f"money-back-only, confidence {confidence} and LKR {amount} "
                "are inside the auto-fix limits"
            )
            return verdict(Outcome.AUTO_FIX)

        # Auto-fix was declined. Say which condition failed, because "a service
        # change is involved" would be wrong and misleading when the real
        # reason was the amount or the confidence.
        if case_input.money_back_only and case_input.rule_auto_whitelisted:
            if amount > t.auto_cap_lkr:
                why.append(
                    f"LKR {amount} is above the auto-fix cap of LKR {t.auto_cap_lkr} "
                    "for this cause, so the customer confirms"
                )
            else:
                why.append(
                    f"confidence {confidence} is below the {t.auto_min_confidence} "
                    "needed to fix without asking, so the customer confirms"
                )
            return verdict(Outcome.ONE_TAP_FIX)

        # 11. Everything else that is safe: the customer confirms in one tap.
        if not flags.customer_actions:
            why.append("customer confirmations are switched off, so staff complete this")
            return verdict(Outcome.STAFF_APPROVAL)

        if not case_input.channel_supports_confirmation:
            why.append("this channel cannot capture a confirmation, so staff complete it")
            return verdict(Outcome.STAFF_APPROVAL)

        why.append(
            "a service change is involved or the rule is not auto-whitelisted, "
            "so the customer confirms"
        )
        return verdict(Outcome.ONE_TAP_FIX)
