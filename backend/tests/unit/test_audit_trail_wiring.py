"""One persisted audit trail, wired into the application (W1, ADR-0034).

``test_events_and_audit.py`` covers the ledger on its own. These cover what
the audit assurance plan found missing around it: domain events never reached
the trail, MCP calls were kept in a list inside the MCP process, a demo reset
built a fresh store and so a fresh, empty trail, and nothing checked the chain
before a process started adding to it.
"""

from __future__ import annotations

import pytest

from clarity.app.container import AuditChainBroken, Clarity
from clarity.app.settings import Settings
from clarity.integration.drivers.mock.world import build_demo_world, ref_for
from clarity.interfaces.mcp.server import ClarityMCPServer, Principal, Profile
from clarity.kernel.common import Channel
from clarity.platform.audit.ledger import AUDIT, ActorKind, AuditEventType

from ..acceptance.conftest import DILANI


@pytest.fixture
def clarity() -> Clarity:
    return Clarity(world=build_demo_world())


def open_and_evaluate(clarity: Clarity) -> str:
    account = clarity.world.account(ref_for(DILANI))
    assert account is not None
    case = clarity.cases.open_case(
        subscriber_ref=account.ref, msisdn_masked=account.masked, channel=Channel.APP
    )
    clarity.cases.evaluate(case.case_id)
    return case.case_id


def test_a_process_records_that_it_opened_a_verified_trail(clarity: Clarity):
    opened = clarity.audit.of_type(AuditEventType.LEDGER_OPENED)

    assert len(opened) == 1
    assert opened[0].detail["intact"] is True


def test_domain_events_reach_the_trail_from_the_outbox(clarity: Clarity):
    """Before W1 a decision or a new case was published and never audited."""
    case_id = open_and_evaluate(clarity)

    clarity.deliver_events()

    recorded = clarity.audit.for_case(case_id)
    kinds = {record.event_type for record in recorded}
    assert AuditEventType.DECISION_MADE in kinds
    assert any(r.detail.get("event_type") == "case.created" for r in recorded)
    assert all(record.actor_kind is ActorKind.SYSTEM for record in recorded)
    assert clarity.audit.verify().intact


def test_a_redelivered_event_is_recorded_once(clarity: Clarity):
    """At-least-once delivery must not mean at-least-once auditing."""
    open_and_evaluate(clarity)
    clarity.deliver_events()
    before = len(clarity.audit)
    already_delivered = clarity.relay.published_events()[-1]

    # The relay's one honest failure: it published, then died before marking
    # the row sent, so the same event goes out again.
    clarity.bus.publish(already_delivered)
    clarity.bus.drain()

    assert len(clarity.audit) == before


def test_the_trail_survives_a_demo_reset_and_records_it(clarity: Clarity):
    """A reset that erased the trail would be the easiest way to hide anything."""
    open_and_evaluate(clarity)
    clarity.deliver_events()
    head_before = clarity.audit.head
    length_before = len(clarity.audit)

    fresh = clarity.reset()

    assert fresh.audit is clarity.audit
    records = fresh.audit.records
    assert len(records) > length_before
    assert records[length_before - 1].chain_hash == head_before
    assert records[length_before].event_type is AuditEventType.DEMO_RESET
    assert fresh.audit.verify().intact


def test_an_mcp_call_lands_in_the_shared_trail(clarity: Clarity):
    """It used to be kept in a list inside the MCP process only."""
    case_id = open_and_evaluate(clarity)
    server = ClarityMCPServer(clarity.mcp_view, ledger=clarity.audit)
    principal = Principal(ref="session-1", profile=Profile.CUSTOMER_ASSIST, case_id=case_id)

    server.call(principal, "propose_action", {"case_id": case_id, "action_type": "REFUND"})

    calls = clarity.audit.of_type(AuditEventType.MCP_INVOKED)
    assert len(calls) == 1
    assert calls[0].actor_ref == "session-1"
    assert calls[0].actor_kind is ActorKind.AGENT
    assert calls[0].object_ref == "propose_action"
    assert "args" not in calls[0].detail, "arguments are hashed, never stored"


def _break_the_trail(clarity: Clarity) -> None:
    """Play the insider: edit a stored record behind the ledger's back.

    ``as_custodian`` because the ordinary write path refuses to overwrite an
    audit row now (W1), which is the layer that stops Clarity's own code doing
    this. These tests are about the layer underneath: what a process does at
    startup when someone with table access has already done it anyway.
    """
    first = clarity.audit.records[0]
    with clarity.open_unit() as unit, unit.as_custodian():
        unit.repository(AUDIT).put(
            str(first.seq).zfill(12), first.model_copy(update={"actor_ref": "someone-else"})
        )
        unit.commit()


def test_a_broken_trail_stops_the_process_from_serving(clarity: Clarity):
    _break_the_trail(clarity)

    with pytest.raises(AuditChainBroken, match="broken at seq 1"):
        Clarity(world=build_demo_world(), audit=clarity.audit)


def test_break_glass_starts_anyway_and_says_so(clarity: Clarity):
    _break_the_trail(clarity)

    started = Clarity(
        world=build_demo_world(),
        audit=clarity.audit,
        settings=Settings(CLARITY_AUDIT_BREAK_GLASS=True),
    )

    opened = started.audit.of_type(AuditEventType.LEDGER_OPENED)[-1]
    assert opened.detail["break_glass"] is True
    assert opened.detail["intact"] is False
