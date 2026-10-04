"""Who did what: identity, access and request coverage in the trail (W2).

Two kinds of test here.

**The coverage contract.** Every state-changing route is either recorded as
``request.performed`` or listed in ``NOT_RECORDED_AS_REQUESTS`` with a reason.
A new route that is neither fails the build, as a route without a permission
already does (I9). And every recorded route is *driven* here, not just listed:
a declaration nobody exercises is the box-ticking the plan warns about.

**Identity and access.** Sign-in, failed codes, staff sessions, refresh,
denials and rejected tokens, none of which the trail held before W2, and the
gap that made this necessary: an approval's domain event names a mode
(``staff_approved``), never the supervisor who approved.
"""

from __future__ import annotations

import json
import re

import pytest
from fastapi.testclient import TestClient

from clarity.app.container import Clarity
from clarity.integration.drivers.mock.world import build_demo_world
from clarity.interfaces.http.main import create_app
from clarity.interfaces.http.trail import NOT_RECORDED_AS_REQUESTS, STATE_CHANGING
from clarity.platform.audit.ledger import AuditEventType, AuditRecord

from ..acceptance.conftest import DILANI, PRIYA


@pytest.fixture
def clarity() -> Clarity:
    return Clarity(world=build_demo_world())


@pytest.fixture
def api(clarity: Clarity) -> TestClient:
    return TestClient(create_app(clarity))


def staff(api: TestClient, user: str, roles: list[str], *, step_up: bool = False) -> dict[str, str]:
    session = api.post(
        "/v1/auth/staff/session", json={"user_ref": user, "roles": roles, "step_up": step_up}
    )
    assert session.status_code == 200, session.text
    return {"Authorization": f"Bearer {session.json()['token']}"}


def customer(api: TestClient, msisdn: str) -> dict[str, str]:
    started = api.post("/v1/auth/otp/request", json={"msisdn": msisdn})
    assert started.status_code == 200, started.text
    code = api.get("/v1/auth/otp/inbox", params={"msisdn": msisdn}).json()["code"]
    verified = api.post(
        "/v1/auth/otp/verify",
        json={"challenge_id": started.json()["challenge_id"], "code": code},
    )
    assert verified.status_code == 200, verified.text
    return {"Authorization": f"Bearer {verified.json()['token']}"}


def of(clarity: Clarity, event_type: AuditEventType) -> list[AuditRecord]:
    return clarity.audit.of_type(event_type)


def state_changing_routes(api: TestClient) -> list[tuple[str, str]]:
    found = []
    for route in api.app.routes:  # type: ignore[attr-defined]
        for method in sorted(getattr(route, "methods", None) or ()):
            if method in STATE_CHANGING:
                found.append((method, route.path))
    return found


def _app_routes() -> list[tuple[str, str]]:
    return state_changing_routes(TestClient(create_app(Clarity(world=build_demo_world()))))


RECORDED = [
    (method, path)
    for method, path in _app_routes()
    if f"{method} {path}" not in NOT_RECORDED_AS_REQUESTS
]


# --------------------------------------------------------------------------- #
# The coverage contract
# --------------------------------------------------------------------------- #


def test_every_exemption_names_a_real_route_and_gives_a_reason(api: TestClient):
    """A stale exemption would silently exempt whatever route takes its name next."""
    real = {f"{method} {path}" for method, path in state_changing_routes(api)}

    stale = set(NOT_RECORDED_AS_REQUESTS) - real
    assert stale == set(), f"exemptions for routes that no longer exist: {stale}"
    assert all(reason.strip() for reason in NOT_RECORDED_AS_REQUESTS.values())


def test_most_state_changing_routes_are_recorded_not_exempted():
    """Exemption is for sign-in (recorded its own way) and reads that use POST."""
    assert len(RECORDED) >= 20


@pytest.mark.parametrize(("method", "path"), RECORDED, ids=[f"{m} {p}" for m, p in RECORDED])
def test_driving_a_recorded_route_leaves_a_record_naming_it(
    api: TestClient, clarity: Clarity, method: str, path: str
):
    """Whatever the outcome, accepted, refused or invalid, the attempt is in the trail.

    Driven with an empty body and placeholder ids, as a signed-in agent, so
    most of these are refused or rejected. That is the point: a refusal is a
    record too, either ``request.performed`` with its status or
    ``access.denied`` with its reason.
    """
    headers = staff(api, "agent:coverage", ["agent"])
    concrete = re.sub(r"\{[^}]+\}", "X-placeholder", path)

    api.request(method, concrete, json={}, headers=headers)

    route = f"{method} {path}"
    named = [
        record
        for record in (
            of(clarity, AuditEventType.REQUEST_PERFORMED)
            + of(clarity, AuditEventType.ACCESS_DENIED)
        )
        if record.object_ref == route
    ]
    assert named, f"{route} left no record in the trail"
    assert named[-1].actor_ref == "agent:coverage"


# --------------------------------------------------------------------------- #
# Who approved: the gap domain events cannot close
# --------------------------------------------------------------------------- #


