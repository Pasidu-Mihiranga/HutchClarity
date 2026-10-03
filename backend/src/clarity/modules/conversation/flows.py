"""The flow DSL and registry (C02, plan 22 section 5; plan 02 section 3.8).

A flow is **policy content**, not code: versioned YAML published under the
change lifecycle (plan 20, kinds K4 and K6), the same way a rule pack is. The
reason is the same reason rule packs are files. Changing what the assistant is
allowed to do in a given step should be a reviewable artefact with an owner and
a version, not a commit somewhere in a service class.

Three properties this module exists to guarantee.

**A state may only use the tools its flow declares.** The allowlist is the
security surface of a flow: it is what stops a knowledge answer reaching
`propose_action`. It is checked when the file loads, so a flow naming a tool
outside its own allowlist is refused at publication rather than discovered when
a customer hits that state (C02 acceptance 2). The router enforces it again at
call time, because a validated list that nothing consults is documentation.

**Conditions are a closed vocabulary, never an expression.** `when:` takes one
of the values in `Condition` and nothing else. A flow file is policy content
written by people who are not reviewing it as code, so an evaluated expression
in it would be both a correctness risk and an injection surface. An unknown
condition fails the load.

The field is called `transitions` and not `on`. In YAML 1.1, which PyYAML
implements, a bare `on` key parses as the boolean `True`: the same trap that
bites GitHub Actions workflows. `extra="forbid"` on the model turns that into a
loud refusal rather than a flow whose edges silently vanish, but the field is
named out of the way so nobody has to rediscover it.

**Loading is strict and whole.** One malformed flow fails the entire load, as
with rule packs. Silently shrinking the flow set means a customer gets the
fallback for a journey that exists, which looks like a product gap rather than
a deployment fault.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import model_validator

from clarity.kernel.canonical import hash_payload
from clarity.kernel.common import ClarityModel
from clarity.modules.conversation.intents import Intent


class FlowStatus(StrEnum):
    ACTIVE = "active"
    DRAFT = "draft"
    RETIRED = "retired"


class Condition(StrEnum):
    """Everything a transition is allowed to test.

    Closed on purpose. Each value is a question the router can answer from the
    turn's intake and the case facts it was handed, with no access to anything
    else, so reading a flow file tells you exactly what can move it.
    """

    ALWAYS = "always"
    """Unconditional. Used for a step that simply follows the previous one."""

    HANDOFF_REQUESTED = "handoff_requested"
    """The customer asked for a person, or the guard tripped."""

    NO_CASE = "no_case"
    CASE_PRESENT = "case_present"
    DECISION_PENDING = "decision_pending"
    """A case exists but has not been evaluated yet."""

    OUTCOME_AUTO_FIX = "outcome_auto_fix"
    OUTCOME_ONE_TAP = "outcome_one_tap"
    OUTCOME_STAFF_APPROVAL = "outcome_staff_approval"
    OUTCOME_EXPLAIN_ONLY = "outcome_explain_only"
    OUTCOME_HANDOFF = "outcome_handoff"

    PLAN_PENDING = "plan_pending"
    """A plan has been proposed and is waiting for a confirmation."""
    RECEIPT_READY = "receipt_ready"
    """A receipt exists for this case, so something was executed and proved."""

    ANSWER_FOUND = "answer_found"
    NO_SOURCE = "no_source"
    """Retrieval returned nothing citable, so the honest move is a person."""

    SAFEGUARD_CHOSEN = "safeguard_chosen"
    NETWORK_INCIDENT = "network_incident"
    NETWORK_CLEAR = "network_clear"


class Transition(ClarityModel):
    """One edge out of a state."""

    when: Condition
    to: str


class FlowState(ClarityModel):
    """One step of a flow."""

    name: str
    description: str = ""
    tools: tuple[str, ...] = ()
    """Tools this state may use. Must be a subset of the flow's allowlist."""

    agentic: bool = False
    """Whether a bounded agent step may choose among `tools` here.

    Declared and validated now; the planner that honours it is C03 (#22). A
    state marked agentic behaves exactly like a deterministic one until then,
    which is the safe direction for the marker to fail in.
    """

    slots_required: tuple[str, ...] = ()
    proposes: bool = False
    """Whether this state creates a pending plan. Never executes one."""

    terminal: bool = False
    transitions: tuple[Transition, ...] = ()

    @model_validator(mode="after")
    def _proposing_states_need_the_tool(self) -> FlowState:
        if self.proposes and "propose_action" not in self.tools:
            raise ValueError(
                f"state {self.name!r} proposes but does not allow 'propose_action'; "
                "a state that creates a plan must say so in its tools"
            )
        if self.terminal and self.transitions:
            raise ValueError(f"state {self.name!r} is terminal but declares transitions")
        return self


