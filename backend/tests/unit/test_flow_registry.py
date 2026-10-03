"""The flow registry and its validation (C02, issue #21; plan 22 section 5).

Acceptance test 2 for C02 is the first test here: a flow file naming a tool
outside its own allowlist is refused when it loads, not when a customer reaches
that state.

That matters more than it looks. The allowlist is the security surface of a
flow: it is what stops a knowledge answer reaching `propose_action`. A flow is
policy content, published by people who are not reviewing it as code, so the
file has to be the thing that fails. The rest of this file covers the other
ways a flow can be wrong in a way nobody notices until the journey it describes
quietly stops working.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from clarity.app.container import default_flow_dir
from clarity.modules.conversation.flows import (
    Flow,
    FlowError,
    FlowNotFound,
    FlowRegistry,
    FlowStatus,
    load_flow,
    load_flows,
)
from clarity.modules.conversation.intents import Intent

FLOWS = default_flow_dir()

#: A minimal valid flow, copied and broken one way at a time by the tests.
BASE: dict[str, object] = {
    "flow_id": "TEST_FLOW",
    "version": 1,
    "status": "active",
    "owner": "tests",
    "description": "A flow for exercising validation.",
    "entry_intents": ["CASE_STATUS"],
    "tools": ["get_case_timeline", "request_handoff"],
    "initial": "start",
    "exits": ["done"],
    "states": [
        {
            "name": "start",
            "tools": ["get_case_timeline"],
            "transitions": [{"when": "always", "to": "done"}],
        },
        {"name": "done", "terminal": True},
    ],
}


def _write(tmp_path: Path, document: dict[str, object], name: str = "flow.yaml") -> Path:
    path = tmp_path / name
    path.write_text(yaml.safe_dump(document, allow_unicode=True), encoding="utf-8")
    return path


def _broken(**changes: object) -> dict[str, object]:
    import copy

    document = copy.deepcopy(BASE)
    document.update(changes)
    return document


def test_the_base_flow_is_valid(tmp_path):
    """The guard for every test below: they must break something real."""
    flow = load_flow(_write(tmp_path, BASE))

    assert flow.flow_id == "TEST_FLOW"
    assert flow.ref == "TEST_FLOW@1"
    assert flow.status is FlowStatus.ACTIVE


# -- acceptance 2 --------------------------------------------------------- #


def test_a_state_using_a_tool_outside_the_allowlist_is_refused(tmp_path):
    """C02 acceptance 2. The allowlist is the flow's security surface."""
    document = _broken(
        states=[
            {
                "name": "start",
                # propose_action is not in the flow's `tools`.
                "tools": ["get_case_timeline", "propose_action"],
                "transitions": [{"when": "always", "to": "done"}],
            },
            {"name": "done", "terminal": True},
        ]
    )

    with pytest.raises(FlowError) as refused:
        load_flow(_write(tmp_path, document))

    message = str(refused.value)
    assert "propose_action" in message
    assert "allowlist" in message


def test_the_refusal_names_the_state_and_the_allowlist(tmp_path):
    """A validation error nobody can act on makes people delete the check."""
    document = _broken(
        states=[
            {
                "name": "offer",
                "tools": ["search_knowledge"],
                "transitions": [{"when": "always", "to": "done"}],
            },
            {"name": "done", "terminal": True},
        ],
        initial="offer",
    )

    with pytest.raises(FlowError) as refused:
        load_flow(_write(tmp_path, document))

    message = str(refused.value)
    assert "'offer'" in message
    assert "search_knowledge" in message
    assert "get_case_timeline" in message, "the message should say what is allowed"


def test_a_state_that_proposes_must_allow_propose_action(tmp_path):
    """`proposes: true` with no tool is a plan nobody authorised a path to."""
    document = _broken(
        tools=["get_case_timeline", "request_handoff"],
        states=[
            {
                "name": "start",
                "tools": ["get_case_timeline"],
                "proposes": True,
                "transitions": [{"when": "always", "to": "done"}],
            },
            {"name": "done", "terminal": True},
        ],
    )

    with pytest.raises(FlowError, match="propose_action"):
        load_flow(_write(tmp_path, document))


# -- the other ways a flow goes quietly wrong ----------------------------- #


def test_a_transition_to_an_undeclared_state_is_refused(tmp_path):
    document = _broken(
        states=[
            {"name": "start", "transitions": [{"when": "always", "to": "nowhere"}]},
            {"name": "done", "terminal": True},
        ]
    )

    with pytest.raises(FlowError, match="nowhere"):
        load_flow(_write(tmp_path, document))