def test_an_approval_records_the_supervisor_who_made_it(api: TestClient, clarity: Clarity):
    agent = staff(api, "agent:nadeesha", ["agent"])
    opened = api.post("/v1/cases", json={"msisdn": PRIYA}, headers=agent)
    case_id = opened.json()["case_id"]
    api.post(f"/v1/cases/{case_id}/evaluate", headers=agent)
    plan_id = api.post(
        f"/v1/cases/{case_id}/proposals", json={"created_by": "agent:nadeesha"}, headers=agent
    ).json()["plan_id"]

    supervisor = staff(api, "sup:ruwan", ["supervisor"], step_up=True)
    approved = api.post(
        f"/v1/cases/{case_id}/approve",
        json={"plan_id": plan_id, "role": "supervisor"},
        headers=supervisor,
    )
    assert approved.status_code == 200, approved.text

    approvals = [
        r
        for r in of(clarity, AuditEventType.REQUEST_PERFORMED)
        if r.object_ref == "POST /v1/cases/{case_id}/approve"
    ]
    assert len(approvals) == 1
    record = approvals[0]
    assert record.actor_ref == "sup:ruwan"
    assert record.actor_kind == "staff"
    assert record.case_id == case_id
    assert record.detail["assurance"] == "mfa-recent"

    # And the session that approved is the one that signed in with step-up.
    started = [
        r for r in of(clarity, AuditEventType.STAFF_SESSION_STARTED) if r.actor_ref == "sup:ruwan"
    ]
    assert started[-1].session_ref == record.session_ref
    assert started[-1].detail["step_up"] is True


# --------------------------------------------------------------------------- #
# Identity and access events
# --------------------------------------------------------------------------- #


def test_a_customer_sign_in_is_recorded_without_the_number(api: TestClient, clarity: Clarity):
    headers = customer(api, DILANI)
    api.get("/v1/me/app", headers=headers)

    requested = of(clarity, AuditEventType.OTP_REQUESTED)
    verified = of(clarity, AuditEventType.OTP_VERIFIED)
    assert requested[-1].detail["outcome"] == "sent"
    assert verified[-1].actor_kind == "customer"
    assert verified[-1].session_ref is not None


def test_a_wrong_code_is_recorded_and_the_code_is_not(api: TestClient, clarity: Clarity):
    started = api.post("/v1/auth/otp/request", json={"msisdn": DILANI}).json()
    real = api.get("/v1/auth/otp/inbox", params={"msisdn": DILANI}).json()["code"]
    wrong = "000000" if real != "000000" else "111111"

    refused = api.post(
        "/v1/auth/otp/verify", json={"challenge_id": started["challenge_id"], "code": wrong}
    )

    assert refused.status_code == 401
    failed = of(clarity, AuditEventType.OTP_FAILED)
    assert len(failed) == 1
    assert failed[0].object_ref == started["challenge_id"]
    assert wrong not in json.dumps(failed[0].detail)


def test_a_request_for_an_unknown_number_is_recorded_masked(api: TestClient, clarity: Clarity):
    api.post("/v1/auth/otp/request", json={"msisdn": "+94770000001"})

    requested = of(clarity, AuditEventType.OTP_REQUESTED)
    assert requested[-1].detail["outcome"] == "unknown_number"
    assert "+94770000001" not in requested[-1].actor_ref


def test_a_refused_request_records_who_was_refused_and_why(api: TestClient, clarity: Clarity):
    auditor = staff(api, "aud:kamal", ["auditor"])

    refused = api.post(
        "/v1/admin/switches", json={"key": "auto_fix_global", "enabled": False}, headers=auditor
    )

    assert refused.status_code == 403
    denied = of(clarity, AuditEventType.ACCESS_DENIED)[-1]
    assert denied.actor_ref == "aud:kamal"
    assert denied.object_ref == "POST /v1/admin/switches"
    assert denied.detail["roles"] == ["auditor"]
    assert "may not" in denied.detail["reason"]


def test_a_forged_token_is_recorded_and_an_anonymous_call_is_not(api: TestClient, clarity: Clarity):
    before = len(of(clarity, AuditEventType.TOKEN_REJECTED))

    api.post("/v1/cases", json={"msisdn": DILANI})
    api.post(
        "/v1/cases", json={"msisdn": DILANI}, headers={"Authorization": "Bearer forged.token.value"}
    )

    rejected = of(clarity, AuditEventType.TOKEN_REJECTED)
    assert len(rejected) == before + 1
    assert rejected[-1].object_ref == "POST /v1/cases"
    assert rejected[-1].session_ref is not None
    assert "forged.token.value" not in json.dumps(rejected[-1].model_dump(mode="json"))


def test_a_staff_session_records_its_roles_and_step_up(api: TestClient, clarity: Clarity):
    staff(api, "sup:ruwan", ["supervisor"], step_up=True)

    started = of(clarity, AuditEventType.STAFF_SESSION_STARTED)[-1]
    assert started.actor_ref == "sup:ruwan"
    assert started.detail["roles"] == ["supervisor"]
    assert started.detail["step_up"] is True


def test_no_raw_phone_number_reaches_the_trail(api: TestClient, clarity: Clarity):
    """I13: identity events identify a number by pseudonym or mask only."""
    headers = customer(api, DILANI)
    api.post("/v1/cases", json={"msisdn": DILANI}, headers=headers)
    api.post("/v1/auth/otp/request", json={"msisdn": "+94770000001"})

    serialised = json.dumps([r.model_dump(mode="json") for r in clarity.audit.records])

    assert DILANI not in serialised
    assert "0" + DILANI.removeprefix("+94") not in serialised
    assert "+94770000001" not in serialised
    assert clarity.audit.verify().intact
