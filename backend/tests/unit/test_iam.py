"""Identity and authorization (improvement plan Phase 3).

Until now every endpoint was open: holding a case id was enough to read anyone's
case. These tests are the evidence that it no longer is.
"""

from __future__ import annotations

from datetime import timedelta

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric.rsa import generate_private_key
from fastapi.testclient import TestClient

from clarity.app.container import Clarity
from clarity.app.settings import Settings
from clarity.integration.drivers.mock.world import build_demo_world
from clarity.interfaces.http.main import create_app
from clarity.kernel.common import utc_now
from clarity.modules.iam.keycloak import KeycloakTokenVerifier
from clarity.modules.iam.otp import (
    MAX_ATTEMPTS,
    MAX_REQUESTS_PER_WINDOW,
    OTP_TTL,
    OtpRefused,
    OtpService,
    SimulatedInbox,
)
from clarity.modules.iam.tokens import (
    STEP_UP_WINDOW,
    TokenInvalid,
    TokenIssuer,
)
from clarity.platform.persistence import MemoryStore, MemoryUnitOfWork
from clarity.platform.security.principal import (
    MONEY_PERMISSIONS,
    Assurance,
    Permission,
    Principal,
    Role,
    permissions_for,
)

DILANI = "+94781234567"
PRIYA = "+94784445555"


@pytest.fixture
def issuer() -> TokenIssuer:
    return TokenIssuer()


@pytest.fixture
def otp() -> OtpService:
    return OtpService()


# --------------------------------------------------------------------------- #
# OTP
# --------------------------------------------------------------------------- #


def test_the_code_never_comes_back_from_the_request(otp: OtpService):
    """Possession of the phone is what proves identity, so the code only
    travels through the delivery port."""
    challenge = otp.request(DILANI)

    assert isinstance(challenge, str)
    assert otp.delivery.latest_for(DILANI)["code"] not in challenge


def test_a_correct_code_proves_the_number(otp: OtpService):
    challenge = otp.request(DILANI)
    code = otp.delivery.latest_for(DILANI)["code"]

    assert otp.verify(challenge, code) == DILANI


def test_a_code_is_single_use(otp: OtpService):
    challenge = otp.request(DILANI)
    code = otp.delivery.latest_for(DILANI)["code"]
    otp.verify(challenge, code)

    with pytest.raises(OtpRefused):
        otp.verify(challenge, code)


def test_a_wrong_code_is_refused(otp: OtpService):
    challenge = otp.request(DILANI)

    with pytest.raises(OtpRefused):
        otp.verify(challenge, "000000")


def test_guessing_is_capped(otp: OtpService):
    """The cheap attack is trying every six-digit code."""
    challenge = otp.request(DILANI)

    for _ in range(MAX_ATTEMPTS):
        with pytest.raises(OtpRefused):
            otp.verify(challenge, "000000")

    # The challenge is burned, so even the right code no longer works.
    code = otp.delivery.latest_for(DILANI)["code"]
    with pytest.raises(OtpRefused):
        otp.verify(challenge, code)


def test_a_code_expires(otp: OtpService):
    now = utc_now()
    challenge = otp.request(DILANI, now=now)
    code = otp.delivery.latest_for(DILANI)["code"]

    with pytest.raises(OtpRefused):
        otp.verify(challenge, code, now=now + OTP_TTL + timedelta(seconds=1))


def test_requests_are_rate_limited_per_number(otp: OtpService):
    """Otherwise the endpoint is an SMS pump."""
    for _ in range(MAX_REQUESTS_PER_WINDOW):
        otp.request(DILANI)

    with pytest.raises(OtpRefused) as error:
        otp.request(DILANI)

    assert error.value.code == "OTP_RATE_LIMITED"