class Flow(ClarityModel):
    """One customer journey, as published policy content."""

    flow_id: str
    version: int
    status: FlowStatus = FlowStatus.ACTIVE
    owner: str
    description: str
    entry_intents: tuple[str, ...]
    tools: tuple[str, ...] = ()
    """The flow's allowlist. No state may use a tool outside it."""

    initial: str
    states: tuple[FlowState, ...]
    exits: tuple[str, ...] = ()

    @property
    def ref(self) -> str:
        return f"{self.flow_id}@{self.version}"

    @property
    def flow_hash(self) -> str:
        """Hash recorded on a turn, so a trail names the exact flow logic."""
        return str(hash_payload(self.model_dump(mode="json")))

    @property
    def state_names(self) -> frozenset[str]:
        return frozenset(state.name for state in self.states)

    def state(self, name: str) -> FlowState:
        for state in self.states:
            if state.name == name:
                return state
        raise FlowNotFound(f"{self.flow_id}: no state named {name!r}")

    def allows(self, state_name: str, tool: str) -> bool:
        """Whether `tool` may be used in `state_name`."""
        if tool not in self.tools:
            return False
        return tool in self.state(state_name).tools

    @model_validator(mode="after")
    def _validate(self) -> Flow:
        if not self.states:
            raise ValueError(f"{self.flow_id}: declares no states")

        names = [state.name for state in self.states]
        duplicates = sorted({name for name in names if names.count(name) > 1})
        if duplicates:
            raise ValueError(f"{self.flow_id}: duplicate states {duplicates}")

        known = self.state_names

        # C02 acceptance 2. The allowlist is the flow's security surface, so a
        # state reaching outside it is refused here rather than at runtime.
        for state in self.states:
            outside = sorted(set(state.tools) - set(self.tools))
            if outside:
                raise ValueError(
                    f"{self.flow_id}: state {state.name!r} uses {outside} "
                    f"which is not in the flow's allowlist {sorted(self.tools)}"
                )

        if self.initial not in known:
            raise ValueError(f"{self.flow_id}: initial state {self.initial!r} is not declared")

        for state in self.states:
            for edge in state.transitions:
                if edge.to not in known:
                    raise ValueError(
                        f"{self.flow_id}: state {state.name!r} transitions to "
                        f"{edge.to!r}, which is not declared"
                    )
            whens = [edge.when for edge in state.transitions]
            repeated = sorted({w.value for w in whens if whens.count(w) > 1})
            if repeated:
                raise ValueError(
                    f"{self.flow_id}: state {state.name!r} tests {repeated} more than once; "
                    "the first match wins, so the later one is dead"
                )

        for exit_name in self.exits:
            if exit_name not in known:
                raise ValueError(f"{self.flow_id}: exit {exit_name!r} is not a declared state")
            if not self.state(exit_name).terminal:
                raise ValueError(f"{self.flow_id}: exit {exit_name!r} is not a terminal state")

        if not any(state.terminal for state in self.states):
            raise ValueError(f"{self.flow_id}: no terminal state, so the flow cannot end")

        unknown_intents = sorted(set(self.entry_intents) - {i.value for i in Intent})
        if unknown_intents:
            raise ValueError(
                f"{self.flow_id}: entry intents {unknown_intents} are not real intents"
            )

        # Unreachable states are almost always a renamed transition target that
        # was missed, and they are invisible until the journey they belong to
        # stops working.
        reachable = {self.initial}
        frontier = [self.initial]
        while frontier:
            current = frontier.pop()
            for edge in self.state(current).transitions:
                if edge.to not in reachable:
                    reachable.add(edge.to)
                    frontier.append(edge.to)
        orphans = sorted(known - reachable)
        if orphans:
            raise ValueError(f"{self.flow_id}: states {orphans} cannot be reached from the initial")

        return self


