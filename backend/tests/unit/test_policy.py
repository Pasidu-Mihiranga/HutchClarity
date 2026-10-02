"""Policy as governed, time-aware data (improvement plan Phase 1).

The question behind every test here is the one a regulator asks: *which rules
applied when this happened, and who agreed to them?*
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from clarity.contracts.decision import BudgetState, DecisionInput, Outcome, RiskSignals
from clarity.kernel.common import Channel, money
from clarity.modules.decision.policy import DecisionPolicy, PolicyThresholds
from clarity.modules.governance.governance import ChangeRefused, PolicyGovernance
from clarity.modules.governance.replay import ImpactReport, PolicyReplay, ReplayCase, cases_from
from clarity.platform.audit.ledger import AuditLedger
from clarity.platform.config.artefacts import (
    ChangeClass,
    Guardrail,
    PolicyKey,
    PolicyValue,
    Scope,
    Tag,
    class_for,
)
from clarity.platform.config.resolver import PolicyResolver, UnknownPolicyKey
from clarity.platform.config.switches import Switch, SwitchBoard, SwitchState, auto_fix_switch

JAN = datetime(2027, 1, 1, tzinfo=UTC)
APR = datetime(2027, 4, 15, tzinfo=UTC)
JUL = datetime(2027, 7, 1, tzinfo=UTC)


def a_key(**overrides) -> PolicyKey:
    defaults = {
        "key": "decision.auto_fix.cap_lkr",
        "tags": {Tag.MONEY},
        "guardrail": Guardrail(min=Decimal(0), max=Decimal(5000)),
        "values": [PolicyValue(value=money("1000.00"))],
    }
    return PolicyKey.model_validate(defaults | overrides)


# --------------------------------------------------------------------------- #
# Scope precedence
# --------------------------------------------------------------------------- #


def test_the_most_specific_scope_wins():
    resolver = PolicyResolver()
    resolver.add(
        a_key(
            values=[
                PolicyValue(value=money("1000.00")),
                PolicyValue(value=money("3500.00"), scope=Scope(rule="DUPLICATE_RELOAD")),
            ]
        )
    )

    general = resolver.resolve("decision.auto_fix.cap_lkr", as_of=APR, context={})
    scoped = resolver.resolve(
        "decision.auto_fix.cap_lkr", as_of=APR, context={"rule": "DUPLICATE_RELOAD"}
    )

    assert general == money("1000.00")
    assert scoped == money("3500.00")


def test_a_scope_that_does_not_match_is_ignored():
    resolver = PolicyResolver()
    resolver.add(
        a_key(
            values=[
                PolicyValue(value=money("1000.00")),
                PolicyValue(value=money("3500.00"), scope=Scope(rule="DUPLICATE_RELOAD")),
            ]
        )
    )

    assert resolver.resolve(
        "decision.auto_fix.cap_lkr", as_of=APR, context={"rule": "FUP_CAP_REACHED"}
    ) == money("1000.00")


def test_a_subscriber_scope_outranks_a_channel_scope():
    """Precedence is by dimension, not just by how many are pinned."""
    assert Scope(subscriber="sub_a").rank < Scope(channel="ussd").rank


# --------------------------------------------------------------------------- #
# Time
# --------------------------------------------------------------------------- #


def test_a_value_applies_only_inside_its_window():
    resolver = PolicyResolver()
    resolver.add(
        a_key(
            values=[
                PolicyValue(value=money("1000.00"), effective_to=APR),
                PolicyValue(value=money("2000.00"), effective_from=APR),
            ]
        )
    )

    assert resolver.resolve("decision.auto_fix.cap_lkr", as_of=JAN) == money("1000.00")
    assert resolver.resolve("decision.auto_fix.cap_lkr", as_of=JUL) == money("2000.00")


def test_a_charge_is_judged_by_the_rules_that_applied_then():
    """The regulator's question. A cap raised in April must not change a
    January decision when it is replayed today."""
    resolver = PolicyResolver()
    resolver.add(
        a_key(
            values=[
                PolicyValue(value=money("1000.00"), effective_to=APR),
                PolicyValue(value=money("5000.00"), effective_from=APR),
            ]
        )
    )

    january_charge = resolver.resolve("decision.auto_fix.cap_lkr", as_of=JAN)

    assert january_charge == money("1000.00"), "not today's cap"


def test_a_future_change_does_not_affect_today():
    resolver = PolicyResolver()
    resolver.add(
        a_key(
            values=[
                PolicyValue(value=money("1000.00"), effective_to=JUL),
                PolicyValue(value=money("4000.00"), effective_from=JUL),
            ]
        )
    )

    assert resolver.resolve("decision.auto_fix.cap_lkr", as_of=APR) == money("1000.00")


def test_overlapping_windows_for_one_scope_are_rejected():
    """Two values that could both apply is ambiguity, not a preference."""
    with pytest.raises(ValueError, match="overlapping"):
        a_key(values=[PolicyValue(value=money("1000")), PolicyValue(value=money("2000"))])


def test_a_window_must_be_ordered():
    with pytest.raises(ValueError, match="after"):
        PolicyValue(value=1, effective_from=JUL, effective_to=JAN)


# --------------------------------------------------------------------------- #
# Guardrails
# --------------------------------------------------------------------------- #


def test_a_value_above_its_guardrail_is_rejected():
    """A ceiling Finance set cannot be exceeded by an override."""
    with pytest.raises(ValueError, match="guardrail"):
        a_key(values=[PolicyValue(value=money("9000.00"))])


def test_a_value_inside_its_guardrail_is_accepted():
    assert a_key(values=[PolicyValue(value=money("4999.00"))]).values[0].value == money("4999.00")


def test_an_unknown_key_is_an_error_not_a_default():
    """A silently defaulted cap is how money leaks."""
    with pytest.raises(UnknownPolicyKey):
        PolicyResolver().resolve("decision.nonexistent", as_of=APR)


# --------------------------------------------------------------------------- #
# Snapshots and replay
# --------------------------------------------------------------------------- #


def test_a_snapshot_records_what_was_used_and_why():
    resolver = PolicyResolver()
    resolver.add(a_key(values=[PolicyValue(value=money("3500.00"), scope=Scope(rule="R"))]))

    snapshot = resolver.snapshot_for(
        ["decision.auto_fix.cap_lkr"], as_of=APR, context={"rule": "R"}
    )

    assert snapshot.get("decision.auto_fix.cap_lkr") == money("3500.00")
    assert "rule=R" in snapshot.explain()[0]


def test_the_snapshot_hash_is_stable_and_sensitive():
    resolver = PolicyResolver()
    resolver.add(a_key())

    first = resolver.snapshot_for(["decision.auto_fix.cap_lkr"], as_of=APR)
    again = resolver.snapshot_for(["decision.auto_fix.cap_lkr"], as_of=APR)
    later = resolver.snapshot_for(["decision.auto_fix.cap_lkr"], as_of=JUL)

    assert first.hash == again.hash
    assert first.hash != later.hash, "a different as_of is a different snapshot"


def test_a_candidate_supersedes_rather_than_collides(policies: PolicyResolver):
    """Publishing a new version closes the old one's window, never duplicates it."""
    proposed = policies.with_override(
        "decision.auto_fix.cap_lkr", PolicyValue(value=money("2000.00"), effective_from=JUL)
    )

    assert proposed.resolve("decision.auto_fix.cap_lkr", as_of=APR) == money("1000.00")
    assert proposed.resolve("decision.auto_fix.cap_lkr", as_of=JUL) == money("2000.00")


