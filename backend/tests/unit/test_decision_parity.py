"""Python and ZEN outcome policies stay identical through the cutover."""

from __future__ import annotations

import random
from decimal import Decimal
from pathlib import Path

import pytest

from clarity.contracts.decision import BudgetState, DecisionInput, RiskSignals
from clarity.kernel.common import money
from clarity.modules.decision.public import (
    DecisionPolicy,
    PolicyThresholds,
    ZenDecisionPolicy,
)
from clarity.platform.config.switches import SwitchState
from tests.unit.test_decision_policy import an_input

TABLE = Path(__file__).resolve().parents[3] / "config" / "policy" / "decision-table.json"
THRESHOLDS = PolicyThresholds(auto_cap_lkr=money("3500.00"), one_tap_cap_lkr=money("10000.00"))


@pytest.mark.parametrize(
    "case_input",
    [
        an_input(),
        an_input(evidence_complete=False),
        an_input(top_cause_ref=None, top_confidence=Decimal("0")),
        an_input(risk=RiskSignals(customer_requested_human=True)),
        an_input(risk=RiskSignals(fraud_flag=True)),
        an_input(risk=RiskSignals(sim_swap_days=7)),
        an_input(margin=Decimal("0.01")),
        an_input(disclosed_to_customer=True),
        an_input(top_confidence=Decimal("0.60")),
        an_input(top_confidence=Decimal("0.85")),
        an_input(amount_lkr=money("12000.00")),
        an_input(budget=BudgetState(global_remaining_lkr=money("1.00"))),
        an_input(money_back_only=False, rule_auto_whitelisted=False),
        an_input(channel_supports_confirmation=False),
    ],
)
def test_canonical_decision_cases_match(case_input: DecisionInput):
    python = DecisionPolicy(THRESHOLDS)
    zen = ZenDecisionPolicy.from_file(TABLE, thresholds=THRESHOLDS)
    assert zen.decide(case_input).outcome is python.decide(case_input).outcome


def test_one_thousand_generated_inputs_match_exactly():
    rng = random.Random(20271002)
    python = DecisionPolicy(THRESHOLDS)
    zen = ZenDecisionPolicy.from_file(TABLE, thresholds=THRESHOLDS)
    for index in range(1000):
        amount = money(str(rng.randrange(0, 500000) / 100))
        budget = money(str(rng.randrange(0, 500000) / 100))
        value = DecisionInput(
            case_id=f"CASE-{index}",
            snapshot_hash=f"sha256:{index}",
            evidence_complete=rng.choice([True, False]),
            top_cause_ref=rng.choice(["RULE@1", None]),
            top_confidence=Decimal(rng.randrange(0, 101)) / Decimal("100"),
            margin=Decimal(rng.randrange(0, 101)) / Decimal("100"),
            amount_lkr=amount,
            money_back_only=rng.choice([True, False]),
            rule_auto_whitelisted=rng.choice([True, False]),
            disclosed_to_customer=rng.choice([True, False]),
            risk=RiskSignals(
                sim_swap_days=rng.choice([None, 0, 2, 7, 8, 30]),
                fraud_flag=rng.choice([True, False]),
                refunds_last_30d=rng.randrange(0, 8),
                customer_requested_human=rng.choice([True, False]),
            ),
            budget=BudgetState(global_remaining_lkr=budget),
            channel_supports_confirmation=rng.choice([True, False]),
        )
        switches = SwitchState(
            auto_fix_global=rng.choice([True, False]),
            customer_actions=rng.choice([True, False]),
            rule_auto_fix=rng.choice([True, False]),
        )
        before = python.decide(value, switches=switches).outcome
        after = zen.decide(value, switches=switches).outcome
        assert after is before, f"generated input {index} diverged"
