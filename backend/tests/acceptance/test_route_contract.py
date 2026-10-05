"""Every route's security posture, frozen (R0).

Each route is classified once:

- ``PUBLIC``: answers anonymous callers by design (health, keys, sign-in,
  receipt verification, help content).
- ``SIGNED_IN``: an anonymous caller gets 401.
- ``SYNTHETIC_ONLY``: development and simulated-HUTCH routes; they work in the
  synthetic profiles and return 404 in ``prod`` (D3, D7).

A new route that is not classified here fails the build, so nobody adds an
endpoint without deciding who may call it (AGENTS.md I9).
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from clarity.app.container import Clarity, Profile
from clarity.integration.drivers.mock.world import build_demo_world
from clarity.interfaces.http.main import create_app

PUBLIC = {
    # Exchanges a refresh token for a new access token (M-IAM). Public like
    # sign-in: the refresh token is the credential, so there is no session yet.
    ("POST", "/v1/auth/refresh"),
    # Staff SSO (B1). Public by necessity: nobody is signed in when a sign-in
    # starts, and the callback arrives from the provider's redirect, not from
    # an authenticated caller. What protects them is the single-use `state`,
    # PKCE, and the nonce check on the id token.
    ("GET", "/v1/auth/sign-in-methods"),
    ("GET", "/v1/auth/staff/oidc/start"),
    ("GET", "/v1/auth/staff/oidc/callback"),
    ("POST", "/v1/auth/logout"),
    # The page routes that used to sit here are gone: FE01 retired the static
    # UI, so this app serves `/v1`, the schema and the key endpoints only, and
    # the three Next.js apps are the UI.
    ("GET", "/docs"),
    ("GET", "/docs/oauth2-redirect"),
    ("GET", "/redoc"),
    ("GET", "/openapi.json"),
    ("GET", "/health"),
    ("GET", "/.well-known/clarity-keys.json"),
    # The latest signed audit checkpoint: hashes and a signature, for anyone
    # to keep as a witness (ADR-0035).
    ("GET", "/.well-known/clarity-audit-checkpoint.json"),
    ("GET", "/.well-known/jwks.json"),
    ("POST", "/v1/auth/otp/request"),
    ("POST", "/v1/auth/otp/verify"),
    ("POST", "/v1/receipts/{receipt_id}/verify"),
    ("GET", "/v1/receipts/{receipt_id}/qr.svg"),
    ("GET", "/v1/ai/usage"),
    ("GET", "/v1/mcp/tools"),
    ("GET", "/v1/knowledge/search"),
    ("POST", "/v1/clarity/route"),
    ("POST", "/v1/conversation/turn"),
    ("POST", "/v1/conversation/turn/stream"),
    ("POST", "/v1/conversation/suggestions"),
    ("GET", "/v1/conversation/suggestions"),
}

SIGNED_IN = {
    # Beginning a step-up needs a session: it re-authenticates somebody who is
    # already here (B2).
    ("POST", "/v1/auth/staff/step-up"),
    # The Autopsy reviewer workspace (D1). Reading is the desk permission;
    # ruling needs `autopsy:review`; proposing a policy change needs
    # `rule:draft`, which is a different judgement from reviewing.
    ("GET", "/v1/autopsy/clusters"),
    # Operations dashboards, folded from the event log (D2).
    ("GET", "/v1/insights/dashboards"),
    ("POST", "/v1/autopsy/clusters/{cluster_id}/review"),
    ("POST", "/v1/autopsy/clusters/{cluster_id}/supersede"),
    ("POST", "/v1/autopsy/clusters/{cluster_id}/rule-candidate"),
    # A person's own sessions (B3). Signed in only, and the subject comes from
    # the token, so there is nothing to enumerate.
    ("GET", "/v1/auth/sessions"),
    ("DELETE", "/v1/auth/sessions"),
    # The audit trail and audit duties (audit assurance Phase 3): reading needs
    # audit:read, granting needs audit:assign, break-glass needs admin:manage.
    ("GET", "/v1/audit"),
    # The verifiable export a regulator checks offline (Phase 7, ADR-0039).
    # Needs audit:export, which costs its holder every money permission.
    ("GET", "/v1/audit/export"),
    # The console Audit section's panels (Phase 5). All need audit:read.
    # ``health`` is deliberately not recorded as audit.read: a dashboard polls it,
    # and recording every poll would make the console trip mass_audit_read.
    ("GET", "/v1/audit/health"),
    ("GET", "/v1/audit/recovery"),
    ("POST", "/v1/audit/records/{seq}/verify"),
    ("GET", "/v1/audit/grants"),
    ("POST", "/v1/audit/grants"),
    ("POST", "/v1/audit/grants/{grant_id}/approve"),
    ("POST", "/v1/audit/grants/{grant_id}/revoke"),
    ("POST", "/v1/audit/grants/{grant_id}/recertify"),
    ("POST", "/v1/audit/break-glass"),
    # Assurance alerts (Phase 4): reading needs audit:read, the lifecycle
    # needs alert:dispose.
    ("GET", "/v1/assurance/alerts"),
    ("POST", "/v1/assurance/alerts/{alert_id}/acknowledge"),
    ("POST", "/v1/assurance/alerts/{alert_id}/investigate"),
    ("POST", "/v1/assurance/alerts/{alert_id}/dispose"),
    ("GET", "/v1/auth/me"),
    ("POST", "/v1/cases"),
    ("GET", "/v1/cases/{case_id}"),
    ("GET", "/v1/cases/{case_id}/timeline"),
    ("GET", "/v1/cases/{case_id}/transcript"),
    ("POST", "/v1/cases/{case_id}/evaluate"),
    ("POST", "/v1/cases/{case_id}/proposals"),
    ("POST", "/v1/cases/{case_id}/confirm"),
    ("POST", "/v1/cases/{case_id}/auto-fix"),
    ("POST", "/v1/cases/{case_id}/approve"),
    ("POST", "/v1/cases/{case_id}/receipt"),
    ("GET", "/v1/receipts/{receipt_id}"),
    ("GET", "/v1/receipts/{receipt_id}/render"),
    # Foresight (C4, F06). Four permissions, all staff: `foresight:read` to
    # look, `foresight:scenario:draft` and `foresight:run` for product, and
    # `foresight:outcome:record` for whoever observes a launch, deliberately not
    # product. Nothing here is customer-facing and nothing is public: a
    # rehearsal names changes HUTCH has not announced.
    ("POST", "/v1/foresight/scenarios"),
    ("GET", "/v1/foresight/scenarios"),
    ("GET", "/v1/foresight/scenarios/{scenario_id}"),
    ("POST", "/v1/foresight/scenarios/{scenario_id}/versions"),
    ("POST", "/v1/foresight/runs"),
    ("GET", "/v1/foresight/runs"),
    ("GET", "/v1/foresight/runs/{run_id}"),
    ("POST", "/v1/foresight/launches"),
    ("GET", "/v1/foresight/launches"),
    ("POST", "/v1/foresight/launches/{launch_id}/outcomes"),
    ("POST", "/v1/foresight/backtests"),
    ("GET", "/v1/foresight/backtests"),
    ("GET", "/v1/foresight/calibration"),
    ("GET", "/v1/foresight/spikes"),
    # The autopsy loop (C7). Reading candidates needs `foresight:read`;
    # confirming one needs `foresight:outcome:record`, which `product` does not
    # hold, because turning a cluster into evidence is the act the calibration
    # gate rests on.
    ("GET", "/v1/foresight/candidates"),
    ("POST", "/v1/foresight/candidates/{cluster_id}/confirm"),
    ("GET", "/v1/foresight/launches/{launch_id}/comparison"),
    ("GET", "/v1/desk/queue"),
    ("GET", "/v1/admin/switches"),
    ("POST", "/v1/admin/switches"),
    ("POST", "/v1/admin/merchants/suspend"),
    # The finance queue of unmatched actions (M-REC). Staff only: it lists
    # money that moved without a confirmation from the adapter.
    ("GET", "/v1/finance/reconciliation"),
    # Policy Studio (M-GOV). Staff only, and the governance gate inside decides
    # who may approve or activate: separation of duties is enforced there, not
    # by the route, because the route cannot know who drafted the change.
    ("GET", "/v1/admin/policy/changes"),
    ("POST", "/v1/admin/policy/changes"),
    ("POST", "/v1/admin/policy/changes/{change_id}/review"),
    ("POST", "/v1/admin/policy/changes/{change_id}/approve"),
    ("POST", "/v1/admin/policy/changes/{change_id}/schedule"),
    ("POST", "/v1/admin/policy/changes/{change_id}/activate"),
    ("POST", "/v1/admin/policy/changes/{change_id}/rollback"),
    ("GET", "/v1/me/home"),
    ("GET", "/v1/me/app"),
    ("GET", "/v1/me/cases"),
    ("GET", "/v1/me/receipts"),
    ("POST", "/v1/me/reload"),
    ("POST", "/v1/me/packages/{offering_id}/purchase"),
    ("POST", "/v1/me/subscriptions/{subscription_id}/cancel"),
    ("POST", "/v1/me/safeguards"),
    ("POST", "/v1/me/family"),
    ("POST", "/v1/me/preferences"),
    # The MCP connector (OPS01). Connection details for `clarity-mcp`: the
    # endpoint, the scopes and the resource indicator are the recipe for
    # pointing a client at this system, so both need `admin:manage`.
    ("GET", "/v1/admin/mcp"),
    ("GET", "/v1/admin/mcp/health"),
}

SYNTHETIC_ONLY = {
    ("POST", "/v1/demo/reset"),
    ("GET", "/v1/demo/inbox"),
    ("GET", "/v1/demo/subscribers"),
    ("POST", "/v1/auth/staff/session"),
    ("POST", "/v1/auth/staff/login"),
}

#: Valid bodies, so a 401 proves the sign-in check rather than input validation.
BODIES: dict[str, dict[str, object]] = {
    "/v1/me/reload": {"amount_lkr": "100"},
    "/v1/me/safeguards": {"kind": "spend_cap", "value": "100"},
    "/v1/me/family": {"msisdn": "+94781234567"},
    "/v1/me/preferences": {"language": "en"},
    "/v1/conversation/turn": {"text": "why was I charged"},
    "/v1/conversation/turn/stream": {"text": "why was I charged"},
}


def _app(profile: Profile = Profile.DEMO) -> TestClient:
    clarity = Clarity(world=build_demo_world())
    clarity.profile = profile
    return TestClient(create_app(clarity))


def _routes(client: TestClient) -> set[tuple[str, str]]:
    return {
        (method, route.path)
        for route in client.app.routes  # type: ignore[attr-defined]
        if hasattr(route, "methods")
        for method in route.methods
        if method in {"GET", "POST", "PUT", "PATCH", "DELETE"}
    }


def test_no_route_hides_inside_an_included_router():
    """Every route must be registered on the app, not through a router.

    This classification walks `app.routes`, and FastAPI wraps anything added
    with `include_router` in an opaque `_IncludedRouter` object that carries no
    `path` and no `methods`. Such a route is invisible here, so it would be
    exempt from declaring who may call it and the I9 guard would pass without
    ever having seen it. Found while adding staff SSO, which was written as a
    router first.

    If a router ever becomes worth having, this test is the thing to change:
    descend into it and classify what is inside. Until then the rule is that
    routes are declared where the classifier can see them.
    """
    app = _app().app
    hidden = [
        type(route).__name__
        for route in app.routes  # type: ignore[attr-defined]
        if type(route).__name__ == "_IncludedRouter"
    ]

    assert hidden == [], (
        "a route was added with include_router, so it is invisible to the "
        "classification below and would skip the I9 check entirely"
    )


def _call(client: TestClient, method: str, path: str) -> int:
    concrete = re.sub(r"\{[^}]+\}", "X", path)
    if path == "/v1/demo/inbox":
        # The inbox holds a code only after one was requested.
        client.post("/v1/auth/otp/request", json={"msisdn": "+94781234567"})
        concrete += "?msisdn=%2B94781234567"
    if method == "GET":
        return client.get(concrete).status_code
    return client.request(method, concrete, json=BODIES.get(path, {})).status_code


def test_every_route_is_classified_exactly_once():
    routes = _routes(_app())
    classified = PUBLIC | SIGNED_IN | SYNTHETIC_ONLY

    assert routes - classified == set(), "unclassified routes: decide who may call them"
    assert classified - routes == set(), "classified routes that no longer exist"
    assert not (PUBLIC & SIGNED_IN or PUBLIC & SYNTHETIC_ONLY or SIGNED_IN & SYNTHETIC_ONLY)


@pytest.mark.parametrize("route", sorted(SIGNED_IN))
def test_signed_in_routes_refuse_anonymous_callers(route: tuple[str, str]):
    assert _call(_app(), *route) == 401


@pytest.mark.parametrize("route", sorted(PUBLIC))
def test_public_routes_answer_anonymous_callers(route: tuple[str, str]):
    assert _call(_app(), *route) not in {401, 403}


@pytest.mark.parametrize("route", sorted(SYNTHETIC_ONLY))
def test_synthetic_only_routes_do_not_exist_in_production(route: tuple[str, str]):
    assert _call(_app(Profile.PROD), *route) == 404


@pytest.mark.parametrize("route", sorted(SYNTHETIC_ONLY - {("POST", "/v1/demo/reset")}))
def test_synthetic_only_routes_work_in_the_demo_profile(route: tuple[str, str]):
    assert _call(_app(), *route) != 404