def test_an_unreachable_state_is_refused(tmp_path):
    """Almost always a renamed transition target, and invisible until a
    customer needs the journey that used to pass through it."""
    document = _broken(
        states=[
            {"name": "start", "transitions": [{"when": "always", "to": "done"}]},
            {"name": "done", "terminal": True},
            {"name": "orphan", "terminal": True},
        ]
    )

    with pytest.raises(FlowError, match="orphan"):
        load_flow(_write(tmp_path, document))


def test_an_initial_state_that_does_not_exist_is_refused(tmp_path):
    with pytest.raises(FlowError, match="initial"):
        load_flow(_write(tmp_path, _broken(initial="missing")))


def test_a_flow_with_no_terminal_state_is_refused(tmp_path):
    """A flow that cannot end keeps a customer in automation for ever."""
    document = _broken(
        exits=[],
        states=[
            {"name": "start", "transitions": [{"when": "always", "to": "loop"}]},
            {"name": "loop", "transitions": [{"when": "always", "to": "start"}]},
        ],
    )

    with pytest.raises(FlowError, match="terminal"):
        load_flow(_write(tmp_path, document))


def test_an_exit_that_is_not_terminal_is_refused(tmp_path):
    document = _broken(exits=["start"])

    with pytest.raises(FlowError, match="terminal"):
        load_flow(_write(tmp_path, document))


def test_a_terminal_state_with_transitions_is_refused(tmp_path):
    document = _broken(
        states=[
            {"name": "start", "transitions": [{"when": "always", "to": "done"}]},
            {
                "name": "done",
                "terminal": True,
                "transitions": [{"when": "always", "to": "start"}],
            },
        ]
    )

    with pytest.raises(FlowError, match="terminal"):
        load_flow(_write(tmp_path, document))


def test_the_same_condition_twice_in_one_state_is_refused(tmp_path):
    """The first match wins, so the second edge is dead and misleading."""
    document = _broken(
        states=[
            {
                "name": "start",
                "transitions": [
                    {"when": "always", "to": "done"},
                    {"when": "always", "to": "other"},
                ],
            },
            {"name": "done", "terminal": True},
            {"name": "other", "terminal": True},
        ]
    )

    with pytest.raises(FlowError, match="more than once"):
        load_flow(_write(tmp_path, document))


def test_an_entry_intent_that_is_not_a_real_intent_is_refused(tmp_path):
    """A typo here silently makes the flow unreachable."""
    with pytest.raises(FlowError, match="not real intents"):
        load_flow(_write(tmp_path, _broken(entry_intents=["NOT_AN_INTENT"])))


def test_an_unknown_condition_is_refused(tmp_path):
    """Conditions are a closed vocabulary, never an expression."""
    document = _broken(
        states=[
            {"name": "start", "transitions": [{"when": "customer_seems_cross", "to": "done"}]},
            {"name": "done", "terminal": True},
        ]
    )

    with pytest.raises(FlowError):
        load_flow(_write(tmp_path, document))


def test_an_unknown_field_is_refused(tmp_path):
    """Strict models, so `on:` parsing as the YAML boolean True fails loudly.

    In YAML 1.1, which PyYAML implements, a bare `on` key is the boolean True.
    That is why the DSL field is `transitions`. If someone writes `on:` anyway,
    this is what catches it rather than the edges silently vanishing.
    """
    document = _broken(
        states=[
            {"name": "start", "on": [{"when": "always", "to": "done"}]},
            {"name": "done", "terminal": True},
        ]
    )

    with pytest.raises(FlowError):
        load_flow(_write(tmp_path, document))


def test_duplicate_states_are_refused(tmp_path):
    document = _broken(
        states=[
            {"name": "start", "transitions": [{"when": "always", "to": "done"}]},
            {"name": "start", "terminal": True},
            {"name": "done", "terminal": True},
        ]
    )

    with pytest.raises(FlowError, match="duplicate"):
        load_flow(_write(tmp_path, document))


def test_malformed_yaml_is_refused(tmp_path):
    path = tmp_path / "flow.yaml"
    path.write_text("flow_id: [unclosed\n", encoding="utf-8")

    with pytest.raises(FlowError, match="invalid YAML"):
        load_flow(path)


def test_one_bad_flow_fails_the_whole_load(tmp_path):
    """Strict, like rule packs. A set that quietly shrank would answer a real
    journey with the fallback, which reads as a product gap not a fault."""
    _write(tmp_path, BASE, "good.yaml")
    _write(tmp_path, _broken(initial="missing"), "bad.yaml")

    with pytest.raises(FlowError):
        load_flows(tmp_path)