def test_a_preview_never_changes_the_live_resolver(policies: PolicyResolver):
    policies.with_override("decision.auto_fix.cap_lkr", PolicyValue(value=money("4000.00")))

    assert policies.resolve("decision.auto_fix.cap_lkr", as_of=APR) == money("1000.00")


def test_a_candidate_breaking_its_guardrail_is_refused(policies: PolicyResolver):
    with pytest.raises(ValueError, match="guardrail"):
        policies.with_override("decision.auto_fix.cap_lkr", PolicyValue(value=money("99000.00")))


# --------------------------------------------------------------------------- #
# Impact report
# --------------------------------------------------------------------------- #


def a_case(case_id: str, *, rule: str, amount: str, outcome: Outcome) -> ReplayCase:
    return ReplayCase(
        case_id=case_id,
        decision_input=DecisionInput(
            case_id=case_id,
            snapshot_hash="sha256:x",
            evidence_complete=True,
            top_cause_ref=f"{rule}@1",
            top_confidence=Decimal("0.97"),
            margin=Decimal("1.0"),
            amount_lkr=money(amount),
            money_back_only=True,
            rule_auto_whitelisted=True,
            risk=RiskSignals(),
            budget=BudgetState(global_remaining_lkr=money("1000000")),
            as_of=APR,
        ),
        rule_id=rule,
        outcome=outcome,
        amount_lkr=money(amount),
    )


