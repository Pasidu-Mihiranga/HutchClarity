"""GoRules ZEN JDM outcome table adapter (M-DEC, ADR-0026).

The checked-in JDM file is the governed artefact. This adapter evaluates its
ordered predicate rows in process, using the same input contract recorded on a
decision. The row vocabulary is deliberately fixed and reviewable: the table
may reorder or remove rows, while thresholds still come from the effective-
dated policy snapshot.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from clarity.contracts.decision import (
    ActionType,
    CauseAssessment,
    Decision,
    DecisionInput,
    HandoffReason,
    Outcome,
)
from clarity.kernel.ids import new_id
from clarity.modules.decision.policy import DecisionPolicy, PolicyThresholds
from clarity.platform.config.switches import SwitchState


class DecisionTableInvalid(ValueError):
    """The JDM artefact is malformed or names an unknown predicate."""


@dataclass(frozen=True)
class DecisionTableRow:
    row_id: str
    outcome: Outcome


@dataclass(frozen=True)
class DecisionTable:
    version: str
    rows: tuple[DecisionTableRow, ...]

    @classmethod
    def load(cls, path: Path) -> DecisionTable:
        raw = json.loads(path.read_text(encoding="utf-8"))
        try:
            nodes = raw["nodes"]
            node = next(item for item in nodes if item["type"] == "decisionTableNode")
            rules = node["content"]["rules"]
            version = str(raw["version"])
            rows = tuple(
                DecisionTableRow(row_id=str(rule["predicate"]), outcome=Outcome(rule["outcome"]))
                for rule in rules
            )
        except (KeyError, StopIteration, TypeError, ValueError) as error:
            raise DecisionTableInvalid(f"{path}: invalid ZEN decision table") from error
        unknown = {row.row_id for row in rows} - ZenDecisionPolicy.PREDICATES
        if unknown:
            raise DecisionTableInvalid(f"unknown decision predicates: {sorted(unknown)}")
        if not rows or rows[-1].row_id != "true":
            raise DecisionTableInvalid("the final decision-table row must be the default 'true'")
        return cls(version=version, rows=rows)


class ZenDecisionPolicy(DecisionPolicy):
    """Decision policy whose first matching row comes from a ZEN JDM table."""

    PREDICATES = frozenset(
        {
            "customer_requested_human",
            "evidence_incomplete",
            "no_cause",
            "fraud_flag",
            "recent_sim_swap",
            "refund_velocity",
            "cause_conflict",
            "disclosed_term",
            "low_confidence",
            "staff_confidence",
            "above_one_tap_cap",
            "budget_exhausted",
            "auto_fix_disabled",
            "auto_fix",
            "auto_candidate_needs_tap",
            "customer_actions_disabled",
            "channel_cannot_confirm",
            "true",
        }
    )

    _HANDOFF: ClassVar[dict[str, HandoffReason]] = {
        "customer_requested_human": HandoffReason.CUSTOMER_REQUESTED,
        "evidence_incomplete": HandoffReason.EVIDENCE_INCOMPLETE,
        "no_cause": HandoffReason.NO_CAUSE_FOUND,
        "low_confidence": HandoffReason.LOW_CONFIDENCE,
    }

    def __init__(self, table: DecisionTable, thresholds: PolicyThresholds | None = None) -> None:
        self.table = table
        super().__init__(thresholds or PolicyThresholds(version=table.version))

    @classmethod
    def from_file(
        cls, path: Path, *, thresholds: PolicyThresholds | None = None
    ) -> ZenDecisionPolicy:
        return cls(DecisionTable.load(path), thresholds=thresholds)

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
        active = thresholds or self.thresholds
        flags = switches or SwitchState()
        row = next(
            row for row in self.table.rows if self._matches(row.row_id, case_input, active, flags)
        )
        handoff = self._HANDOFF.get(row.row_id)
        actions = [] if row.outcome is Outcome.HANDOFF else list(allowed_actions or [])
        return Decision(
            decision_id=new_id("DEC"),
            case_id=case_input.case_id,
            outcome=row.outcome,
            policy_version=self.table.version,
            input_hash=case_input.input_hash,
            allowed_actions=actions,
            amount_lkr=case_input.amount_lkr,
            top_cause_ref=case_input.top_cause_ref,
            ruled_out=list(ruled_out or []),
            handoff_reason=handoff,
            rationale=[f"ZEN decision table row: {row.row_id}"],
            config_snapshot_hash=config_snapshot_hash,
            as_of=case_input.as_of,
        )

    @staticmethod
    def _matches(
        row: str,
        value: DecisionInput,
        thresholds: PolicyThresholds,
        switches: SwitchState,
    ) -> bool:
        risk = value.risk
        amount = value.amount_lkr
        confidence = value.top_confidence
        predicates: dict[str, Any] = {
            "customer_requested_human": risk.customer_requested_human,
            "evidence_incomplete": not value.evidence_complete,
            "no_cause": value.top_cause_ref is None,
            "fraud_flag": risk.fraud_flag,
            "recent_sim_swap": (
                risk.sim_swap_days is not None
                and risk.sim_swap_days <= thresholds.sim_swap_window_days
            ),
            "refund_velocity": risk.refunds_last_30d > thresholds.repeat_refund_limit_30d,
            "cause_conflict": value.margin < thresholds.conflict_margin,
            "disclosed_term": value.disclosed_to_customer,
            "low_confidence": confidence < thresholds.staff_min_confidence,
            "staff_confidence": confidence < thresholds.one_tap_min_confidence,
            "above_one_tap_cap": amount > thresholds.one_tap_cap_lkr,
            "budget_exhausted": amount > 0 and not value.budget.allows(amount),
            "auto_fix_disabled": not switches.auto_fix_allowed and value.money_back_only,
            "auto_fix": (
                value.money_back_only
                and value.rule_auto_whitelisted
                and confidence >= thresholds.auto_min_confidence
                and amount <= thresholds.auto_cap_lkr
            ),
            "auto_candidate_needs_tap": (value.money_back_only and value.rule_auto_whitelisted),
            "customer_actions_disabled": not switches.customer_actions,
            "channel_cannot_confirm": not value.channel_supports_confirmation,
            "true": True,
        }
        return bool(predicates[row])


__all__ = [
    "DecisionTable",
    "DecisionTableInvalid",
    "DecisionTableRow",
    "ZenDecisionPolicy",
]