def test_every_failure_looks_the_same(otp: OtpService):
    """A specific message would tell an attacker how close they were."""
    challenge = otp.request(DILANI)

    def message(challenge_id: str, code: str) -> str:
        try:
            otp.verify(challenge_id, code)
        except OtpRefused as refused:
            return str(refused)
        raise AssertionError("expected a refusal")

    unknown_challenge = message("no-such-challenge", "123456")
    wrong_code = message(challenge, "000000")

    assert unknown_challenge == wrong_code


def test_the_demo_inbox_is_labelled_as_simulated():
    inbox = SimulatedInbox()
    inbox.send(DILANI, "123456")

    assert inbox.latest_for(DILANI)["simulated"] == "yes"


def test_two_otp_replicas_share_challenges_and_rate_limits():
    store = MemoryStore()

    def open_unit() -> MemoryUnitOfWork:
        return MemoryUnitOfWork(store)

    inbox = SimulatedInbox()
    first = OtpService(inbox, open_unit=open_unit)
    second = OtpService(inbox, open_unit=open_unit)
    challenge = first.request(DILANI)
    code = inbox.latest_for(DILANI)["code"]

    assert second.verify(challenge, code) == DILANI

    for _ in range(MAX_REQUESTS_PER_WINDOW):
        first.request(PRIYA)
    with pytest.raises(OtpRefused, match="that code is not valid"):
        second.request(PRIYA)


# --------------------------------------------------------------------------- #
# Tokens
# --------------------------------------------------------------------------- #


def test_a_customer_token_carries_the_pseudonym_not_the_number(issuer: TokenIssuer):
    """A token is copied into logs and proxies; a phone number there is a leak."""
    issued = issuer.for_customer("sub_abc123", assurance=Assurance.OTP, channel="web")

    assert "781234567" not in issued.value
    assert issuer.verify(issued.value).subscriber_ref == "sub_abc123"


def test_a_valid_token_names_its_roles_and_assurance(issuer: TokenIssuer):
    issued = issuer.for_staff("sup-1", roles={Role.SUPERVISOR}, assurance=Assurance.MFA)

    principal = issuer.verify(issued.value)

    assert principal.roles == frozenset({Role.SUPERVISOR})
    assert principal.assurance is Assurance.MFA


def test_a_tampered_token_is_refused(issuer: TokenIssuer):
    issued = issuer.for_customer("sub_a", assurance=Assurance.OTP, channel="web")
    tampered = issued.value[:-4] + "AAAA"

    with pytest.raises(TokenInvalid):
        issuer.verify(tampered)


def test_a_token_from_another_issuer_is_refused(issuer: TokenIssuer):
    """Different key, same shape: it must not validate."""
    attacker = TokenIssuer()
    forged = attacker.for_staff("sup-1", roles={Role.SUPERVISOR})

    with pytest.raises(TokenInvalid):
        issuer.verify(forged.value)


def test_an_expired_token_is_refused(issuer: TokenIssuer):
    now = utc_now()
    issued = issuer.for_customer("sub_a", assurance=Assurance.OTP, channel="web", now=now)

    with pytest.raises(TokenInvalid):
        issuer.verify(issued.value, now=now + timedelta(hours=1))


