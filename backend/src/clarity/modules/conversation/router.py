"""The flow router: moves a conversation through a published flow (C02).

This fills the `FlowEngine` seam C01 left. It is deliberately small, because
everything interesting is in the flow file: the router evaluates the current
state's transitions against a closed vocabulary of conditions and moves on. It
holds no journey logic of its own, which is what makes a flow change a content
change.

Two rules it enforces that the file cannot enforce by itself.

**A state may only call the tools it declares.** The flow file is validated at
load, and this is checked again at call time, because a list nothing consults
is documentation. `ToolNotAllowed` is raised rather than the call being quietly
skipped: a flow asking for a tool it may not use is a bug in the flow, and
silently continuing would hide it until someone noticed the journey producing
nothing.

**The router proposes; it never executes.** A state marked `proposes` creates a
pending plan and stops. The customer's tap goes to `/v1/cases/{id}/confirm`,
which mints and spends the confirmation token server side (ADR-0007, I1). There
is no path from here to an execution, and the tool surface it is given has no
execute capability to reach for.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from clarity.modules.conversation.agent import AgentTrace, BoundedAgent
from clarity.modules.conversation.flows import Condition, Flow, FlowRegistry, FlowState
from clarity.modules.conversation.intents import Intent
from clarity.modules.conversation.orchestrator import FlowOutcome
from clarity.modules.conversation.service import IntakeResult
from clarity.modules.conversation.state import NO_FLOW, ConversationState

#: Facts the router reads. The interface builds these from the case record;
#: nothing here reaches for a module. Documented as a vocabulary because a
#: flow file's conditions are written against it.
#:
#:   case_id            str | None   the case this conversation is attached to
#:   decision_outcome   str | None   an `Outcome` value once evaluated
#:   plan_id            str | None   a pending plan, if one was proposed
#:   receipt_id         str | None   set once something executed and was proved
#:   citations          list[str]    sources a knowledge answer can cite
#:   safeguard          str | None   the safeguard the customer chose
#:   network_incident   bool         an open outage affecting this subscriber
FACT_KEYS = (
    "case_id",
    "decision_outcome",
    "plan_id",
    "receipt_id",
    "citations",
    "safeguard",
    "network_incident",
)

#: How a decision outcome answers an outcome condition.
_OUTCOMES: Mapping[Condition, str] = {
    Condition.OUTCOME_AUTO_FIX: "AUTO_FIX",
    Condition.OUTCOME_ONE_TAP: "ONE_TAP_FIX",
    Condition.OUTCOME_STAFF_APPROVAL: "STAFF_APPROVAL",
    Condition.OUTCOME_EXPLAIN_ONLY: "EXPLAIN_ONLY",
    Condition.OUTCOME_HANDOFF: "HANDOFF",
}

#: How sure the intake has to be before a turn moves an active conversation
#: into a different flow.
#:
#: The keyword rules score a real match at 0.86 and above and a fallback at
#: 0.3, so this sits in the gap. It is a routing parameter rather than a policy
#: value: no amount, cap or eligibility moves with it, and `check_handoff` in
#: this module already works the same way.
MIN_SWITCH_CONFIDENCE = 0.5

#: The most steps one turn may take. A turn walks `always` edges so a flow can
#: describe a step per concept without costing a customer a message each, but a
#: file with a cycle of them would otherwise spin forever. Hitting the limit
#: raises, because a flow that loops is a flow to fix, not to tolerate.
MAX_STEPS_PER_TURN = 8


class ToolNotAllowed(PermissionError):
    """A flow asked for a tool its current state does not declare."""


class FlowLooped(RuntimeError):
    """A flow took too many unconditional steps in one turn."""


class ToolCaller(Protocol):
    """The tool surface a flow may reach, supplied by the composition root.

    Narrow on purpose. The implementation the container wires is built over the
    MCP view, which has read methods and `propose` and no execute capability at
    all, so "the router cannot execute" is a property of the surface rather
    than of this module's good behaviour.
    """

    def call(self, tool: str, *, case_id: str, **args: Any) -> dict[str, Any]: ...


class FlowRouter:
    """Routes an intent to a flow and walks that flow's states."""

    def __init__(
        self,
        registry: FlowRegistry,
        *,
        tools: ToolCaller | None = None,
        agent: BoundedAgent | None = None,
        created_by: str = "assistant",
    ) -> None:
        self._registry = registry
        self._tools = tools
        # No agent is the supported default (ADR-0009): an agentic state then
        # behaves exactly like a deterministic one, which is the safe direction
        # for the marker to fail in.
        self._agent = agent or BoundedAgent()
        self._created_by = created_by

    @property
    def registry(self) -> FlowRegistry:
        return self._registry

    def step(
        self,
        state: ConversationState,
        intake: IntakeResult,
        facts: Mapping[str, Any],
    ) -> FlowOutcome:
        flow = self._flow_for(state, intake)
        if flow is None:
            # No flow claims this intent. Staying put is the honest answer:
            # the fallback template replies and the audit shows no flow drove
            # the turn, rather than a flow being invented for it.
            return FlowOutcome(flow=state.flow, state=state.state)

        current = self._entry_state(flow, state)
        tools_called: list[str] = []
        proposal_id: str | None = facts.get("plan_id")
        produced: dict[str, Any] = {}

        agent_detail: dict[str, Any] = {}
        for _ in range(MAX_STEPS_PER_TURN):
            node = flow.state(current)

            if node.agentic:
                trace = self._plan(flow, node, facts)
                agent_detail = trace.to_detail()
                tools_called.extend(trace.tools_called)
                produced.update(trace.facts)

            if node.proposes and proposal_id is None:
                plan = self._propose(flow, node, facts)
                if plan is not None:
                    tools_called.append("propose_action")
                    proposal_id = str(plan.get("plan_id") or "") or None
                    produced.update(plan)

            nxt = self._next(node, intake, facts, proposal_id=proposal_id)
            if nxt is None or nxt == current:
                break
            current = nxt
        else:
            raise FlowLooped(
                f"{flow.ref}: more than {MAX_STEPS_PER_TURN} steps in one turn; "
                "check for a cycle of 'always' transitions"
            )

        node = flow.state(current)
        found = produced.get("citations") or facts.get("citations") or ()
        citations = tuple(str(entry) for entry in found)
        return FlowOutcome(
            flow=flow.flow_id,
            state=current,
            slots=dict(produced),
            tools_called=tuple(tools_called),
            citations=citations,
            proposal_id=proposal_id,
            facts=dict(produced),
            agent=agent_detail,
            # A knowledge state must cite. The verifier turns this into a
            # blocked reply, so a knowledge answer with no source cannot be
            # sent as though it were grounded (K03, #33).
            requires_citations="search_knowledge" in node.tools,
        )

    # ------------------------------------------------------------------ #

    def _flow_for(self, state: ConversationState, intake: IntakeResult) -> Flow | None:
        """Which flow drives this turn.

        Three rules, in order, and the middle one is the one that matters:

        1. Nothing running: whichever flow claims the intent, if any.
        2. **A flow in progress is not abandoned by a vague turn.** Mid dispute,
           "has it been sorted?" classifies as FALLBACK, and FALLBACK is an
           entry intent for KNOWLEDGE_QA, so taking the claim at face value
           drops the customer out of their dispute and into a knowledge
           answer. A turn only moves a conversation to another flow when it was
           classified confidently.
        3. A finished journey does not trap anyone: once the current flow is in
           a terminal state, a new intent is free to start a new one.
        """
        claimed = self._registry.for_intent(intake.intent)
        current = self._registry.get(state.flow) if state.flow != NO_FLOW else None

        if current is None:
            return claimed
        if claimed is None or claimed.flow_id == current.flow_id:
            return current

        if state.state in current.state_names and current.state(state.state).terminal:
            return claimed
        if intake.intent == Intent.FALLBACK.value:
            return current
        if intake.confidence < MIN_SWITCH_CONFIDENCE:
            return current
        return claimed

    @staticmethod
    def _entry_state(flow: Flow, state: ConversationState) -> str:
        """Where this turn starts: where we were, or the flow's initial state."""
        if state.flow == flow.flow_id and state.state in flow.state_names:
            return state.state
        return flow.initial

    def _next(
        self,
        node: FlowState,
        intake: IntakeResult,
        facts: Mapping[str, Any],
        *,
        proposal_id: str | None,
    ) -> str | None:
        """The first transition whose condition holds. Order is the priority."""
        for edge in node.transitions:
            if self._holds(edge.when, intake, facts, proposal_id=proposal_id):
                return edge.to
        return None

    @staticmethod
    def _holds(
        condition: Condition,
        intake: IntakeResult,
        facts: Mapping[str, Any],
        *,
        proposal_id: str | None,
    ) -> bool:
        outcome = facts.get("decision_outcome")
        expected = _OUTCOMES.get(condition)
        if expected is not None:
            return outcome == expected

        match condition:
            case Condition.ALWAYS:
                return True
            case Condition.HANDOFF_REQUESTED:
                return bool(intake.needs_handoff)
            case Condition.NO_CASE:
                return not facts.get("case_id")
            case Condition.CASE_PRESENT:
                return bool(facts.get("case_id"))
            case Condition.DECISION_PENDING:
                return bool(facts.get("case_id")) and outcome is None
            case Condition.PLAN_PENDING:
                return proposal_id is not None and not facts.get("receipt_id")
            case Condition.RECEIPT_READY:
                return bool(facts.get("receipt_id"))
            case Condition.ANSWER_FOUND:
                return bool(facts.get("citations"))
            case Condition.NO_SOURCE:
                return not facts.get("citations")
            case Condition.SAFEGUARD_CHOSEN:
                return bool(facts.get("safeguard"))
            case Condition.NETWORK_INCIDENT:
                return bool(facts.get("network_incident"))
            case Condition.NETWORK_CLEAR:
                return not facts.get("network_incident")
        return False

    def _propose(
        self, flow: Flow, node: FlowState, facts: Mapping[str, Any]
    ) -> dict[str, Any] | None:
        """Create a pending plan through the tool surface, if one is wired."""
        case_id = facts.get("case_id")
        if self._tools is None or not case_id:
            return None
        if not flow.allows(node.name, "propose_action"):
            raise ToolNotAllowed(f"{flow.ref}: state {node.name!r} may not use 'propose_action'")
        return self._tools.call("propose_action", case_id=str(case_id), created_by=self._created_by)

    def _plan(self, flow: Flow, node: FlowState, facts: Mapping[str, Any]) -> AgentTrace:
        """Let the bounded agent choose among this state's tools (C03, #22).

        Every call it makes goes through ``call_tool``, so the allowlist is
        enforced on the agent's choices by the same code that enforces it on
        the flow's own. The case id comes from the facts and never from the
        plan: the subject is bound by the session (I9).
        """
        case_id = str(facts.get("case_id") or "")

        def call(tool: str, args: dict[str, Any]) -> dict[str, Any]:
            return self.call_tool(flow.flow_id, node.name, tool, case_id=case_id, **args)

        return self._agent.run(
            state_name=node.name,
            allowed_tools=node.tools,
            agentic=node.agentic,
            call_tool=call,
        )

    def call_tool(self, flow_id: str, state_name: str, tool: str, **args: Any) -> dict[str, Any]:
        """Call a tool on behalf of a state, enforcing the allowlist.

        The single entry point for anything a flow wants to do, so the
        allowlist is checked once and cannot be gone around. C03 (#22) routes
        its bounded agent step through here for the same reason.
        """
        flow = self._registry.flow(flow_id)
        if not flow.allows(state_name, tool):
            raise ToolNotAllowed(
                f"{flow.ref}: state {state_name!r} may not use {tool!r}; "
                f"it allows {sorted(flow.state(state_name).tools)}"
            )
        if self._tools is None:
            raise ToolNotAllowed("no tool surface is wired")
        case_id = str(args.pop("case_id", ""))
        return self._tools.call(tool, case_id=case_id, **args)


__all__ = [
    "FACT_KEYS",
    "MAX_STEPS_PER_TURN",
    "MIN_SWITCH_CONFIDENCE",
    "FlowLooped",
    "FlowRouter",
    "ToolCaller",
    "ToolNotAllowed",
]
