"""Smoke tests for case, receipts, customer, timeline, actions, reconciliation."""

from __future__ import annotations

from clarity.modules.actions.public import (
    approve_action,
    confirm_action,
    execute_action,
    propose_action,
    reset_actions,
)
from clarity.modules.case.public import create_case, get_case, handoff, list_queue, reset_cases
from clarity.modules.customer.public import get_safeguards, put_safeguards, reset_safeguards
from clarity.modules.receipts.public import (
    issue_receipt,
    replay_receipt,
    reset_receipts,
    verify_receipt,
)
from clarity.modules.reconciliation.public import (
    add_adapter_confirmation,
    reset_reconciliation,
    run_reconciliation,
)
from clarity.modules.timeline.public import build_timeline


def setup_function() -> None:
    reset_cases()
    reset_safeguards()
    reset_actions()
    reset_receipts()
    reset_reconciliation()


def test_customer_safeguards_roundtrip() -> None:
    ref = "sub_demo_001"
    defaults = get_safeguards(ref)
    assert defaults.subscriber_ref == ref
    assert defaults.allow_auto_refund is True

    updated = put_safeguards(
        ref,
        spend_cap_lkr="1000.00",
        language="si",
        allow_auto_refund=False,
        quiet_hours={"start_hour": 22, "end_hour": 6, "enabled": True},
    )
    assert str(updated.spend_cap_lkr) == "1000.00"
    assert updated.language.value == "si"
    assert updated.allow_auto_refund is False
    assert get_safeguards(ref).quiet_hours.start_hour == 22


def test_case_create_queue_handoff() -> None:
    case = create_case(
        subscriber_ref="sub_demo",
        channel="whatsapp",
        message="why was I charged?",
        amount_lkr="499.00",
        decision={"outcome": "HANDOFF", "amount_lkr": "499.00"},
    )
    assert case.id.startswith("CAS-")
    assert get_case(case.id).case_no.startswith("CASE-")

    queue = list_queue()
    assert any(item["id"] == case.id for item in queue)
    assert queue[0]["smart_score"] >= 0

    handed = handoff(case.id, reason="customer_requested", note="please help")
    assert handed.status.value == "handed_off"
    assert handed.handoff_reason == "customer_requested"


def test_timeline_eight_sources() -> None:
    world = {
        "payments": [{"id": "p1", "amount_lkr": "100.00"}],
        "charging": [],
        "catalogue": {"events": [{"sku": "pack-a"}], "completeness": "complete"},
        "vas_consent": None,
        # loans / crm / identity / usage_fup omitted → missing
    }
    timeline = build_timeline("sub_demo", world=world)
    assert set(timeline["sources"]) == {
        "payments",
        "charging",
        "catalogue",
        "vas_consent",
        "usage_fup",
        "loans",
        "crm",
        "identity",
    }
    assert timeline["payments"]["count"] == 1
    assert timeline["charging"]["completeness"] == "complete"
    assert timeline["loans"]["completeness"] == "missing"
    assert timeline["completeness"]["total_sources"] == 8


def test_actions_propose_confirm_execute_idempotent() -> None:
    proposed = propose_action(
        action_type="refund",
        subscriber_ref="sub_demo",
        case_id="CAS-1",
        amount_lkr="100.00",
    )
    assert proposed["status"] == "proposed"

    confirmed = confirm_action(proposed["action_id"], subscriber_ref="sub_demo")
    assert confirmed["status"] == "confirmed"
    token = confirmed["confirmation_token"]

    first = execute_action(
        proposed["action_id"],
        idempotency_key="idem-1",
        confirmation_token=token,
    )
    assert first["status"] == "completed"
    second = execute_action(
        proposed["action_id"],
        idempotency_key="idem-1",
        confirmation_token=token,
    )
    assert second["action_id"] == first["action_id"]
    assert second["result"] == first["result"]


def test_actions_approve_path() -> None:
    proposed = propose_action(
        action_type="cancel_vas",
        subscriber_ref="sub_demo",
        params={"subscription_id": "vas-9"},
    )
    approved = approve_action(proposed["action_id"], approver_ref="agent-1")
    assert approved["status"] == "approved"
    done = execute_action(proposed["action_id"], idempotency_key="idem-vas-1")
    assert done["status"] == "completed"
    assert done["result"]["op"] == "cancel_vas"


def test_receipt_issue_verify_replay() -> None:
    issued = issue_receipt(
        subscriber_ref="sub_demo",
        summary="Returned LKR 100.00 for duplicate charge",
        case_id="CAS-1",
        action_type="refund",
        amount_lkr="100.00",
    )
    rid = issued["receipt_id"]
    assert rid.startswith("TR-")
    assert issued["html"] and "Trust Receipt" in issued["html"]

    verification = verify_receipt(rid)
    assert verification["valid"] is True
    assert verification["display"] == "VERIFIED"
    assert verification["chain_ok"] is True

    replayed = replay_receipt(rid)
    assert replayed["receipt"]["receipt_id"] == rid
    assert replayed["verification"]["valid"] is True


def test_reconciliation_detects_missing_confirmation() -> None:
    proposed = propose_action(
        action_type="credit",
        subscriber_ref="sub_demo",
        amount_lkr="50.00",
    )
    confirm_action(proposed["action_id"], subscriber_ref="sub_demo")
    executed = execute_action(proposed["action_id"], idempotency_key="idem-credit-1")

    day = executed["executed_at"][:10]
    mismatches = run_reconciliation(day)
    assert any(m["reason"] == "missing_confirmation" for m in mismatches)

    add_adapter_confirmation(
        {
            "confirmation_ref": executed["result"]["confirmation_ref"],
            "amount_lkr": "50.00",
            "accepted": True,
            "day": day,
        }
    )
    clean = run_reconciliation(day)
    assert not any(
        m["reason"] == "missing_confirmation" and m["action_id"] == executed["action_id"]
        for m in clean
    )


def test_module_class_names_importable() -> None:
    from clarity.modules.actions.module import ActionsModule
    from clarity.modules.case.module import CaseModule
    from clarity.modules.customer.module import CustomerModule
    from clarity.modules.receipts.module import ReceiptsModule
    from clarity.modules.reconciliation.module import ReconciliationModule
    from clarity.modules.timeline.module import TimelineModule

    assert CustomerModule.name == "customer"
    assert CaseModule.name == "case"
    assert TimelineModule.name == "timeline"
    assert ActionsModule.name == "actions"
    assert ReceiptsModule.name == "receipts"
    assert ReconciliationModule.name == "reconciliation"
