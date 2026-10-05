"""The bounded agent with a planner actually attached (F2).

**Why this file exists.** `_planner` in the composition root returns ``None``
unless a remote `reason` model is configured, which no test environment has, so
`BoundedAgent` has only ever been exercised on the `NO_PLANNER` path. Every
other test of it asserts the fallback. The loop that asks a planner, validates
what came back, calls a tool through the allowlist and feeds the result back as
untrusted data has never run in CI.

**Why a test double and not a cassette.** F1 added `scripts/record_cassettes.py`
and it refuses to write a recording without a real provider, on purpose: a
cassette whose `response` a developer typed is not a recording, and a suite
replaying one asserts what somebody imagined a model would say. A `Planner`
here is a stub that returns a fixed string, and it is obviously a stub from its
name. When cassettes are recorded, the same assertions run against a real
answer through `_RolePlanner`; nothing here has to change for that.

What is pinned is the agent's half of the contract, which is the half that
matters under I1: the planner proposes and the agent decides. A model that
names a tool the state does not allow, asks for an amount, or returns prose
must change nothing about the turn.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from clarity.modules.conversation.agent import (
    AgentLimits,
    BoundedAgent,
    PlannerReply,
    RejectionCode,
)


class ScriptedPlanner:
    """A planner that returns prepared replies, in order, then stops.

    Named for what it is. It stands in for a model so the agent's loop can be
    driven deterministically; it is not a recording of one.
    """

    def __init__(self, *replies: str | None) -> None:
        self._replies = list(replies)
        self.prompts: list[str] = []

    def propose(self, prompt: str) -> PlannerReply | None:
        self.prompts.append(prompt)
        if not self._replies:
            return None
        reply = self._replies.pop(0)
        if reply is None:
            return None
        return PlannerReply(text=reply, tokens=12, model_role="reason", model="scripted")


class ExplodingPlanner:
    """A planner that raises, because a planner is a network call."""

    def propose(self, prompt: str) -> PlannerReply | None:
        raise TimeoutError("provider did not answer")


def plan(tool: str, *, reason_code: str = "checking_cause", **args: Any) -> str:
    return json.dumps({"tool": tool, "args": args, "reason_code": reason_code})


@pytest.fixture
def tools() -> tuple[list[tuple[str, dict[str, Any]]], Any]:
    """Records what the agent called, and answers each call."""
    calls: list[tuple[str, dict[str, Any]]] = []

    def call_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
        calls.append((name, args))
        return {"tool": name, "found": "one VAS charge, no consent record"}

    return calls, call_tool


ALLOWED = ("get_cause_assessment", "get_case_timeline")


def test_a_well_formed_plan_runs_its_tool(tools):
    """The path that has never executed: propose, validate, call, feed back."""
    calls, call_tool = tools
    planner = ScriptedPlanner(plan("get_cause_assessment"), None)

    trace = BoundedAgent(planner).run(
        state_name="explain",
        allowed_tools=ALLOWED,
        agentic=True,
        call_tool=call_tool,
        context="customer asked why their balance changed",
    )

    assert calls == [("get_cause_assessment", {})]
    assert [call.tool for call in trace.calls] == ["get_cause_assessment"]
    assert trace.calls[0].ok
    assert trace.calls[0].reason_code == "checking_cause"
    assert trace.rejections == ()
    # The planner contributed, so the deterministic step was not what answered.
    assert trace.fell_back is False
    assert trace.tokens == 12
    assert trace.model_role == "reason"


def test_the_tool_result_comes_back_as_untrusted_data(tools):
    """A result is fed back wrapped, so a tool cannot inject instructions.

    This is the property that makes the loop safe to run at all: the second
    prompt contains the first tool's output, and it has to arrive delimited as
    data rather than as more of the system's own instructions.
    """
    _, call_tool = tools
    planner = ScriptedPlanner(
        plan("get_case_timeline", source="billing"),
        plan("get_cause_assessment"),
        None,
    )

    BoundedAgent(planner).run(
        state_name="explain",
        allowed_tools=ALLOWED,
        agentic=True,
        call_tool=call_tool,
    )

    assert len(planner.prompts) == 3
    second = planner.prompts[1]
    assert "no consent record" in second
    assert "untrusted" in second.lower()


def test_a_tool_the_state_does_not_allow_is_refused(tools):
    """Naming a real tool the state did not declare changes nothing."""
    calls, call_tool = tools
    # `request_handoff` exists in TOOL_ARGS but is not in this state's list.
    planner = ScriptedPlanner(plan("request_handoff", reason="customer asked"))

    trace = BoundedAgent(planner).run(
        state_name="explain",
        allowed_tools=ALLOWED,
        agentic=True,
        call_tool=call_tool,
    )

    assert calls == []
    assert RejectionCode.TOOL_NOT_ALLOWED.value in trace.rejections
    assert trace.fell_back is True


def test_an_amount_in_the_arguments_is_refused(tools):
    """I1: a model never supplies an amount, and the agent is where that holds."""
    calls, call_tool = tools
    planner = ScriptedPlanner(
        json.dumps(
            {
                "tool": "get_cause_assessment",
                "args": {"amount_lkr": "5000.00"},
                "reason_code": "refund",
            }
        )
    )

    trace = BoundedAgent(planner).run(
        state_name="explain",
        allowed_tools=ALLOWED,
        agentic=True,
        call_tool=call_tool,
    )

    assert calls == []
    assert RejectionCode.FORBIDDEN_ARGUMENT.value in trace.rejections
    assert trace.fell_back is True


def test_prose_instead_of_a_plan_is_refused(tools):
    """A model that answers in words is a rejection, not a crash."""
    calls, call_tool = tools
    planner = ScriptedPlanner("I think you should look at the VAS charge.")

    trace = BoundedAgent(planner).run(
        state_name="explain",
        allowed_tools=ALLOWED,
        agentic=True,
        call_tool=call_tool,
    )

    assert calls == []
    assert RejectionCode.NOT_JSON.value in trace.rejections


def test_a_plan_with_no_reason_code_is_refused(tools):
    """The audit records why a tool was called, so a plan has to say."""
    calls, call_tool = tools
    planner = ScriptedPlanner(json.dumps({"tool": "get_cause_assessment", "args": {}}))

    trace = BoundedAgent(planner).run(
        state_name="explain",
        allowed_tools=ALLOWED,
        agentic=True,
        call_tool=call_tool,
    )

    assert calls == []
    assert RejectionCode.MISSING_REASON_CODE.value in trace.rejections


def test_the_call_limit_stops_a_planner_that_never_stops(tools):
    """A planner asking forever is bounded, and the bound is recorded."""
    calls, call_tool = tools
    planner = ScriptedPlanner(*[plan("get_cause_assessment")] * 20)

    trace = BoundedAgent(planner, limits=AgentLimits(max_tool_calls=2)).run(
        state_name="explain",
        allowed_tools=ALLOWED,
        agentic=True,
        call_tool=call_tool,
    )

    assert len(calls) == 2
    assert RejectionCode.CALL_LIMIT.value in trace.rejections
    # Two tools ran, so this is not a fallback even though a limit was hit.
    assert trace.fell_back is False


def test_a_planner_that_raises_falls_back_rather_than_failing_the_turn(tools):
    """A provider timing out is the deterministic step's cue, not an error."""
    calls, call_tool = tools

    trace = BoundedAgent(ExplodingPlanner()).run(
        state_name="explain",
        allowed_tools=ALLOWED,
        agentic=True,
        call_tool=call_tool,
    )

    assert calls == []
    assert RejectionCode.PLANNER_FAILED.value in trace.rejections
    assert trace.fell_back is True