def test_two_flows_claiming_one_intent_are_refused():
    """A silent tie would be broken by filename, so which journey a customer
    gets would depend on what the file was called."""
    first = Flow.model_validate(BASE)
    second = Flow.model_validate(_broken(flow_id="OTHER_FLOW"))

    with pytest.raises(FlowError, match="one intent, one flow"):
        FlowRegistry((first, second))


def test_a_draft_flow_is_not_loaded(tmp_path):
    _write(tmp_path, _broken(status="draft"))

    assert len(load_flows(tmp_path)) == 0
    assert len(load_flows(tmp_path, active_only=False)) == 1


def test_the_newest_version_of_a_flow_wins(tmp_path):
    _write(tmp_path, _broken(version=1), "v1.yaml")
    _write(tmp_path, _broken(version=3), "v3.yaml")

    registry = load_flows(tmp_path)

    assert len(registry) == 1
    assert registry.flow("TEST_FLOW").version == 3


def test_an_unknown_flow_or_state_raises(tmp_path):
    registry = load_flows(_write(tmp_path, BASE).parent)

    with pytest.raises(FlowNotFound):
        registry.flow("NO_SUCH_FLOW")
    with pytest.raises(FlowNotFound):
        registry.flow("TEST_FLOW").state("no_such_state")


# -- the committed flow set ----------------------------------------------- #


def test_the_seven_flows_load():
    """Plan 22 section 5 names seven. All of them, loading from config."""
    registry = load_flows(FLOWS)

    assert len(registry) == 7
    assert {flow.flow_id for flow in registry.flows} == {
        "DISPUTE_CHARGE",
        "KNOWLEDGE_QA",
        "ACCOUNT_AND_POLICY",
        "SAFEGUARD_SETUP",
        "CASE_STATUS",
        "NETWORK_STATUS",
        "HANDOFF",
    }


def test_every_intent_is_claimed_by_exactly_one_flow():
    """An unclaimed intent means a customer saying that thing gets no journey.

    The registry already refuses two flows claiming one intent, so this is the
    other half: nothing left over.
    """
    registry = load_flows(FLOWS)
    claimed = {intent for flow in registry.flows for intent in flow.entry_intents}

    assert claimed == {intent.value for intent in Intent}


def test_every_tool_a_flow_names_is_a_real_mcp_tool():
    """A flow naming a tool that does not exist is a journey that dead ends.

    Checked against the real MCP tool registry rather than a list kept here,
    because a list kept here is the thing that goes stale.

    Note: plan 22 section 5 names `get_pack_details` for KNOWLEDGE_QA. That
    tool does not exist in the registry, so the flows do not use it; raised as
    a plan-versus-code disagreement in the C02 devlog rather than invented.
    """
    from clarity.app.container import Clarity
    from clarity.integration.drivers.mock.world import build_demo_world
    from clarity.interfaces.mcp.server import ClarityMCPServer, Profile

    clarity = Clarity(world=build_demo_world())
    server = ClarityMCPServer(clarity.mcp_view)
    real = {spec["name"] for profile in Profile for spec in server.list_tools(profile)}

    named = load_flows(FLOWS).tool_names()
    unknown = sorted(named - real)

    assert unknown == [], f"flows name tools that do not exist: {unknown}"


def test_no_flow_outside_dispute_and_safeguard_can_propose():
    """Only the two journeys that end in a remedy may create a plan (I1).

    A knowledge answer or a status check reaching `propose_action` would be a
    path from a question to a money movement, which is the shape this allowlist
    exists to prevent.
    """
    registry = load_flows(FLOWS)

    may_propose = {flow.flow_id for flow in registry.flows if "propose_action" in flow.tools}

    assert may_propose == {"DISPUTE_CHARGE", "SAFEGUARD_SETUP"}


def test_every_flow_can_reach_a_person():
    """A journey with no way out to a human is a trap (I2: missing evidence
    goes to a person, never a guess)."""
    registry = load_flows(FLOWS)

    for flow in registry.flows:
        assert "request_handoff" in flow.tools, f"{flow.flow_id} cannot reach a person"


def test_knowledge_states_require_citations_through_their_tools():
    """The verifier keys citation requirement off `search_knowledge`, so a
    state that answers from sources has to declare it."""
    registry = load_flows(FLOWS)
    knowledge = registry.flow("KNOWLEDGE_QA")

    assert "search_knowledge" in knowledge.state("answer").tools
    # And the no-source exit must not, or its honest reply would be blocked
    # for missing the citations it is explaining the absence of.
    assert "search_knowledge" not in knowledge.state("offer_person").tools