@pytest.fixture
def replay(policies: PolicyResolver) -> PolicyReplay:
    return PolicyReplay(DecisionPolicy(), policies)


def test_lowering_a_cap_shows_what_stops_being_automatic(replay: PolicyReplay):
    cases = [a_case("C1", rule="DUPLICATE_RELOAD", amount="3500.00", outcome=Outcome.AUTO_FIX)]

    report = replay.preview(
        "decision.auto_fix.cap_lkr",
        PolicyValue(value=money("500.00"), scope=Scope(rule="DUPLICATE_RELOAD")),
        cases,
    )

    assert report.changed == 1
    assert report.money_delta_lkr == Decimal("-3500.00"), "less money moves unattended"
    assert report.transitions == {"AUTO_FIX -> ONE_TAP_FIX": 1}


def test_a_change_with_no_effect_says_so(replay: PolicyReplay):
    """A cap on one rule must not disturb a case decided by another."""
    cases = [a_case("C1", rule="DUPLICATE_VAS_CHARGE", amount="49.00", outcome=Outcome.AUTO_FIX)]

    report = replay.preview(
        "decision.auto_fix.cap_lkr",
        PolicyValue(value=money("4000.00"), scope=Scope(rule="DUPLICATE_RELOAD")),
        cases,
    )

    assert report.changed == 0
    assert "No case" in report.headline()


def test_the_report_names_the_change_class(replay: PolicyReplay):
    report = replay.preview("decision.auto_fix.cap_lkr", PolicyValue(value=money("2000.00")), [])

    assert report.change_class is ChangeClass.C3_MONEY_AFFECTING


def test_a_case_without_a_recorded_input_is_skipped_not_guessed():
    """A replay that invents its inputs proves nothing."""
    assert cases_from([object()]) == []


# --------------------------------------------------------------------------- #
# Change classes and approval
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("tags", "expected"),
    [
        ({Tag.MONEY}, ChangeClass.C3_MONEY_AFFECTING),
        ({Tag.REGULATORY}, ChangeClass.C4_REGULATORY),
        ({Tag.OUTCOME}, ChangeClass.C2_OUTCOME_AFFECTING),
        ({Tag.CUSTOMER_VISIBLE}, ChangeClass.C1_CUSTOMER_VISIBLE),
        (set(), ChangeClass.C0_COSMETIC),
    ],
)
def test_the_class_follows_what_the_change_touches(tags, expected):
    assert class_for(tags) is expected


def test_a_money_change_needs_two_approvers():
    governance = PolicyGovernance()
    change = governance.draft(
        key="decision.auto_fix.cap_lkr",
        candidate=PolicyValue(value=money("2000.00")),
        computed_class=ChangeClass.C3_MONEY_AFFECTING,
        maker_ref="cx-1",
        reason="Avurudu campaign",
    )
    governance.attach_impact(change.change_id, ImpactReport("k", change.change_class, 0))

    governance.approve(change.change_id, approver_ref="fin-1", role="finance")
    with pytest.raises(ChangeRefused, match="needs 2 approvals"):
        governance.activate(change.change_id)

    governance.approve(change.change_id, approver_ref="risk-1", role="risk")
    assert governance.activate(change.change_id).state.value == "active"


def test_the_maker_cannot_approve_their_own_change():
    governance = PolicyGovernance()
    change = governance.draft(
        key="decision.auto_fix.cap_lkr",
        candidate=PolicyValue(value=money("2000.00")),
        computed_class=ChangeClass.C3_MONEY_AFFECTING,
        maker_ref="cx-1",
        reason="test",
    )

    with pytest.raises(ChangeRefused, match="cannot approve"):
        governance.approve(change.change_id, approver_ref="cx-1", role="cx_engineer")