def test_an_unsigned_token_is_refused(issuer: TokenIssuer):
    """The alg-none attack: a token that declines to be signed."""
    import base64
    import json

    def segment(data: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()

    forged = (
        segment({"alg": "none", "typ": "JWT"})
        + "."
        + segment({"sub": "sub_a", "roles": ["supervisor"], "aud": "clarity-api", "iss": "clarity"})
        + "."
    )

    with pytest.raises(TokenInvalid):
        issuer.verify(forged)


def test_empty_or_missing_tokens_are_refused(issuer: TokenIssuer):
    with pytest.raises(TokenInvalid):
        issuer.verify("")


def test_step_up_ages_out(issuer: TokenIssuer):
    """A session minted with MFA hours ago is valid, but is not *recent* MFA."""
    now = utc_now()
    issued = issuer.for_staff(
        "sup-1", roles={Role.SUPERVISOR}, assurance=Assurance.MFA_RECENT, now=now
    )

    fresh = issuer.verify(issued.value, now=now + timedelta(minutes=1))
    stale = issuer.verify(issued.value, now=now + STEP_UP_WINDOW + timedelta(minutes=1))

    assert fresh.assurance.is_step_up
    assert not stale.assurance.is_step_up, "step-up must expire, or it is not step-up"


def test_the_public_key_is_publishable(issuer: TokenIssuer):
    jwk = issuer.public_key_jwk()

    assert jwk["kty"] == "OKP" and jwk["crv"] == "Ed25519"
    assert "d" not in jwk, "a private key component must never be published"


def test_refresh_rotates_and_reuse_is_refused(issuer: TokenIssuer):
    issued = issuer.for_staff("staff-1", roles={Role.AGENT})
    assert issued.refresh_token is not None

    rotated = issuer.refresh(issued.refresh_token)

    assert issuer.verify(rotated.value).ref == "staff-1"
    with pytest.raises(TokenInvalid):
        issuer.refresh(issued.refresh_token)
    with pytest.raises(TokenInvalid):
        issuer.verify(issued.value)


def test_keycloak_verifier_maps_signed_realm_roles():
    now = utc_now()
    private = generate_private_key(public_exponent=65537, key_size=2048)
    public_jwk = jwt.algorithms.RSAAlgorithm.to_jwk(private.public_key(), as_dict=True)
    public_jwk["kid"] = "kc-1"
    public_jwk["alg"] = "RS256"

    def keycloak(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/protocol/openid-connect/certs")
        return httpx.Response(200, json={"keys": [public_jwk]})

    token = jwt.encode(
        {
            "iss": "https://id.example/realms/clarity",
            "aud": "clarity-api",
            "sub": "staff-42",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=5)).timestamp()),
            "auth_time": int(now.timestamp()),
            "acr": "mfa-recent",
            "realm_access": {"roles": ["supervisor", "unknown-role"]},
        },
        private,
        algorithm="RS256",
        headers={"kid": "kc-1"},
    )
    verifier = KeycloakTokenVerifier(
        "https://id.example/realms/clarity",
        "clarity-api",
        client=httpx.Client(transport=httpx.MockTransport(keycloak)),
    )

    principal = verifier.verify(token, now=now)

    assert principal.roles == frozenset({Role.SUPERVISOR})
    assert principal.assurance is Assurance.MFA_RECENT


# --------------------------------------------------------------------------- #
# Permissions and separation of duties
# --------------------------------------------------------------------------- #


def test_a_customer_can_read_but_only_their_own():
    customer = Principal(ref="sub_a", roles=frozenset({Role.CUSTOMER}), subscriber_ref="sub_a")

    assert customer.has(Permission.CASE_READ)
    assert customer.may_read("sub_a")
    assert not customer.may_read("sub_b")


def test_staff_may_read_any_subject():
    agent = Principal(ref="agent-1", roles=frozenset({Role.AGENT}))

    assert agent.may_read("sub_anyone")


def test_a_guardian_may_read_a_delegated_number():
    guardian = Principal(
        ref="sub_a",
        roles=frozenset({Role.CUSTOMER}),
        subscriber_ref="sub_a",
        delegations=frozenset({"sub_child"}),
    )

    assert guardian.may_read("sub_child")
    assert not guardian.may_read("sub_stranger")


@pytest.mark.parametrize("role", [Role.PLATFORM_ADMIN, Role.SECURITY_ADMIN])
def test_an_admin_cannot_approve_money(role: Role):
    """Running the platform and deciding refunds are different jobs."""
    assert not (permissions_for({role}) & MONEY_PERMISSIONS)


def test_stacking_roles_cannot_buy_an_admin_the_money_permissions():
    """The exclusion is applied after the union, so it cannot be escaped."""
    granted = permissions_for({Role.PLATFORM_ADMIN, Role.FINANCE})

    assert not (granted & MONEY_PERMISSIONS)


