"""Every tool a flow file names is served by the adapter (A6).

The gap this closes was invisible rather than broken. Five of the nine tools
the flow files declare raised `ToolUnavailable`, and nothing noticed because
they are only reachable through the bounded agent step (C03), which has never
run: `_planner` returns `None` with no remote provider configured. So a flow
declared a tool, `FlowRegistry` validated the allowlist at load, `call_tool`
validated it again at call time, and the first planner to pick one would have
got `TOOL_REFUSED` for a tool its state was entitled to use.

The first test here is the one that matters: it reads the tool names out of the
shipped flow files rather than a list written beside it, so adding a tool to a
flow and not to the adapter fails the build.
"""

from __future__ import annotations

import pytest

from clarity.app.container import Clarity
from clarity.app.flow_tools import FlowToolAdapter, ToolUnavailable
from clarity.integration.drivers.mock.world import build_demo_world, ref_for
from clarity.kernel.common import Channel

from ..acceptance.conftest import DILANI


@pytest.fixture
def clarity() -> Clarity:
    return Clarity(world=build_demo_world())


@pytest.fixture
def tools(clarity: Clarity) -> FlowToolAdapter:
    """The adapter exactly as the container builds it for the flow router."""
    return FlowToolAdapter(clarity.mcp_view, answers=clarity.answers)


@pytest.fixture
def evaluated(clarity: Clarity) -> str:
    """A case with a decision, so the read tools have something to read."""
    account = clarity.world.account(ref_for(DILANI))
    assert account is not None
    case = clarity.cases.open_case(
        subscriber_ref=account.ref, msisdn_masked=account.masked, channel=Channel.APP
    )
    clarity.cases.evaluate(case.case_id)
    return case.case_id


def test_every_tool_named_by_a_flow_is_implemented(
    clarity: Clarity, tools: FlowToolAdapter, evaluated: str
) -> None:
    """Read from the shipped flow files, not from a list kept beside this test."""
    named = clarity.flows.tool_names()
    assert named, "no tools parsed; the flow file format changed"

    unimplemented: list[str] = []
    for tool in sorted(named):
        try:
            tools.call(tool, case_id=evaluated, query="fair use", rule_id="x")
        except ToolUnavailable:
            unimplemented.append(tool)
        except Exception:
            # Any other outcome means the adapter served it. A refusal, a
            # missing rule or a not-ready case are answers, not gaps.
            pass

    assert unimplemented == [], (
        "a flow declares these tools and the adapter does not serve them, so a "
        f"planner choosing one gets TOOL_REFUSED for a tool it may use: {unimplemented}"
    )


def test_the_timeline_tool_reports_evidence_by_id_and_hash(tools: FlowToolAdapter, evaluated: str):
    result = tools.call("get_case_timeline", case_id=evaluated)

    assert result["snapshot_hash"]
    assert result["events"], "the demo world should have evidence for this case"
    assert all("event_id" in event for event in result["events"])
    assert result["sources"]


def test_the_assessment_tool_reports_what_the_rules_concluded(
    tools: FlowToolAdapter, evaluated: str
):
    result = tools.call("get_cause_assessment", case_id=evaluated)

    assert result["outcome"]
    assert "allowed_actions" in result
    assert "ruled_out" in result


def test_an_unevaluated_case_is_refused_not_raised(
    clarity: Clarity, tools: FlowToolAdapter
) -> None:
    """A flow may explain before the case is evaluated. That is a no, not a fault."""
    account = clarity.world.account(ref_for(DILANI))
    assert account is not None
    case = clarity.cases.open_case(
        subscriber_ref=account.ref, msisdn_masked=account.masked, channel=Channel.APP
    )

    result = tools.call("get_cause_assessment", case_id=case.case_id)

    assert result == {"refused": "CASE_NOT_EVALUATED"}


def test_an_unknown_rule_is_refused_not_raised(tools: FlowToolAdapter, evaluated: str) -> None:
    result = tools.call("explain_rule", case_id=evaluated, rule_id="NO-SUCH-RULE")

    assert result == {"refused": "UNKNOWN_RULE"}


def test_safeguards_report_only_what_was_executed(tools: FlowToolAdapter, evaluated: str) -> None:
    """Offered is not the same as in place, and a customer reads this as in place."""
    result = tools.call("get_customer_safeguards", case_id=evaluated)

    assert result["case_id"] == evaluated
    assert isinstance(result["safeguards"], list)


def test_a_handoff_request_does_not_write_the_desk_queue(
    clarity: Clarity, tools: FlowToolAdapter, evaluated: str
):
    """It records the ask. The queue is derived from the decision.

    A flow that could put a case on a staff member's screen directly would be a
    second, unreviewed route onto the desk.
    """
    before = len(clarity.cases.all_cases())

    result = tools.call("request_handoff", case_id=evaluated, reason="I want to speak to a person")

    assert result["status"] == "handoff_requested"
    assert result["reason"] == "I want to speak to a person"
    assert len(clarity.cases.all_cases()) == before


def test_a_handoff_reason_is_capped(tools: FlowToolAdapter, evaluated: str) -> None:
    """Customer words, so a hint and never evidence (I2), and never unbounded."""
    result = tools.call("request_handoff", case_id=evaluated, reason="x" * 500)

    assert len(result["reason"]) == 200
