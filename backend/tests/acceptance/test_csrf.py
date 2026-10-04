"""Cross-site request forgery, for sessions carried by a cookie (B4).

The session cookies are `SameSite=Lax` and CORS is pinned, which covers the
ordinary case. These cover what it does not: a sibling subdomain is same-site
as far as Lax is concerned, and a browser that does not apply the Lax default
sends the cookie on a cross-site POST as it always did. On a surface that
approves refunds, the ordinary case is not the bar.

The shape of the mechanism is what makes it work: an attacker can cause a
browser to *send* cookies but cannot *read* them, so they cannot produce the
header that echoes one.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from clarity.app.container import Clarity
from clarity.integration.drivers.mock.world import build_demo_world
from clarity.interfaces.http.cookies import (
    CSRF_COOKIE,
    CSRF_HEADER,
    CUSTOMER_COOKIE,
    STAFF_COOKIE,
)
from clarity.interfaces.http.main import create_app
from clarity.platform.security.principal import Role

TOKEN = "a-csrf-token"


@pytest.fixture
def clarity() -> Clarity:
    return Clarity(world=build_demo_world())


@pytest.fixture
def api(clarity: Clarity) -> TestClient:
    return TestClient(create_app(clarity))


def _as_browser(api: TestClient, clarity: Clarity) -> None:
    issued = clarity.tokens.for_staff("sup-1", roles={Role.SUPERVISOR})
    api.cookies.set(STAFF_COOKIE, issued.value)
    api.cookies.set(CSRF_COOKIE, TOKEN)


def test_a_cookie_borne_change_without_the_header_is_refused(
    api: TestClient, clarity: Clarity
) -> None:
    _as_browser(api, clarity)

    refused = api.request("DELETE", "/v1/auth/sessions")

    assert refused.status_code == 403
    assert refused.json()["code"] == "CSRF_FAILED"


def test_the_same_change_with_the_header_is_allowed(api: TestClient, clarity: Clarity) -> None:
    _as_browser(api, clarity)

    allowed = api.request("DELETE", "/v1/auth/sessions", headers={CSRF_HEADER: TOKEN})

    assert allowed.status_code == 200


def test_a_header_that_does_not_match_the_cookie_is_refused(
    api: TestClient, clarity: Clarity
) -> None:
    """Guessing is the only other way in, so the comparison has to be real."""
    _as_browser(api, clarity)

    refused = api.request("DELETE", "/v1/auth/sessions", headers={CSRF_HEADER: "not-the-token"})

    assert refused.status_code == 403


def test_a_bearer_token_is_not_subject_to_this(api: TestClient, clarity: Clarity) -> None:
    """Another origin cannot make a browser send a header it does not know, so
    a bearer caller is not forgeable this way. The MCP server, the channel
    gateway and every machine client stay out of it."""
    issued = clarity.tokens.for_staff("sup-1", roles={Role.SUPERVISOR})

    allowed = api.request(
        "DELETE", "/v1/auth/sessions", headers={"Authorization": f"Bearer {issued.value}"}
    )

    assert allowed.status_code == 200


def test_a_caller_with_no_session_is_not_asked_for_a_token(api: TestClient) -> None:
    """There is nothing to forge without a session, and demanding a token from
    a signed-out caller would turn sign-in into a two-step dance."""
    refused = api.request("DELETE", "/v1/auth/sessions")

    assert refused.status_code == 401


def test_reading_never_needs_a_token(api: TestClient, clarity: Clarity) -> None:
    """`SameSite=Lax` lets a top-level GET carry the cookie, and that is safe
    only because no GET here changes anything."""
    _as_browser(api, clarity)

    assert api.get("/v1/auth/sessions").status_code == 200


def test_signing_in_does_not_need_a_token_it_cannot_have(api: TestClient) -> None:
    """The sign-in routes set the cookie, so the caller has none to echo."""
    started = api.post("/v1/auth/otp/request", json={"msisdn": "+94781234567"})

    assert started.status_code == 200


def test_signing_in_hands_the_browser_its_token(api: TestClient) -> None:
    """Otherwise the first state-changing call after sign-in would be refused."""
    started = api.post("/v1/auth/otp/request", json={"msisdn": "+94781234567"}).json()
    code = api.get("/v1/demo/inbox", params={"msisdn": "+94781234567"}).json()["code"]

    verified = api.post(
        "/v1/auth/otp/verify", json={"challenge_id": started["challenge_id"], "code": code}
    )

    assert verified.status_code == 200
    assert api.cookies.get(CSRF_COOKIE)
    assert api.cookies.get(CUSTOMER_COOKIE)


def test_the_session_cookie_is_not_readable_by_a_script(api: TestClient) -> None:
    """The whole reason it is a cookie rather than `sessionStorage`."""
    started = api.post("/v1/auth/otp/request", json={"msisdn": "+94781234567"}).json()
    code = api.get("/v1/demo/inbox", params={"msisdn": "+94781234567"}).json()["code"]
    verified = api.post(
        "/v1/auth/otp/verify", json={"challenge_id": started["challenge_id"], "code": code}
    )

    session = next(
        header
        for header in verified.headers.get_list("set-cookie")
        if header.startswith(CUSTOMER_COOKIE)
    )
    csrf = next(
        header
        for header in verified.headers.get_list("set-cookie")
        if header.startswith(CSRF_COOKIE)
    )

    assert "httponly" in session.lower()
    # And the CSRF token deliberately is readable: the page has to echo it.
    assert "httponly" not in csrf.lower()


def test_a_read_only_post_is_not_blocked(api: TestClient, clarity: Clarity) -> None:
    """Some routes are POSTs because they are an action a person takes, not
    because they write. Verifying a receipt is one, and an attacker who wants
    one verified can verify it themselves."""
    _as_browser(api, clarity)

    answered = api.post("/v1/receipts/TR-2027-000001/verify")

    assert answered.status_code != 403
