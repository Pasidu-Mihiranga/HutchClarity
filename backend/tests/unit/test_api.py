"""API tests (plan §17).

Two things are being checked: that a channel can drive a whole journey over
HTTP, and that the guards hold at the HTTP boundary - because an attacker
reaches the system here, not through the Python API.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from clarity.app.container import Clarity
from clarity.integration.drivers.mock.world import build_demo_world
from clarity.interfaces.http.main import create_app

DILANI = "+94781234567"  # VAS charged with no consent -> one-tap
NIMAL = "+94782223333"  # duplicate reload -> auto-fix
KUMAR = "+94783334444"  # disclosed FUP cap -> explain only
PRIYA = "+94784445555"  # large reload, SIM swap -> staff approval


@pytest.fixture
def raw_client(tmp_path) -> TestClient:
    """A client with no session, for testing that routes are closed."""
    clarity = Clarity(world=build_demo_world(), verify_base="http://testserver/v")
    return TestClient(create_app(clarity))


def sign_in_customer(client: TestClient, msisdn: str) -> str:
    """Complete the OTP flow and return a bearer token."""
    started = client.post("/v1/auth/otp/request", json={"msisdn": msisdn})
    assert started.status_code == 200, started.text
    code = client.get("/v1/demo/inbox", params={"msisdn": msisdn}).json()["code"]
    session = client.post(
        "/v1/auth/otp/verify",
        json={"challenge_id": started.json()["challenge_id"], "code": code},
    )
    assert session.status_code == 200, session.text
    return session.json()["token"]


def sign_in_staff(
    client: TestClient, user_ref: str, roles: list[str], *, step_up: bool = False
) -> str:
    session = client.post(
        "/v1/auth/staff/session",
        json={"user_ref": user_ref, "roles": roles, "step_up": step_up},
    )
    assert session.status_code == 200, session.text
    return session.json()["token"]


@pytest.fixture
def client(raw_client: TestClient) -> TestClient:
    """A client signed in as staff, so existing journey tests read naturally.

    Staff can act for any subscriber, which is what most of these tests need;
    the customer-specific rules are covered in their own section below.
    """
    token = sign_in_staff(raw_client, "agent-test", ["agent", "supervisor"], step_up=True)
    raw_client.headers["Authorization"] = f"Bearer {token}"
    return raw_client


def open_case(client: TestClient, msisdn: str, **body) -> str:
    response = client.post("/v1/cases", json={"msisdn": msisdn, **body})
    assert response.status_code == 201, response.text
    return response.json()["case_id"]


def evaluate(client: TestClient, case_id: str, **params) -> dict:
    response = client.post(f"/v1/cases/{case_id}/evaluate", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def propose(client: TestClient, case_id: str, **body) -> dict:
    response = client.post(
        f"/v1/cases/{case_id}/proposals", json={"created_by": "channel:web", **body}
    )
    assert response.status_code == 201, response.text
    return response.json()


# --------------------------------------------------------------------------- #
# Service basics
# --------------------------------------------------------------------------- #


def test_health_declares_the_data_is_synthetic(client: TestClient):
    body = client.get("/health").json()

    assert body["status"] == "ok"
    assert body["driver_mode"] == "mock"
    assert "SYNTHETIC" in body["data"]
    # Six at R0, plus the four M-DET added (#35).
    assert len(body["rules"]) == 10


def test_public_keys_are_published_for_verification(client: TestClient):
    body = client.get("/.well-known/clarity-keys.json").json()

    assert body["alg"] == "Ed25519"
    assert body["keys"]


def test_unknown_subscriber_is_rejected(client: TestClient):
    assert client.post("/v1/cases", json={"msisdn": "+94780000000"}).status_code == 404


def test_malformed_number_is_rejected(client: TestClient):
    assert client.post("/v1/cases", json={"msisdn": "nonsense"}).status_code == 422


# --------------------------------------------------------------------------- #
# The Why? journey over HTTP
# --------------------------------------------------------------------------- #


def test_why_returns_a_cause_with_evidence_and_what_was_ruled_out(client: TestClient):
    """Deck S5 step 2: the reason, with evidence and what was ruled out."""
    case_id = open_case(client, DILANI, language="si", channel="app")

    decision = evaluate(client, case_id)

    assert decision["outcome"] == "ONE_TAP_FIX"
    assert decision["cause"]["rule_id"] == "VAS_NO_CONSENT"
    assert decision["amount_lkr"] == "49.00"
    assert decision["ruled_out"], "the customer is told what was excluded"
    assert decision["rationale"], "and why this outcome"


def test_timeline_shows_evidence_and_source_completeness(client: TestClient):
    case_id = open_case(client, DILANI)

    timeline = client.get(f"/v1/cases/{case_id}/timeline").json()

    assert timeline["events"]
    assert len(timeline["sources"]) == 8, "all eight sources report in"
    assert timeline["snapshot_hash"].startswith("sha256:")


def test_one_tap_journey_ends_in_a_verified_receipt(client: TestClient):
    """Confirming is the customer's act, so this journey signs in as them."""
    client.headers["Authorization"] = f"Bearer {sign_in_customer(client, DILANI)}"
    case_id = open_case(client, DILANI, language="si")
    evaluate(client, case_id)
    plan = propose(client, case_id)

    executed = client.post(f"/v1/cases/{case_id}/confirm", json={"plan_id": plan["plan_id"]})

    assert executed.status_code == 200, executed.text
    body = executed.json()
    assert body["status"] == "COMPLETED"
    assert body["confirmed_by"] == "customer_confirmed"
    assert {a["type"] for a in body["actions"]} == {
        "REFUND",
        "DEACTIVATE_VAS",
        "BLOCK_MERCHANT_UNTIL_OPTIN",
    }

    verified = client.post(f"/v1/receipts/{body['receipt_id']}/verify").json()
    assert verified["valid"] and verified["status"] == "VERIFIED"
    assert verified["recurrence_test"] == "PASSED"


