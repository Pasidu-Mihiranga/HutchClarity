"""Detection, alerts, liveness and the playbook (audit assurance Phase 4, ADR-0037).

The plan's four acceptance tests are the first four here, named so. The rest
cover the lifecycle and the rules that are cheap to get subtly wrong.

Every rule is counted from the trail, so each test builds the trail the way the
system would and then asks what detection sees.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from clarity.modules.assurance.public import (
    CHAIN_BREAK,
    DETECTOR_SILENT,
    Alert,
    AlertRefused,
    AlertState,
    AssuranceService,
    Band,
    Disposition,
)
from clarity.platform.audit.ledger import AuditEventType, AuditLedger
from clarity.platform.config.switches import Switch, SwitchBoard
from clarity.platform.persistence.memory import MemoryStore, MemoryUnitOfWork
from clarity.platform.security.principal import Assurance, Permission, Principal, Role

#: The thresholds the rules read, as the policy store serves them.
POLICY: dict[str, object] = {
    "decision.four_eyes.threshold_lkr": "10000.00",
    "assurance.structuring.near_cap_fraction": "0.9",
    "assurance.structuring.min_count": "5",
    "assurance.structuring.window": "PT1H",
    "assurance.receipt.grace": "PT15M",
    "assurance.switch_then_pay.window": "PT6H",
    "assurance.otp_failures.window": "PT15M",
    "assurance.otp_failures.min_count": "10",
    "assurance.denials.window": "PT15M",
    "assurance.denials.min_count": "10",
    "assurance.audit_reads.window": "PT1H",
    "assurance.audit_reads.min_count": "50",
    "assurance.alert.ack_sla": "PT4H",
    "assurance.liveness.max_silence": "PT30M",
    "assurance.checkpoint.max_gap": "PT1H",
    "assurance.detection.interval": "PT5M",
}


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 10, 4, 9, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, by: timedelta) -> None:
        self.now += by


class Verification:
    """Stands in for the checkpoint verification the container passes in."""

    def __init__(self) -> None:
        self.intact = True
        self.reason: str | None = None
        self.broken_at: int | None = None
        self.last_checkpoint_seq: int | None = 1

    def __call__(self) -> Verification:
        return self


def staff(ref: str, *roles: Role, dispose: bool = True) -> Principal:
    """A principal holding alert:dispose through a grant, as Phase 3 gives it."""
    return Principal(
        ref=ref,
        roles=frozenset(roles or (Role.COMPLIANCE,)),
        assurance=Assurance.MFA_RECENT,
        granted=frozenset({Permission.ALERT_DISPOSE}) if dispose else frozenset(),
    )


ALICE = staff("comp:alice")
BOB = staff("comp:bob")


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def ledger(clock: Clock) -> AuditLedger:
    return AuditLedger(clock=clock)


@pytest.fixture
def switches(ledger: AuditLedger) -> SwitchBoard:
    return SwitchBoard(audit_sink=ledger)


@pytest.fixture
def verification() -> Verification:
    return Verification()


@pytest.fixture
def assurance(
    clock: Clock, ledger: AuditLedger, switches: SwitchBoard, verification: Verification
) -> AssuranceService:
    store = MemoryStore()
    return AssuranceService(
        lambda: MemoryUnitOfWork(store),
        audit=ledger,
        switches=switches,
        verify=verification,
        resolve=lambda key, as_of: POLICY[key],
        clock=clock,
    )


def approve_and_execute(ledger: AuditLedger, *, case_id: str, actor: str, amount: str) -> None:
    """One approved, executed refund, as the trail records it."""
    ledger.append(
        AuditEventType.REQUEST_PERFORMED,
        actor_ref=actor,
        object_ref="POST /v1/cases/{case_id}/approve",
        payload={},
        case_id=case_id,
        detail={"status": 200},
    )
    ledger.append(
        AuditEventType.ACTION_EXECUTED,
        actor_ref="clarity",
        object_ref=f"plan:{case_id}",
        payload={},
        case_id=case_id,
        detail={"total_amount_lkr": amount},
    )
    ledger.append(
        AuditEventType.RECEIPT_ISSUED,
        actor_ref="clarity",
        object_ref=f"TR-{case_id}",
        payload={},
        case_id=case_id,
        detail={},
    )


def alerts_by_rule(service: AssuranceService, rule_id: str) -> list[Alert]:
    return [alert for alert in service.alerts() if alert.rule_id == rule_id]


# --------------------------------------------------------------------------- #
# The plan's four acceptance tests
# --------------------------------------------------------------------------- #


def test_acceptance_1_five_refunds_under_the_cap_raise_a_high_alert_citing_them(
    assurance: AssuranceService, ledger: AuditLedger
):
    """Given five refunds just under the cap by one actor, when detection runs,
    then a high alert cites those five records."""
    for index in range(5):
        approve_and_execute(ledger, case_id=f"CASE-{index}", actor="sup:ruwan", amount="9800.00")
    # A sixth, by someone else and well under the cap: not part of the pattern.
    approve_and_execute(ledger, case_id="CASE-X", actor="sup:other", amount="100.00")

    assurance.run()

    raised = alerts_by_rule(assurance, "structuring")
    assert len(raised) == 1
    alert = raised[0]
    assert alert.band is Band.HIGH
    assert alert.subject_ref == "sup:ruwan"
    executions = [
        record.seq
        for record in ledger.records
        if record.event_type is AuditEventType.ACTION_EXECUTED and record.case_id != "CASE-X"
    ]
    assert set(executions) <= set(alert.evidence), "the alert cites the refunds it counted"
    assert len(alert.evidence) == 10, "each refund's approval and execution"


def test_acceptance_2_a_chain_break_stops_money_and_raises_a_critical_alert(
    assurance: AssuranceService, switches: SwitchBoard, verification: Verification
):
    """Given a chain break, when it is detected, then `auto_fix_global` is off
    and a critical alert exists."""
    verification.intact = False
    verification.reason = "record hash does not match its contents"
    verification.broken_at = 7
    assert switches.is_on(Switch.AUTO_FIX_GLOBAL)

    assurance.run()

    assert switches.is_off(Switch.AUTO_FIX_GLOBAL)
    assert switches.is_off(Switch.CUSTOMER_ACTIONS)
    alert = alerts_by_rule(assurance, CHAIN_BREAK)[0]
    assert alert.band is Band.CRITICAL
    assert "seq 7" in alert.summary


def test_acceptance_3_detection_going_silent_raises_a_critical_alert(
    assurance: AssuranceService, clock: Clock
):
    """Given detection stopped, when the interval passes, then a critical
    liveness alert."""
    assurance.run()
    assert assurance.check_liveness() is None, "just ran, nothing to say"

    clock.advance(timedelta(minutes=31))
    alert = assurance.check_liveness()

    assert alert is not None
    assert alert.rule_id == DETECTOR_SILENT
    assert alert.band is Band.CRITICAL


def test_acceptance_4_the_subject_of_an_alert_cannot_dispose_of_it(
    assurance: AssuranceService, ledger: AuditLedger
):
    """Given a high alert, when its subject tries to dispose of it, then refused."""
    for index in range(5):
        approve_and_execute(ledger, case_id=f"CASE-{index}", actor="comp:alice", amount="9800.00")
    assurance.run()
    alert = alerts_by_rule(assurance, "structuring")[0]
    assert alert.subject_ref == "comp:alice"

    with pytest.raises(AlertRefused) as refused:
        assurance.acknowledge(ALICE, alert.alert_id)

    assert refused.value.code == "SELF_DISPOSAL"


# --------------------------------------------------------------------------- #
# The lifecycle
# --------------------------------------------------------------------------- #


def raise_one(
    assurance: AssuranceService, ledger: AuditLedger, *, actor: str = "sup:ruwan"
) -> Alert:
    for index in range(5):
        approve_and_execute(ledger, case_id=f"CASE-{index}", actor=actor, amount="9800.00")
    assurance.run()
    return alerts_by_rule(assurance, "structuring")[0]


def test_an_alert_moves_through_its_lifecycle_and_every_step_is_recorded(
    assurance: AssuranceService, ledger: AuditLedger
):
    alert = raise_one(assurance, ledger)

    assurance.acknowledge(ALICE, alert.alert_id)
    assurance.investigate(ALICE, alert.alert_id)
    closed = assurance.dispose(
        BOB, alert.alert_id, disposition=Disposition.CONFIRMED, reason="split payouts, escalated"
    )

    assert closed.state is AlertState.DISPOSED
    assert closed.disposition is Disposition.CONFIRMED
    assert closed.disposition_reason == "split payouts, escalated"
    steps = [r.event_type for r in ledger.records if r.object_ref == alert.alert_id]
    assert steps == [
        AuditEventType.ALERT_RAISED,
        AuditEventType.ALERT_ACKNOWLEDGED,
        AuditEventType.ALERT_INVESTIGATING,
        AuditEventType.ALERT_DISPOSED,
    ]
    assert ledger.verify().intact


def test_a_high_alert_needs_a_second_person_to_close(
    assurance: AssuranceService, ledger: AuditLedger
):
    alert = raise_one(assurance, ledger)
    assurance.acknowledge(ALICE, alert.alert_id)
    assurance.investigate(ALICE, alert.alert_id)

    with pytest.raises(AlertRefused) as refused:
        assurance.dispose(
            ALICE, alert.alert_id, disposition=Disposition.FALSE_POSITIVE, reason="mine to close"
        )

    assert refused.value.code == "SECOND_PERSON"


def test_disposing_needs_the_permission(assurance: AssuranceService, ledger: AuditLedger):
    alert = raise_one(assurance, ledger)

    with pytest.raises(AlertRefused) as refused:
        assurance.acknowledge(staff("agent:nadeesha", Role.AGENT, dispose=False), alert.alert_id)

    assert refused.value.code == "NOT_PERMITTED"


def test_a_disposition_always_carries_a_reason(assurance: AssuranceService, ledger: AuditLedger):
    alert = raise_one(assurance, ledger)
    assurance.acknowledge(ALICE, alert.alert_id)

    with pytest.raises(AlertRefused) as refused:
        assurance.dispose(BOB, alert.alert_id, disposition=Disposition.CONFIRMED, reason="  ")

    assert refused.value.code == "REASON_REQUIRED"


def test_an_alert_cannot_be_closed_before_it_is_acknowledged(
    assurance: AssuranceService, ledger: AuditLedger
):
    alert = raise_one(assurance, ledger)

    with pytest.raises(AlertRefused) as refused:
        assurance.dispose(BOB, alert.alert_id, disposition=Disposition.CONFIRMED, reason="r")

    assert refused.value.code == "NOT_ACKNOWLEDGED"


def test_the_same_finding_again_is_one_alert_not_two(
    assurance: AssuranceService, ledger: AuditLedger
):
    """A noisy rule must not bury the quiet one next to it."""
    raise_one(assurance, ledger)
    approve_and_execute(ledger, case_id="CASE-6", actor="sup:ruwan", amount="9900.00")

    assurance.run()

    raised = alerts_by_rule(assurance, "structuring")
    assert len(raised) == 1
    assert raised[0].occurrences == 2
    assert len(raised[0].evidence) == 12, "the new records joined the same alert"


def test_a_closed_alert_does_not_suppress_the_next_one(
    assurance: AssuranceService, ledger: AuditLedger
):
    alert = raise_one(assurance, ledger)
    assurance.acknowledge(ALICE, alert.alert_id)
    assurance.dispose(BOB, alert.alert_id, disposition=Disposition.CONFIRMED, reason="handled")

    approve_and_execute(ledger, case_id="CASE-7", actor="sup:ruwan", amount="9900.00")
    assurance.run()

    assert len(alerts_by_rule(assurance, "structuring")) == 2


def test_an_unacknowledged_alert_escalates_once(
    assurance: AssuranceService, ledger: AuditLedger, clock: Clock
):
    alert = raise_one(assurance, ledger)
    clock.advance(timedelta(hours=5))

    assurance.run()
    assurance.run()

    escalated = assurance.alert(alert.alert_id)
    assert escalated.escalated_at is not None
    events = [r for r in ledger.records if r.event_type is AuditEventType.ALERT_ESCALATED]
    assert len(events) == 1, "escalated once, not on every run"


# --------------------------------------------------------------------------- #
# Rules and integrity
# --------------------------------------------------------------------------- #


def test_four_refunds_under_the_cap_are_not_a_finding(
    assurance: AssuranceService, ledger: AuditLedger
):
    """The threshold is the threshold: one below it says nothing."""
    for index in range(4):
        approve_and_execute(ledger, case_id=f"CASE-{index}", actor="sup:ruwan", amount="9800.00")

    assurance.run()

    assert alerts_by_rule(assurance, "structuring") == []


def test_refunds_well_under_the_cap_are_not_structuring(
    assurance: AssuranceService, ledger: AuditLedger
):
    """Ordinary small refunds are the system working, not a pattern."""
    for index in range(8):
        approve_and_execute(ledger, case_id=f"CASE-{index}", actor="sup:ruwan", amount="500.00")

    assurance.run()

    assert alerts_by_rule(assurance, "structuring") == []


def test_refunds_outside_the_window_are_not_counted_together(
    assurance: AssuranceService, ledger: AuditLedger, clock: Clock
):
    for index in range(3):
        approve_and_execute(ledger, case_id=f"CASE-{index}", actor="sup:ruwan", amount="9800.00")
    clock.advance(timedelta(hours=2))
    for index in range(3, 6):
        approve_and_execute(ledger, case_id=f"CASE-{index}", actor="sup:ruwan", amount="9800.00")

    assurance.run()

    assert alerts_by_rule(assurance, "structuring") == []


def test_self_approval_is_a_high_finding(assurance: AssuranceService, ledger: AuditLedger):
    for route in ("proposals", "approve"):
        ledger.append(
            AuditEventType.REQUEST_PERFORMED,
            actor_ref="sup:ruwan",
            object_ref=f"POST /v1/cases/{{case_id}}/{route}",
            payload={},
            case_id="CASE-1",
            detail={"status": 200},
        )

    assurance.run()

    alert = alerts_by_rule(assurance, "self_approval")[0]
    assert alert.band is Band.HIGH
    assert alert.subject_ref == "sup:ruwan"


def test_money_without_a_receipt_is_a_finding_after_the_grace(
    assurance: AssuranceService, ledger: AuditLedger, clock: Clock
):
    ledger.append(
        AuditEventType.ACTION_EXECUTED,
        actor_ref="clarity",
        object_ref="plan:1",
        payload={},
        case_id="CASE-1",
        detail={"total_amount_lkr": "500.00"},
    )

    assurance.run()
    assert alerts_by_rule(assurance, "money_without_proof") == [], "still inside the grace"

    clock.advance(timedelta(minutes=16))
    assurance.run()
    assert alerts_by_rule(assurance, "money_without_proof")[0].band is Band.HIGH


def test_a_switch_turned_off_around_a_payment_is_a_finding(
    assurance: AssuranceService, ledger: AuditLedger, switches: SwitchBoard, clock: Clock
):
    # Explicit times: ``SwitchBoard`` stamps a flip with the real clock, not an
    # injected one, so a frozen-clock test has to say when each flip happened.
    switches.turn_off(
        Switch.AUTO_FIX_GLOBAL, actor_ref="sup:ruwan", reason="maintenance", now=clock.now
    )
    clock.advance(timedelta(minutes=5))
    ledger.append(
        AuditEventType.ACTION_EXECUTED,
        actor_ref="clarity",
        object_ref="plan:1",
        payload={},
        case_id="CASE-1",
        detail={"total_amount_lkr": "9000.00"},
    )
    clock.advance(timedelta(minutes=5))
    switches.turn_on(Switch.AUTO_FIX_GLOBAL, actor_ref="sup:ruwan", reason="done", now=clock.now)

    assurance.run()

    alert = alerts_by_rule(assurance, "switch_then_pay")[0]
    assert alert.band is Band.HIGH
    assert alert.subject_ref == "sup:ruwan"


def test_a_broken_rule_does_not_stop_the_others(
    assurance: AssuranceService, ledger: AuditLedger, monkeypatch: pytest.MonkeyPatch
):
    """One rule raising must not leave the rest unevaluated."""
    from clarity.modules.assurance import rules

    def broken(*_: object) -> list[object]:
        raise RuntimeError("bad threshold")

    monkeypatch.setitem(rules.RULES, "self_approval", broken)
    for index in range(5):
        approve_and_execute(ledger, case_id=f"CASE-{index}", actor="sup:ruwan", amount="9800.00")

    assurance.run()

    assert alerts_by_rule(assurance, "structuring"), "the other rules still ran"
    assert alerts_by_rule(assurance, "self_approval_failed")[0].band is Band.MEDIUM


def test_the_playbook_never_turns_a_switch_back_on(
    assurance: AssuranceService, switches: SwitchBoard, verification: Verification
):
    verification.intact = False
    verification.reason = "broken"
    assurance.run()
    switches.turn_on(
        Switch.AUTO_FIX_GLOBAL, actor_ref="sec:alice", reason="investigated", now=datetime.now(UTC)
    )

    flipped = assurance.chain_break_playbook(reason="broken again")

    assert flipped == [Switch.AUTO_FIX_GLOBAL], "only the one that was on"
    assert switches.is_off(Switch.AUTO_FIX_GLOBAL)


def test_a_quiet_run_still_beats(assurance: AssuranceService, clock: Clock):
    """A run that found nothing and a run that never happened must differ."""
    assurance.run()
    first = assurance.last_run()
    clock.advance(timedelta(minutes=5))
    assurance.run()

    assert first is not None
    assert assurance.last_run() != first


def test_an_intact_trail_raises_nothing(assurance: AssuranceService):
    assert assurance.run() == []


def test_the_detection_interval_comes_from_policy(assurance: AssuranceService):
    assert assurance.sweep_interval() == timedelta(minutes=5)


def test_the_structuring_cap_comes_from_the_decision_policy(
    assurance: AssuranceService, ledger: AuditLedger
):
    """The rule reads the real four-eyes cap, not a number of its own (I10)."""
    cap = Decimal(str(POLICY["decision.four_eyes.threshold_lkr"]))
    just_under = cap * Decimal("0.95")
    for index in range(5):
        approve_and_execute(
            ledger, case_id=f"CASE-{index}", actor="sup:ruwan", amount=f"{just_under:.2f}"
        )

    assurance.run()

    assert alerts_by_rule(assurance, "structuring")
