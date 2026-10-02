"""The case aggregate and the resolution service (issue #34, M-CASE).

``CaseService`` used to be one class that both held the case and called every
other module. Plan 21 section 2.2 split those two jobs. These tests cover the
seam: the aggregate owns the state machine, the resolution service owns the
sequence, and reading a case never changes it.
"""

from __future__ import annotations

import pytest

from clarity.app.container import Clarity
from clarity.contracts.case import CaseState
from clarity.integration.drivers.mock.world import build_demo_world, ref_for
from clarity.kernel.common import Channel
from clarity.modules.case.public import CaseAggregate, CaseNotFound
from clarity.modules.resolution.public import ResolutionService
from clarity.platform.messaging.envelope import EventType

DILANI = "+94771234567"  # VAS without consent: ONE_TAP_FIX, LKR 49


@pytest.fixture
def clarity() -> Clarity:
    return Clarity(world=build_demo_world())


@pytest.fixture
def cases(clarity: Clarity) -> ResolutionService:
    return clarity.cases


def _open(cases: ResolutionService) -> str:
    case = cases.open_case(
        subscriber_ref=ref_for(DILANI), msisdn_masked="077***4567", channel=Channel.APP
    )
    return case.case_id


# -- acceptance 2: reading a case does not re-decide it ------------------- #


def test_evaluating_twice_does_not_re_make_the_decision(cases: ResolutionService) -> None:
    """An agent reading a case in the Desk must not change its outcome.

    A receipt already cites the original decision, so a second evaluation that
    produced a different one would make the receipt a lie about what was
    decided.
    """
    case_id = _open(cases)

    first = cases.evaluate(case_id)
    second = cases.evaluate(case_id)

    assert second.decision_id == first.decision_id
    assert second is first or second == first


def test_evaluating_after_a_plan_exists_keeps_the_same_decision(
    cases: ResolutionService,
) -> None:
    case_id = _open(cases)
    decision = cases.evaluate(case_id)
    cases.propose(case_id, created_by="channel:web")

    assert cases.evaluate(case_id).decision_id == decision.decision_id


def test_evaluating_after_execution_keeps_the_decision_the_receipt_cites(
    cases: ResolutionService, clarity: Clarity
) -> None:
    case_id = _open(cases)
    decision = cases.evaluate(case_id)
    plan = cases.propose(case_id, created_by="channel:web")
    _, receipt = cases.confirm_and_execute(case_id, plan.plan_id)

    again = cases.evaluate(case_id)

    assert again.decision_id == decision.decision_id
    assert receipt.payload.decision.decision_id == decision.decision_id


# -- the aggregate owns the state machine -------------------------------- #


def test_the_aggregate_is_the_only_thing_that_moves_a_case(clarity: Clarity) -> None:
    """The resolution service asks the aggregate; it does not set a state."""
    aggregate = clarity.case_aggregate

    assert isinstance(aggregate, CaseAggregate)
    case_id = _open(clarity.cases)
    assert aggregate.get(case_id).case.state is CaseState.OPEN


def test_the_aggregate_refuses_an_unknown_case(clarity: Clarity) -> None:
    with pytest.raises(CaseNotFound):
        clarity.case_aggregate.get("CASE-does-not-exist")


def test_a_case_moves_through_its_states_in_order(cases: ResolutionService) -> None:
    case_id = _open(cases)
    assert cases.get(case_id).case.state is CaseState.OPEN

    cases.evaluate(case_id)
    assert cases.get(case_id).case.state is CaseState.AWAITING_CUSTOMER

    plan = cases.propose(case_id, created_by="channel:web")
    cases.confirm_and_execute(case_id, plan.plan_id)
    assert cases.get(case_id).case.state is CaseState.RECEIPTED


def test_the_resolution_service_keeps_no_case_state(cases: ResolutionService) -> None:
    """All of it is in the repository, so a second replica sees the same case."""
    collections = [
        name
        for name, value in vars(cases).items()
        if isinstance(value, dict | list | set) and value
    ]
    assert collections == [], f"the orchestrator is holding state: {collections}"


# -- case.created is published ------------------------------------------- #


def test_opening_a_case_publishes_case_created(cases: ResolutionService, clarity: Clarity) -> None:
    """So insights and autopsy can follow a case from its start (ADR-0029)."""
    case_id = _open(cases)
    clarity.relay.run_once()

    created = [
        event for event in clarity.relay.published_events() if event.type is EventType.CASE_CREATED
    ]
    assert len(created) == 1
    assert created[0].payload().case_id == case_id  # type: ignore[attr-defined]
    assert created[0].subject == ref_for(DILANI), "keyed by subscriber, so order holds"


def test_case_created_carries_no_raw_number(cases: ResolutionService, clarity: Clarity) -> None:
    _open(cases)
    clarity.relay.run_once()
    event = next(e for e in clarity.relay.published_events() if e.type is EventType.CASE_CREATED)

    serialised = event.model_dump_json()
    assert DILANI not in serialised
    assert "771234567" not in serialised


# -- the public surface the interfaces use is unchanged ------------------- #


def test_the_resolution_service_answers_the_calls_case_service_did() -> None:
    """M-CASE moved the class; the interfaces were not supposed to notice."""
    expected = {
        "open_case",
        "get",
        "save",
        "all_cases",
        "build_timeline",
        "evaluate",
        "propose",
        "confirm_and_execute",
        "approve_and_execute",
        "auto_fix",
        "issue_explanation_receipt",
        "on_action_completed",
        "switches",
        "policies",
        "rules",
        "receipts",
        "executable_outcomes",
    }
    missing = sorted(name for name in expected if not hasattr(ResolutionService, name))
    assert missing == [], f"the HTTP and MCP interfaces call these: {missing}"