class FlowError(ValueError):
    """A flow file is malformed, or asks for something that does not exist."""


class FlowNotFound(LookupError):
    """No flow or state by that name."""


class FlowRegistry:
    """Every published flow, with intent routing.

    Routing is by entry intent and must be unambiguous: two active flows
    claiming the same intent is refused, because the alternative is a silent
    tie broken by file order, and which journey a customer gets would then
    depend on a filename.
    """

    def __init__(self, flows: tuple[Flow, ...]) -> None:
        self._flows = flows
        self._by_id = {flow.flow_id: flow for flow in flows}

        claims: dict[str, str] = {}
        for flow in flows:
            for intent in flow.entry_intents:
                owner = claims.get(intent)
                if owner is not None:
                    raise FlowError(
                        f"intent {intent!r} is claimed by both {owner!r} and "
                        f"{flow.flow_id!r}; one intent, one flow"
                    )
                claims[intent] = flow.flow_id
        self._by_intent = claims

    @property
    def flows(self) -> tuple[Flow, ...]:
        return self._flows

    def __len__(self) -> int:
        return len(self._flows)

    def flow(self, flow_id: str) -> Flow:
        found = self._by_id.get(flow_id)
        if found is None:
            raise FlowNotFound(f"no flow named {flow_id!r}")
        return found

    def get(self, flow_id: str) -> Flow | None:
        return self._by_id.get(flow_id)

    def for_intent(self, intent: str) -> Flow | None:
        """The flow that claims this entry intent, if any."""
        flow_id = self._by_intent.get(intent)
        return self._by_id.get(flow_id) if flow_id else None

    def tool_names(self) -> frozenset[str]:
        """Every tool named by any flow, for checking against the real tools."""
        return frozenset(tool for flow in self._flows for tool in flow.tools)


def load_flow(path: Path) -> Flow:
    """Load and validate one YAML flow."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise FlowError(f"{path.name}: invalid YAML: {error}") from error
    if not isinstance(raw, dict):
        raise FlowError(f"{path.name}: expected a mapping at the top level")
    try:
        return Flow.model_validate(raw)
    except Exception as error:
        raise FlowError(f"{path.name}: {error}") from error


def load_flows(directory: Path, *, active_only: bool = True) -> FlowRegistry:
    """Load every flow in a directory, newest version per flow.

    Strict, like `load_packs`: one malformed file fails the whole load. A flow
    set that quietly shrank would answer a real journey with the fallback, and
    that reads as a product gap rather than a deployment fault.
    """
    if not directory.is_dir():
        raise FlowError(f"{directory} is not a directory")

    flows = [load_flow(path) for path in sorted(directory.glob("*.yaml"))]
    if active_only:
        flows = [flow for flow in flows if flow.status is FlowStatus.ACTIVE]

    newest: dict[str, Flow] = {}
    for flow in flows:
        existing = newest.get(flow.flow_id)
        if existing is None or flow.version > existing.version:
            newest[flow.flow_id] = flow
    return FlowRegistry(tuple(newest[key] for key in sorted(newest)))


__all__ = [
    "Condition",
    "Flow",
    "FlowError",
    "FlowNotFound",
    "FlowRegistry",
    "FlowState",
    "FlowStatus",
    "Transition",
    "load_flow",
    "load_flows",
]
