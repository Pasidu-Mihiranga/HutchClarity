"""The four demo journeys over HTTP, end to end (R0).

These are the behaviours the migration must never change: who can do what, which
outcome each synthetic customer gets, and that every fix ends in a receipt
anyone can verify.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from .conftest import DILANI, KUMAR, NIMAL, PRIYA, bearer, customer_token, staff_token


def _open_and_evaluate(api: TestClient, headers: dict[str, str], msisdn: str, **body: object):
    opened = api.post("/v1/cases", json={"msisdn": msisdn, **body}, headers=headers)
    assert opened.status_code == 201, opened.text
    case_id = opened.json()["case_id"]
    decided = api.post(f"/v1/cases/{case_id}/evaluate", headers=headers)
    assert decided.status_code == 200, decided.text
    return case_id, decided.json()


def _propose(api: TestClient, headers: dict[str, str], case_id: str, created_by: str) -> str:
    plan = api.post(
        f"/v1/cases/{case_id}/proposals", json={"created_by": created_by}, headers=headers
    )
    assert plan.status_code == 201, plan.text
    return str(plan.json()["plan_id"])


def _verified(api: TestClient, receipt_id: str) -> dict[str, object]:
    """Public check, exactly what the QR code opens: no credentials."""
    result = api.post(f"/v1/receipts/{receipt_id}/verify")
    assert result.status_code == 200, result.text
    body: dict[str, object] = result.json()
    return body


def test_vas_without_consent_one_tap_fix_and_verified_receipt(api: TestClient):
    me = bearer(customer_token(api, DILANI))
    case_id, decision = _open_and_evaluate(api, me, DILANI, channel="app", language="si")

    assert decision["outcome"] == "ONE_TAP_FIX"
    assert decision["amount_lkr"] == "49.00"
    plan_id = _propose(api, me, case_id, "channel:web")

    first = api.post(f"/v1/cases/{case_id}/confirm", json={"plan_id": plan_id}, headers=me)
    again = api.post(f"/v1/cases/{case_id}/confirm", json={"plan_id": plan_id}, headers=me)

    assert first.status_code == 200, first.text
    assert first.json()["confirmed_by"] == "customer_confirmed"
    # A second tap replays the original outcome: same receipt, no new action (D1).
    assert again.status_code == 200
    assert again.json()["receipt_id"] == first.json()["receipt_id"]
    verdict = _verified(api, first.json()["receipt_id"])
    assert verdict["valid"] is True and verdict["status"] == "VERIFIED"


def test_duplicate_reload_is_fixed_with_no_human(api: TestClient):
    staff = bearer(staff_token(api, "ops:stream", ["supervisor"], step_up=True))
    case_id, decision = _open_and_evaluate(api, staff, NIMAL)

    assert decision["outcome"] == "AUTO_FIX"
    plan_id = _propose(api, staff, case_id, "clarity-stream-detector")
    fixed = api.post(f"/v1/cases/{case_id}/auto-fix", json={"plan_id": plan_id}, headers=staff)

    assert fixed.status_code == 200, fixed.text
    assert fixed.json()["confirmed_by"] == "system_auto_fix"
    assert _verified(api, fixed.json()["receipt_id"])["valid"] is True


def test_disclosed_fair_use_cap_is_explained_not_refunded(api: TestClient):
    me = bearer(customer_token(api, KUMAR))
    case_id, decision = _open_and_evaluate(api, me, KUMAR, language="ta")

    assert decision["outcome"] == "EXPLAIN_ONLY"
    proof = api.post(f"/v1/cases/{case_id}/receipt", headers=me)

    assert proof.status_code == 200, proof.text
    assert proof.json()["valid"] is True
    assert proof.json()["corrected_lkr"] == "0.00"


def test_large_disputed_reload_needs_a_stepped_up_staff_approval(api: TestClient):
    agent = bearer(staff_token(api, "agent:nadeesha", ["agent"], step_up=False))
    case_id, decision = _open_and_evaluate(api, agent, PRIYA)
    assert decision["outcome"] == "STAFF_APPROVAL"
    plan_id = _propose(api, agent, case_id, "agent:nadeesha")

    without_step_up = bearer(staff_token(api, "sup:ruwan", ["supervisor"], step_up=False))
    refused = api.post(
        f"/v1/cases/{case_id}/approve",
        json={"plan_id": plan_id, "role": "supervisor"},
        headers=without_step_up,
    )
    stepped_up = bearer(staff_token(api, "sup:ruwan", ["supervisor"], step_up=True))
    approved = api.post(
        f"/v1/cases/{case_id}/approve",
        json={"plan_id": plan_id, "role": "supervisor"},
        headers=stepped_up,
    )

    assert refused.status_code == 403
    assert approved.status_code == 200, approved.text
    assert approved.json()["confirmed_by"] == "staff_approved"


def test_a_customer_cannot_read_another_customers_case(api: TestClient):
    dilani = bearer(customer_token(api, DILANI))
    case_id, _ = _open_and_evaluate(api, dilani, DILANI)

    kumar = bearer(customer_token(api, KUMAR))

    assert api.get(f"/v1/cases/{case_id}", headers=kumar).status_code in {403, 404}
    assert api.get(f"/v1/cases/{case_id}", headers=dilani).status_code == 200


def test_ai_and_mcp_never_hold_an_executing_tool(api: TestClient):
    tools = api.get("/v1/mcp/tools", params={"profile": "staff-assist"}).json()["tools"]
    names = {tool["name"] for tool in tools}

    assert names, "the staff profile lists its tools"
    assert not {n for n in names if any(w in n for w in ("execute", "confirm", "approve"))}
    assert api.get("/v1/ai/usage").status_code == 200


def test_only_a_customer_has_a_me_and_each_action_needs_its_named_permission(api: TestClient):
    """I9: every /v1/me route declares self:read, self:settings or self:transact."""
    me = bearer(customer_token(api, DILANI))
    staff = bearer(staff_token(api, "sup:ruwan", ["supervisor", "finance"], step_up=True))

    assert api.get("/v1/me/home", headers=me).status_code == 200
    assert api.post("/v1/me/preferences", json={"language": "si"}, headers=me).status_code == 200
    assert api.post("/v1/me/reload", json={"amount_lkr": "100"}, headers=me).status_code == 200

    for method, path, body in [
        ("GET", "/v1/me/home", None),
        ("POST", "/v1/me/preferences", {"language": "si"}),
        ("POST", "/v1/me/reload", {"amount_lkr": "100"}),
    ]:
        assert api.request(method, path, json=body, headers=staff).status_code == 403, path
