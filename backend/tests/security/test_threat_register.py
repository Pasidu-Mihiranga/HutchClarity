"""Every threat in the register is either tested or deliberately out of scope (X01).

The threat register lives in plan 11 and currently names nineteen threats. The
scope for this issue is "tests for each mitigable threat", which is only a
checkable claim if something compares the two lists. So this file parses the
register out of the plan and requires every TH id to appear in exactly one of:

- :data:`MITIGATED`, naming a test that demonstrates the mitigation, or
- :data:`NOT_MITIGABLE_HERE`, with the reason it cannot be shown in this
  repository.

The second map is the honest half. A prototype cannot demonstrate a WAF, a key
rotation schedule or a WORM archive, and writing a test that pretends otherwise
would be worse than having no test: it would report coverage that does not
exist. This is the same shape as an `UNEVALUABLE` evaluation gate.

Adding a threat to the plan without deciding which half it belongs in fails
these tests, which is the point.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT.parent / "docs" / "enterprise-plan" / "11-security-privacy-audit.md"
TESTS = ROOT / "tests"

#: TH id -> (test file relative to backend/tests, test function).
#: One test per threat, chosen as the one that fails if the mitigation is
#: removed. Several threats have far more coverage than the single test named.
MITIGATED: dict[str, tuple[str, str]] = {
    "TH1": ("unit/test_iam.py", "test_requests_are_rate_limited_per_number"),
    "TH2": ("unit/test_tool_layer.py", "test_budget_blocks_execution_it_cannot_cover"),
    "TH3": ("unit/test_agent_step.py", "test_a_plan_carrying_an_amount_is_rejected"),
    "TH4": ("unit/test_log_masking.py", "test_a_log_line_with_an_msisdn_is_masked"),
    "TH5": (
        "security/test_th05_replay.py",
        "test_a_captured_confirmation_token_cannot_be_redeemed_twice",
    ),
    "TH6": (
        "unit/test_migration_defects.py",
        "test_d1_fifteen_hundred_concurrent_confirms_give_one_refund_and_one_receipt",
    ),
    "TH7": ("unit/test_tool_layer.py", "test_the_maker_cannot_approve_their_own_plan"),
    "TH8": ("unit/test_mcp.py", "test_a_tool_outside_the_profile_is_denied"),
    "TH10": ("unit/test_receipts.py", "test_a_tampered_amount_fails_verification"),
    "TH13": ("unit/test_deskops.py", "test_a_merchant_score_shows_what_it_was_counted_from"),
    "TH14": ("unit/test_mcp.py", "test_an_unknown_tool_is_denied"),
    "TH15": ("unit/test_mcp_network.py", "test_a_token_for_another_audience_is_refused"),
    "TH16": ("unit/test_ai.py", "test_customer_text_is_masked_before_it_reaches_a_provider"),
    "TH17": ("unit/test_policy.py", "test_the_maker_cannot_approve_their_own_change"),
    "TH18": (
        "unit/test_receipts_consumer.py",
        "test_action_completed_delivered_twice_issues_one_receipt",
    ),
    "TH19": (
        "acceptance/test_route_contract.py",
        "test_synthetic_only_routes_do_not_exist_in_production",
    ),
}

#: TH id -> why this repository cannot demonstrate the mitigation.
#: Each of these is a real control that belongs to a deployment, not to code.
NOT_MITIGABLE_HERE: dict[str, str] = {
    "TH9": (
        "Compromised API keys. The mitigations are short-lived credentials, "
        "OpenBao dynamic secrets, egress allowlists and rotation. The signing "
        "key rotation half is covered by the port parity suite, but a leaked "
        "provider key is detected by upstream anomaly alerting that does not "
        "exist here. REQUIRES HUTCH CONFIRMATION of the key management service."
    ),
    "TH11": (
        "Insider tampering with the audit trail. The hash chain is built and "
        "tested (test_receipts_chain_to_their_predecessor), but the mitigation "
        "that matters against a database administrator is the WORM anchor and "
        "the SIEM copy, which are external systems. A test here would only "
        "re-check the chain and would overstate the coverage."
    ),
    "TH12": (
        "Denial of service. OTP rate limiting and AI token budgets exist and "
        "are tested, but the mitigations for a flood are a WAF, edge rate "
        "limits and queue back-pressure, which are deployment concerns. Load "
        "and chaos testing is issue #43 (X02), not this one."
    ),
}

_TH_ROW = re.compile(r"^\|\s*(TH\d+)\s*\|", re.MULTILINE)


def registered() -> list[str]:
    """Every TH id the plan's register declares."""
    assert REGISTER.exists(), f"the threat register moved: {REGISTER}"
    found = _TH_ROW.findall(REGISTER.read_text(encoding="utf-8"))
    assert found, "no threats parsed; the register's table format changed"
    return found


def test_the_register_parses() -> None:
    threats = registered()

    assert len(threats) == len(set(threats)), "a TH id is listed twice"
    assert len(threats) >= 19, f"only {len(threats)} threats parsed, expected the full register"


@pytest.mark.parametrize("threat", registered())
def test_every_threat_is_either_tested_or_explicitly_out_of_scope(threat: str) -> None:
    tested = threat in MITIGATED
    excused = threat in NOT_MITIGABLE_HERE

    assert tested or excused, (
        f"{threat} is in the plan's register and in neither map. Add a test to "
        "MITIGATED, or record in NOT_MITIGABLE_HERE why this repository cannot "
        "show the mitigation."
    )
    assert not (tested and excused), f"{threat} is claimed as both tested and out of scope"


@pytest.mark.parametrize(("threat", "location"), sorted(MITIGATED.items()))
def test_the_named_test_for_a_threat_exists(threat: str, location: tuple[str, str]) -> None:
    """A map entry pointing at a renamed test is a coverage claim with nothing behind it."""
    relative, name = location
    path = TESTS / relative

    assert path.exists(), f"{threat} names a file that does not exist: {relative}"
    assert f"def {name}(" in path.read_text(encoding="utf-8"), (
        f"{threat} names {name} in {relative}, which no longer defines it"
    )


@pytest.mark.parametrize(("threat", "reason"), sorted(NOT_MITIGABLE_HERE.items()))
def test_an_out_of_scope_threat_says_why(threat: str, reason: str) -> None:
    """An exclusion is a decision, so it carries a justification rather than a name."""
    assert len(reason.split()) >= 15, f"{threat} is excused without a real reason"


def test_no_map_entry_refers_to_a_threat_the_plan_dropped() -> None:
    """A test for a threat nobody tracks any more is a test nobody reads."""
    threats = set(registered())
    claimed = set(MITIGATED) | set(NOT_MITIGABLE_HERE)

    dropped = sorted(claimed - threats)

    assert not dropped, f"these are not in the register any more: {dropped}"