def test_duplicate_reload_is_auto_fixed(client: TestClient):
    case_id = open_case(client, NIMAL)
    decision = evaluate(client, case_id)
    assert decision["outcome"] == "AUTO_FIX"
    plan = propose(client, case_id, created_by="clarity-stream-detector")

    body = client.post(f"/v1/cases/{case_id}/auto-fix", json={"plan_id": plan["plan_id"]}).json()

    assert body["confirmed_by"] == "system_auto_fix"
    assert body["actions"][0]["after"] == {"balance_lkr": "7000.00"}


def test_disclosed_cap_is_explained_and_still_gets_a_receipt(client: TestClient):
    """Explain-only still produces proof: nothing was owed, and here is why."""
    case_id = open_case(client, KUMAR, language="ta")
    decision = evaluate(client, case_id)
    assert decision["outcome"] == "EXPLAIN_ONLY"

    receipt = client.post(f"/v1/cases/{case_id}/receipt")

    assert receipt.status_code == 200, receipt.text
    assert receipt.json()["valid"]
    assert receipt.json()["corrected_lkr"] == "0.00"


def test_customer_asking_for_a_person_hands_off(client: TestClient):
    case_id = open_case(client, DILANI)

    decision = evaluate(client, case_id, human=True)

    assert decision["outcome"] == "HANDOFF"
    assert decision["handoff_reason"] == "customer_requested"
    assert decision["allowed_actions"] == []


# --------------------------------------------------------------------------- #
# Guards at the HTTP boundary
# --------------------------------------------------------------------------- #


def test_a_client_cannot_propose_an_action_the_decision_did_not_allow(client: TestClient):
    """The key guard, exercised the way an attacker would reach it."""
    case_id = open_case(client, NIMAL)
    evaluate(client, case_id)  # allows REFUND only

    response = client.post(
        f"/v1/cases/{case_id}/proposals",
        json={"created_by": "attacker", "action_types": ["DEACTIVATE_VAS"]},
    )

    assert response.status_code == 403
    assert response.json()["code"] == "ACTION_NOT_ALLOWED_BY_POLICY"