def test_an_agent_cannot_approve_above_the_cap():
    assert Permission.ACTION_APPROVE in permissions_for({Role.AGENT})
    assert Permission.ACTION_APPROVE_HIGH_VALUE not in permissions_for({Role.AGENT})


def test_only_compliance_exports_the_regulator_pack():
    for role in Role:
        has_it = Permission.REGULATOR_PACK_EXPORT in permissions_for({role})
        assert has_it == (role is Role.COMPLIANCE), role


# --------------------------------------------------------------------------- #
# Over HTTP
# --------------------------------------------------------------------------- #


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(Clarity(world=build_demo_world())))


def customer_token(client: TestClient, msisdn: str) -> str:
    started = client.post("/v1/auth/otp/request", json={"msisdn": msisdn}).json()
    code = client.get("/v1/demo/inbox", params={"msisdn": msisdn}).json()["code"]
    return client.post(
        "/v1/auth/otp/verify",
        json={"challenge_id": started["challenge_id"], "code": code},
    ).json()["token"]


def staff_token(client: TestClient, roles: list[str], *, step_up: bool = False) -> str:
    return client.post(
        "/v1/auth/staff/session",
        json={"user_ref": "u-1", "roles": roles, "step_up": step_up},
    ).json()["token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/v1/cases"),
        ("get", "/v1/cases/CASE-x"),
        ("get", "/v1/cases/CASE-x/timeline"),
        ("post", "/v1/cases/CASE-x/evaluate"),
        ("post", "/v1/cases/CASE-x/proposals"),
        ("get", "/v1/desk/queue"),
        ("get", "/v1/receipts/TR-2027-000001"),
    ],
)
def test_every_protected_route_refuses_an_anonymous_caller(client, method, path):
    """Deny by default: there is no route that forgot to say what it needs."""
    response = client.post(path, json={}) if method == "post" else client.get(path)

    assert response.status_code == 401, f"{method.upper()} {path} was open"


def test_a_garbage_token_is_refused(client: TestClient):
    assert client.get("/v1/desk/queue", headers=auth("not-a-token")).status_code == 401


def test_a_revoked_staff_token_is_refused_with_401():
    clarity = Clarity(world=build_demo_world())
    client = TestClient(create_app(clarity))
    token = staff_token(client, ["agent"])

    clarity.tokens.revoke(token)

    assert client.get("/v1/desk/queue", headers=auth(token)).status_code == 401


def test_one_customer_cannot_read_another_customers_case(client: TestClient):
    """The gap this phase closed. A case id is not authorisation."""
    priya = auth(customer_token(client, PRIYA))
    case_id = client.post("/v1/cases", json={"msisdn": PRIYA}, headers=priya).json()["case_id"]

    dilani = auth(customer_token(client, DILANI))

    assert client.get(f"/v1/cases/{case_id}", headers=dilani).status_code == 403
    assert client.get(f"/v1/cases/{case_id}/timeline", headers=dilani).status_code == 403


def test_a_customer_cannot_open_a_case_about_another_number(client: TestClient):
    dilani = auth(customer_token(client, DILANI))

    assert client.post("/v1/cases", json={"msisdn": PRIYA}, headers=dilani).status_code == 403


def test_a_customer_cannot_read_the_desk_queue(client: TestClient):
    response = client.get("/v1/desk/queue", headers=auth(customer_token(client, DILANI)))

    assert response.status_code == 403


def test_staff_can_read_any_case(client: TestClient):
    dilani = auth(customer_token(client, DILANI))
    case_id = client.post("/v1/cases", json={"msisdn": DILANI}, headers=dilani).json()["case_id"]

    agent = auth(staff_token(client, ["agent"]))

    assert client.get(f"/v1/cases/{case_id}", headers=agent).status_code == 200