def test_a_money_change_cannot_be_approved_without_an_impact_report():
    """Plan §19: no money-affecting change without evidence of its impact."""
    governance = PolicyGovernance()
    change = governance.draft(
        key="decision.auto_fix.cap_lkr",
        candidate=PolicyValue(value=money("2000.00")),
        computed_class=ChangeClass.C3_MONEY_AFFECTING,
        maker_ref="cx-1",
        reason="test",
    )

    with pytest.raises(ChangeRefused, match="impact report"):
        governance.approve(change.change_id, approver_ref="fin-1", role="finance")


def test_a_class_cannot_be_lowered_to_dodge_an_approver():
    governance = PolicyGovernance()

    with pytest.raises(ChangeRefused, match="cannot be lowered"):
        governance.draft(
            key="decision.auto_fix.cap_lkr",
            candidate=PolicyValue(value=money("2000.00")),
            computed_class=ChangeClass.C3_MONEY_AFFECTING,
            maker_ref="cx-1",
            reason="test",
            raise_to=ChangeClass.C0_COSMETIC,
        )


def test_a_change_must_record_why():
    governance = PolicyGovernance()

    with pytest.raises(ChangeRefused, match="why"):
        governance.draft(
            key="k",
            candidate=PolicyValue(value=1),
            computed_class=ChangeClass.C0_COSMETIC,
            maker_ref="cx-1",
            reason="   ",
        )


def test_activating_a_change_is_audited():
    ledger = AuditLedger()
    governance = PolicyGovernance(audit=ledger)
    change = governance.draft(
        key="decision.conflict_margin",
        candidate=PolicyValue(value="0.25"),
        computed_class=ChangeClass.C2_OUTCOME_AFFECTING,
        maker_ref="cx-1",
        reason="fewer conflicts",
    )
    governance.attach_impact(change.change_id, ImpactReport("k", change.change_class, 0))
    governance.approve(change.change_id, approver_ref="cx-lead", role="cx_lead")

    governance.activate(change.change_id)

    assert len(ledger) == 1
    assert ledger.verify().intact


# --------------------------------------------------------------------------- #
# Kill switches
# --------------------------------------------------------------------------- #


def test_everything_is_on_until_someone_turns_it_off():
    board = SwitchBoard()

    assert board.is_on(Switch.AUTO_FIX_GLOBAL)
    assert board.auto_fix_allowed("DUPLICATE_RELOAD")


def test_a_global_switch_stops_every_rule():
    board = SwitchBoard()

    board.turn_off(Switch.AUTO_FIX_GLOBAL, actor_ref="sup-1", reason="refund anomaly")

    assert not board.auto_fix_allowed("DUPLICATE_RELOAD")
    assert not board.auto_fix_allowed(None)


def test_a_rule_switch_stops_only_that_rule():
    board = SwitchBoard()

    board.turn_off(auto_fix_switch("DUPLICATE_RELOAD"), actor_ref="sup-1", reason="misfiring")

    assert not board.auto_fix_allowed("DUPLICATE_RELOAD")
    assert board.auto_fix_allowed("DUPLICATE_VAS_CHARGE")


def test_a_switch_can_be_turned_back_on():
    board = SwitchBoard()
    board.turn_off(Switch.AUTO_FIX_GLOBAL, actor_ref="sup-1", reason="incident")

    board.turn_on(Switch.AUTO_FIX_GLOBAL, actor_ref="sup-1", reason="fixed")

    assert board.is_on(Switch.AUTO_FIX_GLOBAL)
    assert len(board.history) == 2


def test_a_flip_must_record_why():
    with pytest.raises(ValueError, match="why"):
        SwitchBoard().turn_off(Switch.AUTO_FIX_GLOBAL, actor_ref="sup-1", reason="")


def test_every_flip_is_audited():
    """'Who turned this off' is the first question after an incident."""
    ledger = AuditLedger()
    board = SwitchBoard(audit_sink=ledger)

    board.turn_off(Switch.AUTO_FIX_GLOBAL, actor_ref="sup-1", reason="refund spike")

    assert len(ledger) == 1
    assert ledger.records[0].actor_ref == "sup-1"