def test_an_explain_only_case_cannot_be_turned_into_a_refund(client: TestClient):
    case_id = open_case(client, KUMAR)
    evaluate(client, case_id)

    response = client.post(f"/v1/cases/{case_id}/proposals", json={"created_by": "attacker"})

    assert response.status_code == 409
    assert response.json()["code"] == "OUTCOME_NOT_EXECUTABLE"


def test_a_staff_case_cannot_be_confirmed_as_if_by_the_customer(client: TestClient):
    """Priya's case needs a supervisor; a customer tap must not substitute."""
    client.headers["Authorization"] = f"Bearer {sign_in_customer(client, PRIYA)}"
    case_id = open_case(client, PRIYA)
    evaluate(client, case_id)
    plan = propose(client, case_id)

    response = client.post(f"/v1/cases/{case_id}/confirm", json={"plan_id": plan["plan_id"]})

    assert response.status_code == 403
    assert response.json()["code"] == "CONFIRMATION_REQUIRED"


def test_a_one_tap_case_cannot_self_authorise_as_auto_fix(client: TestClient):
    case_id = open_case(client, DILANI)
    evaluate(client, case_id)
    plan = propose(client, case_id)

    response = client.post(f"/v1/cases/{case_id}/auto-fix", json={"plan_id": plan["plan_id"]})

    assert response.status_code == 403


def test_a_plan_cannot_be_executed_twice(client: TestClient):
    """A repeated confirm replays the original outcome (D1): same receipt, no new action.

    It used to answer 409 PLAN_NOT_PENDING, so a customer who double-tapped saw
    an error after a successful fix, and a concurrent double tap could issue a
    second signed receipt for the same refund.
    """
    client.headers["Authorization"] = f"Bearer {sign_in_customer(client, DILANI)}"
    case_id = open_case(client, DILANI)
    evaluate(client, case_id)
    plan = propose(client, case_id)
    first = client.post(f"/v1/cases/{case_id}/confirm", json={"plan_id": plan["plan_id"]})

    repeat = client.post(f"/v1/cases/{case_id}/confirm", json={"plan_id": plan["plan_id"]})

    assert first.status_code == 200 and repeat.status_code == 200
    assert repeat.json()["receipt_id"] == first.json()["receipt_id"]
    first_actions = [a["action_id"] for a in first.json()["actions"]]
    assert [a["action_id"] for a in repeat.json()["actions"]] == first_actions


def test_acting_before_evaluating_is_refused(client: TestClient):
    case_id = open_case(client, DILANI)

    response = client.post(f"/v1/cases/{case_id}/proposals", json={"created_by": "web"})

    assert response.status_code == 409
    assert response.json()["code"] == "CASE_NOT_READY"


def test_unknown_case_is_a_404(client: TestClient):
    assert client.get("/v1/cases/CASE-nope").status_code == 404


def test_unknown_receipt_is_a_404(client: TestClient):
    assert client.post("/v1/receipts/TR-2027-999999/verify").status_code == 404


# --------------------------------------------------------------------------- #
# Desk
# --------------------------------------------------------------------------- #


