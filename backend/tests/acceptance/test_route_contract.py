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
    ("POST", "/v1/conversation/suggestions"),
    ("GET", "/v1/conversation/suggestions"),
}

SIGNED_IN = {
    ("GET", "/v1/auth/me"),
    ("POST", "/v1/cases"),
    ("GET", "/v1/cases/{case_id}"),
    ("GET", "/v1/cases/{case_id}/timeline"),
    ("POST", "/v1/cases/{case_id}/evaluate"),
    ("POST", "/v1/cases/{case_id}/proposals"),
    ("POST", "/v1/cases/{case_id}/confirm"),
    ("POST", "/v1/cases/{case_id}/auto-fix"),
    ("POST", "/v1/cases/{case_id}/approve"),
    ("POST", "/v1/cases/{case_id}/receipt"),
    ("GET", "/v1/receipts/{receipt_id}"),
    ("GET", "/v1/receipts/{receipt_id}/render"),
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
    ("GET", "/v1/demo/ops"),
    ("GET", "/v1/demo/autopsy"),
    ("GET", "/v1/demo/foresight"),
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
}

SYNTHETIC_ONLY = {
    ("POST", "/v1/demo/reset"),
    ("GET", "/v1/demo/inbox"),
    ("GET", "/v1/demo/subscribers"),
    ("POST", "/v1/auth/staff/session"),
}

#: Valid bodies, so a 401 proves the sign-in check rather than input validation.
BODIES: dict[str, dict[str, object]] = {
    "/v1/me/reload": {"amount_lkr": "100"},
    "/v1/me/safeguards": {"kind": "spend_cap", "value": "100"},
    "/v1/me/family": {"msisdn": "+94771234567"},
    "/v1/me/preferences": {"language": "en"},
    "/v1/conversation/turn": {"text": "why was I charged"},
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


def _call(client: TestClient, method: str, path: str) -> int:
    concrete = re.sub(r"\{[^}]+\}", "X", path)
    if path == "/v1/demo/inbox":
        # The inbox holds a code only after one was requested.
        client.post("/v1/auth/otp/request", json={"msisdn": "+94771234567"})
        concrete += "?msisdn=%2B94771234567"
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