def test_a_tool_refusing_is_its_answer_and_is_not_retried(tools):
    """The tool layer refusing ends the loop; it is not a planner fault."""
    seen: list[str] = []

    def call_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
        seen.append(name)
        raise PermissionError("not for this subject")

    planner = ScriptedPlanner(plan("get_cause_assessment"), plan("get_cause_assessment"))

    trace = BoundedAgent(planner).run(
        state_name="explain",
        allowed_tools=ALLOWED,
        agentic=True,
        call_tool=call_tool,
    )

    assert seen == ["get_cause_assessment"]
    assert RejectionCode.TOOL_REFUSED.value in trace.rejections
    assert trace.calls[0].ok is False
    assert trace.calls[0].refusal == "PermissionError"
    assert trace.fell_back is True


def test_a_non_agentic_state_never_asks(tools):
    """The default. Pinned here beside the others so the contrast is visible."""
    calls, call_tool = tools
    planner = ScriptedPlanner(plan("get_cause_assessment"))

    trace = BoundedAgent(planner).run(
        state_name="propose",
        allowed_tools=ALLOWED,
        agentic=False,
        call_tool=call_tool,
    )

    assert calls == []
    assert planner.prompts == []
    assert trace.rejections == (RejectionCode.NOT_AGENTIC.value,)


def test_no_planner_is_a_supported_state(tools):
    """ADR-0009: with no model the deterministic step runs and says so."""
    calls, call_tool = tools

    trace = BoundedAgent(None).run(
        state_name="explain",
        allowed_tools=ALLOWED,
        agentic=True,
        call_tool=call_tool,
    )

    assert calls == []
    assert trace.rejections == (RejectionCode.NO_PLANNER.value,)
    assert trace.fell_back is True