def test_approving_above_the_cap_needs_recent_mfa(client: TestClient):
    """Priya's case is LKR 12,000, above the one-tap cap."""
    agent = auth(staff_token(client, ["agent", "supervisor"]))
    case_id = client.post("/v1/cases", json={"msisdn": PRIYA}, headers=agent).json()["case_id"]
    client.post(f"/v1/cases/{case_id}/evaluate", headers=agent)
    plan = client.post(
        f"/v1/cases/{case_id}/proposals", json={"created_by": "desk"}, headers=agent
    ).json()

    body = {"plan_id": plan["plan_id"], "role": "supervisor"}
    without = client.post(f"/v1/cases/{case_id}/approve", json=body, headers=agent)

    stepped_up = auth(staff_token(client, ["agent", "supervisor"], step_up=True))
    with_step_up = client.post(f"/v1/cases/{case_id}/approve", json=body, headers=stepped_up)

    assert without.status_code == 403
    assert "re-authentication" in without.json()["detail"]
    assert with_step_up.status_code == 200


def test_an_agent_cannot_approve_a_high_value_case_even_with_step_up(client: TestClient):
    agent_only = auth(staff_token(client, ["agent"], step_up=True))
    case_id = client.post("/v1/cases", json={"msisdn": PRIYA}, headers=agent_only).json()["case_id"]
    client.post(f"/v1/cases/{case_id}/evaluate", headers=agent_only)
    plan = client.post(
        f"/v1/cases/{case_id}/proposals", json={"created_by": "desk"}, headers=agent_only
    ).json()

    response = client.post(
        f"/v1/cases/{case_id}/approve",
        json={"plan_id": plan["plan_id"], "role": "agent"},
        headers=agent_only,
    )

    assert response.status_code == 403


def test_staff_cannot_confirm_as_if_they_were_the_customer(client: TestClient):
    """Confirming is the customer's act; approving is staff's."""
    agent = auth(staff_token(client, ["agent", "supervisor"]))
    case_id = client.post("/v1/cases", json={"msisdn": DILANI}, headers=agent).json()["case_id"]
    client.post(f"/v1/cases/{case_id}/evaluate", headers=agent)
    plan = client.post(
        f"/v1/cases/{case_id}/proposals", json={"created_by": "desk"}, headers=agent
    ).json()

    response = client.post(
        f"/v1/cases/{case_id}/confirm", json={"plan_id": plan["plan_id"]}, headers=agent
    )

    assert response.status_code == 403


def test_the_receipt_check_page_stays_public(client: TestClient):
    """Anyone holding a receipt can verify it, including TRCSL."""
    dilani = auth(customer_token(client, DILANI))
    case_id = client.post("/v1/cases", json={"msisdn": DILANI}, headers=dilani).json()["case_id"]
    client.post(f"/v1/cases/{case_id}/evaluate", headers=dilani)
    plan = client.post(
        f"/v1/cases/{case_id}/proposals", json={"created_by": "web"}, headers=dilani
    ).json()
    receipt_id = client.post(
        f"/v1/cases/{case_id}/confirm", json={"plan_id": plan["plan_id"]}, headers=dilani
    ).json()["receipt_id"]

    public = client.post(f"/v1/receipts/{receipt_id}/verify")

    assert public.status_code == 200, "verification must need no account"
    assert public.json()["valid"]


def test_the_customer_is_not_a_staff_role(client: TestClient):
    response = client.post("/v1/auth/staff/session", json={"user_ref": "x", "roles": ["customer"]})

    assert response.status_code == 422


def test_whoami_reports_what_the_session_allows(client: TestClient):
    me = client.get("/v1/auth/me", headers=auth(staff_token(client, ["compliance"]))).json()

    assert "regulator_pack:export" in me["permissions"]
    assert "action:approve" not in me["permissions"]


