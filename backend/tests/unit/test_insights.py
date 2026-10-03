"""Insights read models (I01, #30; plan 02 section 3.5, plan 10).

The issue starts from "dashboards read live objects", which means they read
whatever is in one process: a restart loses the numbers, a second replica
disagrees with the first, and nobody can ask what the figures were last week.

So acceptance 1 is the property that makes a projection worth having:
**replaying the log rebuilds exactly the same numbers**. Everything else here
is a way that property breaks.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from clarity.contracts.decision import ActionType, Outcome
from clarity.contracts.events import (
    ActionCompletedV1,
    ActionStepV1,
    CaseCreatedV1,
    CauseDetectedV1,
    ConversationTurnCompletedV1,
    DecisionGeneratedV1,
)
from clarity.kernel.common import Channel, Language
from clarity.modules.insights.public import Insights, InsightsService, apply, rebuild
from clarity.platform.messaging.envelope import Event

AT = datetime(2026, 10, 4, tzinfo=UTC)
SUBJECT = "sub_dilani"


def case_created(case_id: str) -> Event:
    return Event.of(
        CaseCreatedV1(
            case_id=case_id,
            case_no=f"CL-{case_id}",
            channel=Channel.APP,
            trigger="customer",
            language=Language.EN,
        ),
        subject=SUBJECT,
    )


def cause(case_id: str, rule_id: str = "VAS_NO_CONSENT", version: int = 4) -> Event:
    return Event.of(
        CauseDetectedV1(
            case_id=case_id,
            rule_id=rule_id,
            rule_version=version,
            confidence=0.9,
            snapshot_hash="sha256:aa",
        ),
        subject=SUBJECT,
    )


def decision(case_id: str, outcome: Outcome = Outcome.ONE_TAP_FIX) -> Event:
    return Event.of(
        DecisionGeneratedV1(
            case_id=case_id,
            decision_id=f"DEC-{case_id}",
            outcome=outcome,
            policy_version="1",
            input_hash="sha256:bb",
        ),
        subject=SUBJECT,
    )


def refund(case_id: str, amount: str = "49.00") -> Event:
    return Event.of(
        ActionCompletedV1(
            case_id=case_id,
            plan_id=f"PLAN-{case_id}",
            decision_id=f"DEC-{case_id}",
            steps=[
                ActionStepV1(
                    action_id=f"ACT-{case_id}",
                    action_type=ActionType.REFUND,
                    amount_lkr=amount,
                    status="COMPLETED",
                    idempotency_key=f"{case_id}:plan:0:refund",
                )
            ],
            confirmed_by="customer",
            total_amount_lkr=amount,
        ),
        subject=SUBJECT,
    )


def turn(
    case_id: str,
    turn_no: int,
    *,
    flow: str = "DISPUTE_CHARGE",
    state: str = "explain",
    handoff: bool = False,
    refused: bool = False,
    verifier_ok: bool = True,
) -> Event:
    return Event.of(
        ConversationTurnCompletedV1(
            case_id=case_id,
            turn_no=turn_no,
            channel=Channel.APP,
            flow=flow,
            flow_state=state,
            intent="UNEXPECTED_CHARGE",
            language=Language.EN,
            handoff=handoff,
            refused=refused,
            verifier_ok=verifier_ok,
        ),
        subject=SUBJECT,
    )


def a_log() -> list[Event]:
    """A log with every shape the dashboards read."""
    return [
        case_created("C1"),
        cause("C1"),
        decision("C1"),
        refund("C1", "49.00"),
        turn("C1", 1, state="identify"),
        turn("C1", 2, state="receipt"),
        case_created("C2"),
        cause("C2", "DUPLICATE_RELOAD", 2),
        decision("C2", Outcome.AUTO_FIX),
        refund("C2", "100.00"),
        turn("C2", 1, state="done"),
        case_created("C3"),
        cause("C3", "FUP_CAP_REACHED", 1),
        decision("C3", Outcome.EXPLAIN_ONLY),
        turn("C3", 1, state="explain"),
        case_created("C4"),
        cause("C4", "VAS_NO_CONSENT", 4),
        decision("C4", Outcome.HANDOFF),
        turn("C4", 1, state="handoff", handoff=True),
        case_created("C5"),
        turn("C5", 1, state="identify", refused=True),
        turn("C5", 2, state="identify", verifier_ok=False),
    ]


# -- acceptance 1: replaying the log rebuilds the same numbers ----------- #


def test_replaying_the_log_rebuilds_the_same_numbers():
    """I01 acceptance 1, over the whole dashboard rather than one figure.

    Compared as the serialised dashboards, not field by field: a projection
    that agreed on the counts and disagreed on a rate or a share would pass a
    narrower assertion and still put two different numbers on two screens.
    """
    log = a_log()
    incremental = Insights()
    for event in log:
        apply(incremental, event)

    replayed = rebuild(log)

    assert replayed.to_dict() == incremental.to_dict()


def test_a_rebuild_through_the_service_matches_what_it_folded_live():
    """The same property through the stored read model.

    The pure fold agreeing with itself is necessary and not sufficient: the
    service reads, folds and writes back per event, and a projection that lost
    something on the round trip would still pass the test above.
    """
    log = a_log()
    service = InsightsService()
    for event in log:
        service.on_event(event)
    live = service.dashboards()

    rebuilt = service.rebuild_from(log).to_dict()

    assert rebuilt == live


def test_the_order_events_arrive_in_does_not_change_the_numbers():
    """Across partitions there is no global order, so there must be no reliance on one.

    This is the strong version of acceptance 1: a replay happens to be in log
    order, and a *consumer* sees whatever order delivery gives it. A projection
    that agreed only in log order would drift in production and agree in the
    test.
    """
    log = a_log()
    in_order = rebuild(log).to_dict()

    shuffled = list(log)
    random.Random(7).shuffle(shuffled)
    out_of_order = rebuild(shuffled).to_dict()

    assert out_of_order == in_order


def test_folding_the_whole_log_twice_counts_it_once():
    """Consumers are at-least-once (I7), so a redelivery is normal.

    Without the seen set the first redelivery silently doubles a dashboard and
    nothing says it happened.
    """
    log = a_log()
    once = rebuild(log).to_dict()

    state = rebuild(log)
    for event in log:
        apply(state, event)

    assert state.to_dict() == once


def test_a_redelivery_of_a_folded_event_is_a_no_op():
    """The honest version of the test above, with the same event object."""
    log = a_log()
    state = rebuild(log)
    before = state.to_dict()

    apply(state, log[3])  # the refund, again

    assert state.to_dict() == before


# -- the four dashboards -------------------------------------------------- #


def test_top_causes_ranks_what_the_detector_is_firing_on():
    board = rebuild(a_log()).top_causes()

    assert board[0]["cause_ref"] == "VAS_NO_CONSENT@4"
    assert board[0]["cases"] == 2
    assert board[0]["share"] == pytest.approx(0.5)
    assert [row["cause_ref"] for row in board[1:]] == [
        "DUPLICATE_RELOAD@2",
        "FUP_CAP_REACHED@1",
    ]


def test_a_cause_carries_its_rule_version():
    """A rule id without a version names two different rules over time.

    The same `VAS_NO_CONSENT` at version 3 and version 4 are different logic,
    and a dashboard that merged them would hide the effect of publishing one.
    """
    assert all("@" in row["cause_ref"] for row in rebuild(a_log()).top_causes())


def test_a_share_of_nothing_is_not_zero_percent():
    """An empty dashboard must read as "no data", not as a real zero."""
    assert rebuild([]).top_causes() == []
    assert rebuild([]).drop_offs()["rate"] is None
    assert rebuild([]).where_ai_stops()["containment"] is None


def test_where_ai_stops_separates_the_reasons():
    """One "handoff" number cannot tell a guard firing from a dead journey.

    They call for different work: a refusal is a safety control doing its job,
    a verifier failure is the assistant nearly saying something wrong.
    """
    board = rebuild(a_log()).where_ai_stops()

    assert board["conversations"] == 5
    assert board["by_reason"]["handoff"] == 1
    # C5's latest turn is the verifier failure, so that is what it stopped on.
    assert board["by_reason"]["verifier_failed"] == 1
    assert board["by_reason"]["refused"] == 0
    assert board["stopped"] == 2
    assert board["containment"] == pytest.approx(0.6)


def test_a_handoff_is_not_counted_as_a_drop_off():
    """The metric most easily faked.

    Counting every conversation that is not `answered` would include the ones
    correctly handed to a person, which are resolutions of a different kind.
    """
    board = rebuild(a_log()).drop_offs()

    assert board["dropped"] == 2, board["last_state"]
    assert "DISPUTE_CHARGE.handoff" not in board["last_state"]
    assert "DISPUTE_CHARGE.explain" in board["last_state"]


def test_the_latest_turn_is_decided_by_turn_no_not_by_arrival():
    """Otherwise a replay in another order gives another answer.

    C1 ends at `receipt`, which is an ending. Delivered backwards it must
    still end at `receipt`.
    """
    log = [
        case_created("C1"),
        turn("C1", 1, state="identify"),
        turn("C1", 2, state="receipt"),
    ]
    forwards = rebuild(log)
    backwards = rebuild(list(reversed(log)))

    assert forwards.drop_offs()["dropped"] == 0
    assert backwards.drop_offs()["dropped"] == 0


def test_refunds_by_rule_joins_at_read_time():
    """A refund whose cause has not arrived yet must not be lost.

    The join is deferred precisely so delivery order cannot change the total.
    """
    board = rebuild(a_log()).refunds_by_rule()

    by_cause = {row["cause_ref"]: row for row in board}
    assert by_cause["DUPLICATE_RELOAD@2"]["refunded_lkr"] == "100.00"
    assert by_cause["VAS_NO_CONSENT@4"]["refunded_lkr"] == "49.00"


def test_a_refund_arriving_before_its_cause_is_still_attributed():
    """The order that would break an apply-time join."""
    out_of_order = rebuild([refund("C9", "75.00"), cause("C9", "DUPLICATE_RELOAD", 2)])

    board = out_of_order.refunds_by_rule()

    assert board == [{"cause_ref": "DUPLICATE_RELOAD@2", "cases": 1, "refunded_lkr": "75.00"}]


def test_a_refund_with_no_known_cause_is_reported_not_dropped():
    """Money that moved and cannot be explained is the most important row.

    Dropping it would make the dashboard's total disagree with the ledger and
    hide the one case somebody needs to look at.
    """
    board = rebuild([refund("C9", "25.00")]).refunds_by_rule()

    assert board == [{"cause_ref": "unattributed", "cases": 1, "refunded_lkr": "25.00"}]


def test_money_stays_decimal_through_the_projection():
    """I3: no float ever touches a money path, including a dashboard's."""
    state = rebuild([refund("C1", "0.10"), refund("C1", "0.20")])

    assert state.cases["C1"].refunded_lkr == Decimal("0.30")
    assert state.refunds_by_rule()[0]["refunded_lkr"] == "0.30"