def test_staff_approval_completes_the_case(client: TestClient):
    case_id = open_case(client, PRIYA)
    evaluate(client, case_id)
    plan = propose(client, case_id, created_by="agent-7")

    response = client.post(
        f"/v1/cases/{case_id}/approve",
        json={"plan_id": plan["plan_id"], "role": "supervisor"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["confirmed_by"] == "staff_approved"


def test_approval_without_mfa_is_refused(raw_client: TestClient):
    """Step-up is read from the session, so a stale one cannot approve.

    The caller cannot assert it either: `mfa_step_up` is not a request field.
    """
    token = sign_in_staff(raw_client, "sup-stale", ["agent", "supervisor"], step_up=False)
    raw_client.headers["Authorization"] = f"Bearer {token}"
    case_id = open_case(raw_client, PRIYA)
    evaluate(raw_client, case_id)
    plan = propose(raw_client, case_id, created_by="agent-7")

    response = raw_client.post(
        f"/v1/cases/{case_id}/approve",
        json={"plan_id": plan["plan_id"], "role": "supervisor"},
    )

    assert response.status_code == 403


def test_a_role_the_caller_does_not_hold_cannot_be_used_to_approve(client: TestClient):
    """Otherwise one person satisfies four-eyes by naming two roles."""
    case_id = open_case(client, PRIYA)
    evaluate(client, case_id)
    plan = propose(client, case_id, created_by="agent-7")

    response = client.post(
        f"/v1/cases/{case_id}/approve",
        json={"plan_id": plan["plan_id"], "role": "finance"},
    )

    assert response.status_code == 403
    assert "finance" in response.json()["detail"]


def test_queue_lists_cases_needing_a_person_biggest_first(client: TestClient):
    for msisdn in (DILANI, PRIYA):
        case_id = open_case(client, msisdn)
        evaluate(client, case_id)

    queue = client.get("/v1/desk/queue").json()

    assert len(queue) == 1, "only the staff case waits for a person"
    assert queue[0]["money_at_stake_lkr"] == "12000.00"
    assert queue[0]["reason"]


def test_openapi_document_is_generated(client: TestClient):
    """Guidelines §3: reviewers need to understand the API without us."""
    spec = client.get("/openapi.json").json()

    assert spec["info"]["title"] == "Hutch Clarity API"
    assert "/v1/cases" in spec["paths"]


# --------------------------------------------------------------------------- #
# Re-reading a case must not change it
# --------------------------------------------------------------------------- #


def test_reading_a_decided_case_does_not_re_decide_it(client: TestClient):
    """A Desk agent opening a case must not change its outcome by looking.

    Found by driving the real UI: the Desk re-evaluates when it opens a case,
    which used to attempt an illegal state transition and return a 500.
    """
    case_id = open_case(client, PRIYA)
    first = evaluate(client, case_id)

    second = evaluate(client, case_id)

    assert second["decision_id"] == first["decision_id"]
    assert second["outcome"] == first["outcome"]


def test_a_case_can_be_reopened_repeatedly_without_error(client: TestClient):
    case_id = open_case(client, DILANI)
    evaluate(client, case_id)

    for _ in range(3):
        assert client.post(f"/v1/cases/{case_id}/evaluate").status_code == 200


def test_an_executed_case_keeps_the_decision_its_receipt_cites(client: TestClient):
    case_id = open_case(client, DILANI)
    original = evaluate(client, case_id)
    plan = propose(client, case_id)
    client.post(f"/v1/cases/{case_id}/confirm", json={"plan_id": plan["plan_id"]})

    after = evaluate(client, case_id)

    assert after["decision_id"] == original["decision_id"]


# --------------------------------------------------------------------------- #
# Demo reset
# --------------------------------------------------------------------------- #


def test_reset_restores_the_synthetic_world(client: TestClient):
    """A demo has to be runnable twice in front of judges."""
    client.headers["Authorization"] = f"Bearer {sign_in_customer(client, DILANI)}"
    case_id = open_case(client, DILANI)
    evaluate(client, case_id)
    plan = propose(client, case_id)
    client.post(f"/v1/cases/{case_id}/confirm", json={"plan_id": plan["plan_id"]})

    balance_after_refund = next(
        p["balance_lkr"] for p in client.get("/v1/demo/subscribers").json() if p["msisdn"] == DILANI
    )
    assert balance_after_refund == "500.00"

    assert client.post("/v1/demo/reset").status_code == 200

    restored = next(
        p["balance_lkr"] for p in client.get("/v1/demo/subscribers").json() if p["msisdn"] == DILANI
    )
    assert restored == "451.00", "balances are back to their starting values"

    # The queue is staff-only, and a customer session must survive a reset:
    # identity is not demo data.
    client.headers["Authorization"] = f"Bearer {sign_in_staff(client, 'sup-check', ['supervisor'])}"
    assert client.get("/v1/desk/queue").json() == [], "and no cases are left over"


# --------------------------------------------------------------------------- #
# AI explanation and MCP exposure
# --------------------------------------------------------------------------- #


def test_the_decision_carries_a_customer_facing_explanation(client: TestClient):
    case_id = open_case(client, DILANI, language="si")

    decision = evaluate(client, case_id)

    assert decision["explanation"], "the customer needs words, not only a rule id"
    assert "49.00" in decision["explanation"]
    assert decision["explanation_source"] == "template"


def test_the_explanation_is_in_the_language_that_was_asked_for(client: TestClient):
    tamil = evaluate(client, open_case(client, KUMAR, language="ta"))
    english = evaluate(client, open_case(client, KUMAR, language="en"))

    assert any("஀" <= ch <= "௿" for ch in tamil["explanation"]), "expected Tamil"
    assert tamil["explanation"] != english["explanation"]


def test_ai_usage_is_reported_honestly(client: TestClient):
    evaluate(client, open_case(client, DILANI))

    usage = client.get("/v1/ai/usage").json()

    assert usage["total_tokens"] == 0
    assert usage["llm_free_share"] == 1.0
    assert "works without the" in usage["note"]


def test_mcp_exposes_no_executing_tool(client: TestClient):
    body = client.get("/v1/mcp/tools").json()

    names = {t["name"] for t in body["tools"]}
    assert "propose_action" in names
    assert not any("execute" in n or "confirm" in n or "approve" in n for n in names)
    assert all(t["level"] != "L4" for t in body["tools"])


def test_mcp_staff_profile_sees_more_than_a_customer(client: TestClient):
    customer = {t["name"] for t in client.get("/v1/mcp/tools").json()["tools"]}
    staff = {
        t["name"]
        for t in client.get("/v1/mcp/tools", params={"profile": "staff-assist"}).json()["tools"]
    }

    assert customer < staff


def test_an_unknown_mcp_profile_is_rejected(client: TestClient):
    assert client.get("/v1/mcp/tools", params={"profile": "root"}).status_code == 422


# --------------------------------------------------------------------------- #
# Runtime profiles (improvement plan 2.3)
# --------------------------------------------------------------------------- #


def test_the_default_profile_needs_no_infrastructure():
    from clarity.app.container import Clarity, Profile

    assert Clarity(world=build_demo_world()).profile is Profile.DEMO


def test_the_full_profile_refuses_a_non_postgresql_database(tmp_path):
    """FULL needs PostgreSQL for Clarity's own state (B05).

    It used to accept a SQLite file, which loaded the simulated HUTCH world but
    left Clarity's own state in memory. That looked like success and gave a
    deployment two replicas could not share, so it is now refused with the
    reason. The simulated world still runs on SQLite in the demo profile.
    """
    from clarity.app.container import Clarity, Profile
    from clarity.app.settings import Settings, SettingsInvalid

    settings = Settings(
        CLARITY_PROFILE="full",
        DATABASE_URL=f"sqlite+pysqlite:///{tmp_path / 'full.db'}",
        _env_file=None,
    )

    with pytest.raises(SettingsInvalid, match="PostgreSQL"):
        Clarity(profile=Profile.FULL, settings=settings)


def test_only_the_composition_root_reads_the_profile():
    """Business code that branches on the profile is how drivers drift apart.

    The composition root is ``clarity.app``: ``settings.py`` declares the
    variable and ``container.py`` turns it into driver choices (B07). Anything
    else naming it would be business code deciding its own wiring, which I20
    forbids.
    """
    import pathlib

    root = pathlib.Path(__import__("clarity").__file__).parent
    composition_root = {"app/settings.py", "app/container.py"}
    offenders = [
        str(path.relative_to(root))
        for path in root.rglob("*.py")
        if "CLARITY_PROFILE" in path.read_text(encoding="utf-8")
        and str(path.relative_to(root)) not in composition_root
    ]

    assert offenders == [], f"CLARITY_PROFILE read outside the composition root: {offenders}"