def issue_receipt_for(client: TestClient, msisdn: str) -> str:
    """Drive a case to a receipt as that customer."""
    headers = auth(customer_token(client, msisdn))
    case_id = client.post("/v1/cases", json={"msisdn": msisdn}, headers=headers).json()["case_id"]
    client.post(f"/v1/cases/{case_id}/evaluate", headers=headers)
    plan = client.post(
        f"/v1/cases/{case_id}/proposals", json={"created_by": "web"}, headers=headers
    ).json()
    return client.post(
        f"/v1/cases/{case_id}/confirm", json={"plan_id": plan["plan_id"]}, headers=headers
    ).json()["receipt_id"]


def test_a_receipt_id_does_not_entitle_another_customer_to_the_document(client: TestClient):
    """The full receipt is the owner's; the public page is everyone's."""
    receipt_id = issue_receipt_for(client, DILANI)
    stranger = auth(customer_token(client, PRIYA))

    assert client.get(f"/v1/receipts/{receipt_id}", headers=stranger).status_code == 403
    assert client.get(f"/v1/receipts/{receipt_id}/render", headers=stranger).status_code in {
        403,
        503,
    }, "a stranger must be refused before the renderer is even consulted"


def test_the_owner_can_read_their_own_receipt(client: TestClient):
    receipt_id = issue_receipt_for(client, DILANI)
    owner = auth(customer_token(client, DILANI))

    assert client.get(f"/v1/receipts/{receipt_id}", headers=owner).status_code == 200


def test_staff_can_read_any_receipt(client: TestClient):
    receipt_id = issue_receipt_for(client, DILANI)

    agent = auth(staff_token(client, ["agent"]))
    response = client.get(f"/v1/receipts/{receipt_id}", headers=agent)

    assert response.status_code == 200


def test_a_customer_cannot_propose_on_another_customers_case(client: TestClient):
    """Proposing is where amounts get attached, so it needs the same binding."""
    priya = auth(customer_token(client, PRIYA))
    case_id = client.post("/v1/cases", json={"msisdn": PRIYA}, headers=priya).json()["case_id"]
    client.post(f"/v1/cases/{case_id}/evaluate", headers=priya)

    dilani = auth(customer_token(client, DILANI))
    response = client.post(
        f"/v1/cases/{case_id}/proposals", json={"created_by": "web"}, headers=dilani
    )

    assert response.status_code == 403


def test_the_qr_stays_public(client: TestClient):
    """It encodes only the verify URL, so it grants nothing."""
    receipt_id = issue_receipt_for(client, DILANI)

    assert client.get(f"/v1/receipts/{receipt_id}/qr.svg").status_code == 200


def test_supervisor_can_read_and_flip_kill_switches(client: TestClient):
    headers = auth(staff_token(client, ["supervisor"], step_up=True))

    listed = client.get("/v1/admin/switches", headers=headers)
    assert listed.status_code == 200, listed.text
    assert any(s["key"] == "auto_fix_global" for s in listed.json()["switches"])

    flipped = client.post(
        "/v1/admin/switches",
        json={"key": "auto_fix_global", "enabled": False, "reason": "demo drill"},
        headers=headers,
    )
    assert flipped.status_code == 200, flipped.text
    assert "auto_fix_global" in flipped.json()["disabled"]


def test_a_customer_cannot_read_kill_switches(client: TestClient):
    headers = auth(customer_token(client, DILANI))
    assert client.get("/v1/admin/switches", headers=headers).status_code == 403


def test_security_admin_can_read_switches_but_not_flip_without_kill_switch(
    client: TestClient,
):
    headers = auth(staff_token(client, ["security_admin"], step_up=True))
    assert client.get("/v1/admin/switches", headers=headers).status_code == 200
    response = client.post(
        "/v1/admin/switches",
        json={"key": "auto_fix_global", "enabled": False, "reason": "try"},
        headers=headers,
    )
    assert response.status_code == 403