def test_several_executions_on_one_case_are_summed():
    """A case can be remediated more than once; each one moved money."""
    state = rebuild([cause("C1"), refund("C1", "49.00"), refund("C1", "11.00")])

    assert state.refunds_by_rule()[0]["refunded_lkr"] == "60.00"


# -- the projection is pure ---------------------------------------------- #


def test_the_projection_reads_nothing_but_its_events():
    """A projection that consulted a clock or a repository could not be rebuilt.

    Checked by parsing the module rather than by trusting it: an import added
    later would be invisible in a behaviour test until a rebuild disagreed.
    """
    import ast
    import pathlib

    import clarity.modules.insights.projections as module

    tree = ast.parse(pathlib.Path(module.__file__).read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)

    forbidden = {
        name
        for name in imported
        if "persistence" in name or name in {"time", "random"} or "utc_now" in name
    }
    assert forbidden == set(), f"a projection must not read {forbidden}"
    assert not any("clock" in name for name in imported)


# -- against the real container ------------------------------------------ #


def test_the_real_event_log_rebuilds_to_the_same_dashboards():
    """Acceptance 1 against events the system actually produced.

    The crafted log above proves the fold is deterministic. This proves the
    events the system really emits carry what the dashboards read: a
    projection can be perfectly deterministic over a log whose fields it never
    populates, and every number would be zero.
    """
    from clarity.app.container import Clarity
    from clarity.integration.drivers.mock.world import build_demo_world, ref_for
    from clarity.kernel.common import Channel
    from clarity.platform.messaging.outbox import outbox_in

    clarity = Clarity(world=build_demo_world())
    subscriber = ref_for("+94771234567")
    for _ in range(3):
        case = clarity.cases.open_case(
            subscriber_ref=subscriber,
            msisdn_masked="077***4567",
            channel=Channel.APP,
            charge_ref=None,
        )
        clarity.cases.evaluate(case.case_id)
    clarity.deliver_events()

    live = clarity.insights.dashboards()
    assert live["events_folded"] > 0, "the relay delivered nothing, so this proves nothing"
    assert live["top_causes"], "no cause reached the projection"

    with clarity.open_unit() as unit:
        log = [row.event for row in outbox_in(unit).all_rows()]

    rebuilt = clarity.insights.rebuild_from(log).to_dict()

    assert rebuilt == live