def test_switching_auto_fix_off_degrades_to_staff_not_to_nothing():
    """The switch must not break the journey, only slow it down."""
    policy = DecisionPolicy(PolicyThresholds(auto_cap_lkr=money("5000.00")))
    case_input = DecisionInput(
        case_id="C",
        snapshot_hash="sha256:x",
        evidence_complete=True,
        top_cause_ref="DUPLICATE_RELOAD@2",
        top_confidence=Decimal("0.97"),
        margin=Decimal("1.0"),
        amount_lkr=money("3500.00"),
        money_back_only=True,
        rule_auto_whitelisted=True,
        risk=RiskSignals(),
        budget=BudgetState(global_remaining_lkr=money("100000")),
    )

    on = policy.decide(case_input, switches=SwitchState())
    off = policy.decide(case_input, switches=SwitchState(auto_fix_global=False))

    assert on.outcome is Outcome.AUTO_FIX
    assert off.outcome is Outcome.STAFF_APPROVAL, "a person decides, nothing breaks"
    assert any("switched off" in line for line in off.rationale)


def test_switching_customer_actions_off_routes_to_staff():
    policy = DecisionPolicy()
    case_input = DecisionInput(
        case_id="C",
        snapshot_hash="sha256:x",
        evidence_complete=True,
        top_cause_ref="VAS_NO_CONSENT@4",
        top_confidence=Decimal("0.96"),
        margin=Decimal("1.0"),
        amount_lkr=money("49.00"),
        money_back_only=False,
        rule_auto_whitelisted=False,
        risk=RiskSignals(),
        budget=BudgetState(global_remaining_lkr=money("100000")),
    )

    decision = policy.decide(case_input, switches=SwitchState(customer_actions=False))

    assert decision.outcome is Outcome.STAFF_APPROVAL


# --------------------------------------------------------------------------- #
# End to end through the case service
# --------------------------------------------------------------------------- #


def test_a_decision_records_the_policy_it_used(clarity_container):
    """Without this, a replay silently uses today's thresholds."""
    from clarity.integration.drivers.mock.world import ref_for

    clarity = clarity_container
    account = clarity.world.account(ref_for("+94772223333"))
    case = clarity.cases.open_case(
        subscriber_ref=account.ref, msisdn_masked=account.masked, channel=Channel.APP
    )

    decision = clarity.cases.evaluate(case.case_id)

    assert decision.config_snapshot_hash, "the resolved values must be recorded"
    assert decision.as_of is not None, "and the moment they were resolved for"
    assert decision.as_of < clarity.cases._now(), "as_of is the charge, not now"


def test_the_rule_scoped_cap_is_what_makes_the_deck_example_work(clarity_container):
    """LKR 3,500 auto-fixes for DUPLICATE_RELOAD and only for it."""
    from clarity.integration.drivers.mock.world import ref_for

    clarity = clarity_container
    account = clarity.world.account(ref_for("+94772223333"))
    case = clarity.cases.open_case(
        subscriber_ref=account.ref, msisdn_masked=account.masked, channel=Channel.APP
    )

    decision = clarity.cases.evaluate(case.case_id)

    assert decision.outcome is Outcome.AUTO_FIX
    assert decision.amount_lkr == Decimal("3500.00")
    assert clarity.policies.resolve(
        "decision.auto_fix.cap_lkr", as_of=decision.as_of, context={}
    ) == money("1000.00"), "the global cap stayed low"


def test_pulling_the_rule_switch_stops_that_auto_fix_end_to_end(clarity_container):
    from clarity.integration.drivers.mock.world import ref_for

    clarity = clarity_container
    clarity.switches.turn_off(
        auto_fix_switch("DUPLICATE_RELOAD"), actor_ref="sup-1", reason="refund anomaly"
    )
    account = clarity.world.account(ref_for("+94772223333"))
    case = clarity.cases.open_case(
        subscriber_ref=account.ref, msisdn_masked=account.masked, channel=Channel.APP
    )

    decision = clarity.cases.evaluate(case.case_id)

    assert decision.outcome is Outcome.STAFF_APPROVAL