def test_supervisor_can_flip_kill_switches_without_step_up(client: TestClient):
    """flags:kill_switch is not a step-up permission (unlike merchant:suspend)."""
    headers = auth(staff_token(client, ["supervisor"], step_up=False))
    response = client.post(
        "/v1/admin/switches",
        json={"key": "llm_explanations", "enabled": False, "reason": "incident"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert "llm_explanations" in response.json()["disabled"]


def test_vas_ops_can_suspend_merchant_with_step_up(client: TestClient):
    headers = auth(staff_token(client, ["vas_ops"], step_up=True))
    response = client.post(
        "/v1/admin/merchants/suspend",
        json={
            "merchant_id": "merchant-gamezone",
            "reason": "demo suspend",
            "subscriber_msisdn": DILANI,
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["blocked"] is True
    assert response.json()["simulated"] is True


def test_vas_ops_cannot_suspend_without_step_up(client: TestClient):
    headers = auth(staff_token(client, ["vas_ops"], step_up=False))
    response = client.post(
        "/v1/admin/merchants/suspend",
        json={
            "merchant_id": "merchant-gamezone",
            "reason": "demo suspend",
            "subscriber_msisdn": DILANI,
        },
        headers=headers,
    )
    assert response.status_code == 403


def test_the_otp_inbox_is_a_demo_only_route():
    """It hands out codes, so it must not exist where subscribers are real."""
    from clarity.app.container import Profile

    clarity = Clarity(world=build_demo_world())
    client = TestClient(create_app(clarity))
    assert client.get("/v1/demo/subscribers").status_code == 200

    # PROD is the profile with real subscribers. Note that `/v1/demo/reset`
    # would swap the container out, so it is not called here.
    clarity.profile = Profile.PROD

    assert client.get("/v1/demo/subscribers").status_code == 404
    assert client.get("/v1/demo/inbox", params={"msisdn": DILANI}).status_code == 404
    assert client.post("/v1/demo/reset").status_code == 404
    # The gate is on the demo routes only; the rest still answer as themselves.
    assert client.get("/v1/desk/queue").status_code == 401


def test_self_service_permissions_belong_to_customers_only():
    """A staff role never gets a customer's self-service rights, however senior."""
    from clarity.platform.security.principal import ROLE_PERMISSIONS, Permission, Role

    self_service = {Permission.SELF_READ, Permission.SELF_SETTINGS, Permission.SELF_TRANSACT}

    assert self_service <= ROLE_PERMISSIONS[Role.CUSTOMER]
    for role, permissions in ROLE_PERMISSIONS.items():
        if role is not Role.CUSTOMER:
            assert not (self_service & permissions), role


def test_a_persisted_issuer_key_keeps_sessions_across_a_restart(tmp_path):
    """Every CD deploy restarts the API. With an in-memory key that signed
    every customer out, and the chat answered each turn with a 401. The store
    is shared, as PostgreSQL is between the old and the new process."""
    store = MemoryStore()
    key_path = tmp_path / "keys" / "iam-issuer.pem"
    before = TokenIssuer(open_unit=lambda: MemoryUnitOfWork(store), key_path=key_path)
    issued = before.for_customer("sub_a", assurance=Assurance.OTP, channel="web")

    after = TokenIssuer(open_unit=lambda: MemoryUnitOfWork(store), key_path=key_path)

    assert after.verify(issued.value).subscriber_ref == "sub_a"
    assert key_path.stat().st_mode & 0o777 == 0o600


def test_processes_starting_together_share_one_issuer_key(tmp_path):
    """API, MCP and channel gateway share the key directory on the VPS."""
    from concurrent.futures import ThreadPoolExecutor

    key_path = tmp_path / "iam-issuer.pem"
    with ThreadPoolExecutor(max_workers=8) as pool:
        issuers = list(pool.map(lambda _: TokenIssuer(key_path=key_path), range(8)))

    assert len({str(issuer.public_key_jwk()) for issuer in issuers}) == 1


def test_without_keys_dir_the_issuer_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    clarity = Clarity(settings=Settings(_env_file=None))

    assert clarity.settings.keys_dir is None
    assert clarity.tokens.public_key_jwk()
    assert list(tmp_path.iterdir()) == []
