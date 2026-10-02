"""MCP server tests (plan §10, §11).

The question these answer is the one a security reviewer will ask: *what is
the worst a compromised or prompt-injected model can do here?* The answer has
to be "ask for something and be refused", and that has to be true at the
boundary, not only by convention.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from clarity.app.container import Clarity
from clarity.integration.drivers.mock.world import build_demo_world, ref_for
from clarity.interfaces.mcp.server import ClarityMCPServer, Principal, Profile, ToolDenied
from clarity.kernel.common import ActionSafetyLevel, Channel
from clarity.modules.resolution.public import ResolutionService

DILANI = "+94771234567"
PRIYA = "+94774445555"


@pytest.fixture
def clarity() -> Clarity:
    return Clarity(world=build_demo_world())


@pytest.fixture
def cases(clarity: Clarity) -> ResolutionService:
    return clarity.cases


@pytest.fixture
def server(clarity: Clarity) -> ClarityMCPServer:
    """Built exactly as the container builds it: through the narrow view."""
    return ClarityMCPServer(clarity.mcp_view)


def open_and_evaluate(clarity: Clarity, msisdn: str) -> str:
    account = clarity.world.account(ref_for(msisdn))
    assert account is not None
    case = clarity.cases.open_case(
        subscriber_ref=account.ref, msisdn_masked=account.masked, channel=Channel.APP
    )
    clarity.cases.evaluate(case.case_id)
    return case.case_id


@pytest.fixture
def case_id(clarity: Clarity) -> str:
    return open_and_evaluate(clarity, DILANI)


def customer(case_id: str) -> Principal:
    return Principal(ref="session-1", profile=Profile.CUSTOMER_ASSIST, case_id=case_id)


def staff() -> Principal:
    return Principal(ref="agent-7", profile=Profile.STAFF_ASSIST)


# --------------------------------------------------------------------------- #
# What the model is even told about
# --------------------------------------------------------------------------- #


def test_no_tool_can_execute_anything(server: ClarityMCPServer):
    """The headline guarantee: there is no execute path over MCP at all."""
    for profile in Profile:
        for tool in server.list_tools(profile):
            assert tool["level"] != ActionSafetyLevel.L4_BULK_ADMIN.value
            assert "execute" not in tool["name"]
            assert "confirm" not in tool["name"]
            assert "approve" not in tool["name"]


def test_the_only_write_a_model_has_is_a_proposal(server: ClarityMCPServer):
    names = {t["name"] for t in server.list_tools(Profile.CUSTOMER_ASSIST)}

    writes = {n for n in names if n.startswith(("propose", "request"))}
    assert writes == {"propose_action", "request_handoff"}


def test_a_customer_profile_sees_fewer_tools_than_staff(server: ClarityMCPServer):
    customer_tools = {t["name"] for t in server.list_tools(Profile.CUSTOMER_ASSIST)}
    staff_tools = {t["name"] for t in server.list_tools(Profile.STAFF_ASSIST)}

    assert customer_tools < staff_tools
    assert "get_desk_queue" not in customer_tools


# --------------------------------------------------------------------------- #
# Reading
# --------------------------------------------------------------------------- #


def test_a_model_can_read_the_evidence(server: ClarityMCPServer, case_id: str):
    result = server.call(customer(case_id), "get_case_timeline", {"case_id": case_id})

    assert result["events"]
    assert result["snapshot_hash"].startswith("sha256:")


def test_a_model_can_read_the_cause_and_what_was_ruled_out(server: ClarityMCPServer, case_id: str):
    result = server.call(customer(case_id), "get_cause_assessment", {"case_id": case_id})

    assert result["cause"]["rule_id"] == "VAS_NO_CONSENT"
    assert result["amount_lkr"] == "49.00"
    assert result["ruled_out"]


def test_a_model_can_look_up_what_a_rule_checks(server: ClarityMCPServer, case_id: str):
    result = server.call(customer(case_id), "explain_rule", {"rule_id": "VAS_NO_CONSENT"})

    assert result["version"] == 4
    assert "Gazette" in (result["legal_basis"] or "")


def test_an_unknown_rule_is_refused(server: ClarityMCPServer, case_id: str):
    with pytest.raises(ToolDenied) as error:
        server.call(customer(case_id), "explain_rule", {"rule_id": "MADE_UP_RULE"})

    assert error.value.code == "UNKNOWN_RULE"


# --------------------------------------------------------------------------- #
# The guards
# --------------------------------------------------------------------------- #


def test_a_tool_outside_the_profile_is_denied(server: ClarityMCPServer, case_id: str):
    with pytest.raises(ToolDenied) as error:
        server.call(customer(case_id), "get_desk_queue")

    assert error.value.code == "NOT_IN_PROFILE"


def test_a_session_cannot_read_another_customers_case(
    server: ClarityMCPServer, clarity: Clarity, case_id: str
):
    """Subject binding: the defence against one agent reading everyone."""
    other = open_and_evaluate(clarity, PRIYA)

    with pytest.raises(ToolDenied) as error:
        server.call(customer(case_id), "get_case_timeline", {"case_id": other})

    assert error.value.code == "NOT_AUTHORISED_FOR_CASE"


def test_an_unbound_customer_session_cannot_read_any_case(server: ClarityMCPServer, case_id: str):
    """A customer profile with no case binding must reach nothing (A04, #8).

    While MCP was in-process this could not happen: the orchestrator set
    ``case_id`` on every customer principal it built. Over the network the
    binding arrives in the *token*, so "customer-assist with no case claim" is
    a shape an external client can actually present, and the old comparison
    (`principal.case_id is not None and case_id != principal.case_id`) skipped
    the check entirely for it. That made an unbound customer token a universal
    read over every case in the system.

    Deny by default (I9): a customer session is bound or it is refused.
    """
    unbound = Principal(ref="attacker", profile=Profile.CUSTOMER_ASSIST, case_id=None)

    with pytest.raises(ToolDenied) as error:
        server.call(unbound, "get_case_timeline", {"case_id": case_id})

    assert error.value.code == "SESSION_NOT_BOUND"


def test_an_unbound_customer_denial_is_audited(server: ClarityMCPServer, case_id: str):
    """Acceptance test 1 of A04: "denied **and audited**"."""
    unbound = Principal(ref="attacker", profile=Profile.CUSTOMER_ASSIST, case_id=None)

    with pytest.raises(ToolDenied):
        server.call(unbound, "get_case_timeline", {"case_id": case_id})

    assert [row.error_code for row in server.denials] == ["SESSION_NOT_BOUND"]
    assert server.denials[0].principal_ref == "attacker"


def test_staff_sessions_are_not_required_to_be_bound(
    server: ClarityMCPServer, clarity: Clarity, case_id: str
):
    """The binding rule must not break the staff profile.

    An agent works a queue, so a staff session is deliberately unbound. If the
    fix for the customer hole were "every session must carry a case", the desk
    would stop working and the test above would still pass.
    """
    other = open_and_evaluate(clarity, PRIYA)

    assert server.call(staff(), "get_case_timeline", {"case_id": case_id})
    assert server.call(staff(), "get_case_timeline", {"case_id": other})


def test_an_unknown_tool_is_denied(server: ClarityMCPServer, case_id: str):
    with pytest.raises(ToolDenied) as error:
        server.call(customer(case_id), "execute_refund", {"case_id": case_id})

    assert error.value.code == "UNKNOWN_TOOL"


def test_missing_arguments_are_refused(server: ClarityMCPServer, case_id: str):
    with pytest.raises(ToolDenied) as error:
        server.call(customer(case_id), "get_case_timeline", {})

    assert error.value.code == "INVALID_ARGUMENTS"


@pytest.mark.parametrize("field", ["amount", "amount_lkr"])
def test_a_model_cannot_supply_an_amount(server: ClarityMCPServer, case_id: str, field):
    """Amounts come from the decision. There is no argument to influence them."""
    with pytest.raises(ToolDenied) as error:
        server.call(
            customer(case_id),
            "propose_action",
            {"case_id": case_id, "action_type": "REFUND", field: "999999.00"},
        )

    assert error.value.code == "AMOUNT_NOT_ACCEPTED"


# --------------------------------------------------------------------------- #
# Proposing is as far as it goes
# --------------------------------------------------------------------------- #


def test_proposing_creates_a_pending_plan_and_changes_nothing(
    server: ClarityMCPServer, clarity: Clarity, case_id: str
):
    opening = clarity.world.account(ref_for(DILANI)).balance_lkr

    result = server.call(
        customer(case_id), "propose_action", {"case_id": case_id, "action_type": "REFUND"}
    )

    assert result["status"] == "PENDING_CONFIRMATION"
    assert result["amount_lkr"] == "49.00", "the amount came from the decision"
    assert clarity.world.account(ref_for(DILANI)).balance_lkr == opening, "nothing moved"


def test_proposing_an_action_the_decision_forbids_is_refused(
    server: ClarityMCPServer, clarity: Clarity
):
    """Kumar's case is explain-only, so no action is available at all."""
    case_id = open_and_evaluate(clarity, "+94773334444")

    with pytest.raises(ToolDenied) as error:
        server.call(
            customer(case_id), "propose_action", {"case_id": case_id, "action_type": "REFUND"}
        )

    assert error.value.code == "OUTCOME_NOT_EXECUTABLE"
    assert server.denials, "a refusal must be audited, not just raised"


def test_an_unknown_action_type_is_refused(server: ClarityMCPServer, case_id: str):
    with pytest.raises(ToolDenied) as error:
        server.call(
            customer(case_id),
            "propose_action",
            {"case_id": case_id, "action_type": "DELETE_EVERYTHING"},
        )

    assert error.value.code == "UNKNOWN_ACTION"


def test_a_proposal_cannot_be_executed_through_mcp(server: ClarityMCPServer, case_id: str):
    """There is simply no tool to call next. That is the design."""
    server.call(customer(case_id), "propose_action", {"case_id": case_id, "action_type": "REFUND"})

    available = {t["name"] for t in server.list_tools(Profile.CUSTOMER_ASSIST)}
    assert not any("execute" in n or "confirm" in n for n in available)


# --------------------------------------------------------------------------- #
# Audit
# --------------------------------------------------------------------------- #


def test_every_call_is_audited(server: ClarityMCPServer, case_id: str):
    server.call(customer(case_id), "get_case_timeline", {"case_id": case_id})

    assert len(server.audit) == 1
    row = server.audit[0]
    assert row.tool == "get_case_timeline"
    assert row.decision == "allowed"
    assert row.args_hash.startswith("sha256:")


def test_denials_are_audited_too_and_can_be_watched(server: ClarityMCPServer, case_id: str):
    """A spike of denials is the signal for prompt injection (plan §10.3)."""
    for _ in range(3):
        with pytest.raises(ToolDenied):
            server.call(customer(case_id), "get_desk_queue")

    assert len(server.denials) == 3
    assert all(row.error_code == "NOT_IN_PROFILE" for row in server.denials)


def test_the_audit_records_who_called_and_at_what_level(server: ClarityMCPServer, case_id: str):
    server.call(customer(case_id), "propose_action", {"case_id": case_id, "action_type": "REFUND"})

    row = server.audit[-1]
    assert row.principal_ref == "session-1"
    assert row.profile is Profile.CUSTOMER_ASSIST
    assert row.level is ActionSafetyLevel.L3_FINANCIAL


def test_staff_can_read_the_queue(server: ClarityMCPServer, clarity: Clarity):
    open_and_evaluate(clarity, PRIYA)

    queue = server.call(staff(), "get_desk_queue")

    assert queue and queue[0]["money_at_stake_lkr"] == "12000.00"


# --------------------------------------------------------------------------- #
# The boundary is a property of the code, not a convention (plan item 0.4)
# --------------------------------------------------------------------------- #

#: Methods that move money or authorise it. None may appear in the MCP package.
FORBIDDEN_IN_MCP = frozenset(
    {
        "execute",
        "confirm_and_execute",
        "approve_and_execute",
        "auto_fix",
        "authorise_auto_fix",
        "confirm_by_customer",
        "approve_by_staff",
    }
)


def _mcp_source_files() -> list[Path]:
    package = Path(__import__("clarity.interfaces.mcp", fromlist=["__file__"]).__file__).parent
    return sorted(package.rglob("*.py"))


def test_the_mcp_package_contains_no_call_to_an_executing_method():
    """A future edit inside mcp/ that executes money movement turns this red.

    The name-based test above only inspects the tool catalogue. This one reads
    the source, so the guarantee survives someone adding a direct call.
    """
    offenders: list[str] = []
    for path in _mcp_source_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            name = None
            if isinstance(node, ast.Call):
                func = node.func
                name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            elif isinstance(node, ast.Attribute):
                name = node.attr
            if name in FORBIDDEN_IN_MCP:
                offenders.append(f"{path.name}:{node.lineno} -> {name}")

    assert offenders == [], "MCP code must not reference an executing method: " + "; ".join(
        offenders
    )


def test_the_object_mcp_holds_exposes_no_way_to_execute(server: ClarityMCPServer):
    """Even by reflection, the view handed to MCP has no execute capability."""
    held = server._cases

    reachable = {name for name in dir(held) if not name.startswith("_")}

    assert not (reachable & FORBIDDEN_IN_MCP), f"reachable: {reachable & FORBIDDEN_IN_MCP}"
    assert "propose" in reachable, "proposing is still allowed"
    assert not hasattr(held, "tools"), "the tool layer must not be reachable"


def test_the_guard_would_catch_a_regression(tmp_path: Path):
    """Proves the AST check actually fails on an offending line."""
    offending = tmp_path / "server.py"
    offending.write_text("def handler(cases):\n    return cases.confirm_and_execute('c', 'p')\n")

    tree = ast.parse(offending.read_text())
    found = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }

    assert found & FORBIDDEN_IN_MCP, "the detection logic must catch this"
