"""The staff SSO routes over HTTP (B1, B2, B3).

Two states worth testing and they are both about what the API refuses.

**Off.** Staff SSO needs an issuer, a confidential client secret and a callback.
With any of them missing the routes answer 404 rather than half-working, because
a deployment that believes it has SSO and is actually falling through to the
development sign-in is the failure nobody notices.

**On.** The provider is not reachable from this suite, so these drive the parts
that do not need it: the redirect the API builds, the refusals on the way back,
and the cookie. The round trip against a real Keycloak is
`tests/integration/test_keycloak.py`.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from clarity.app.container import Clarity
from clarity.app.settings import Settings
from clarity.integration.drivers.mock.world import build_demo_world
from clarity.interfaces.http.cookies import (
    CSRF_COOKIE,
    CSRF_HEADER,
    ID_TOKEN_COOKIE,
    STAFF_COOKIE,
)
from clarity.interfaces.http.main import create_app

ISSUER = "http://127.0.0.1:8081/realms/clarity"


def _api(**overrides: object) -> TestClient:
    settings = Settings(_env_file=None, **overrides)  # type: ignore[arg-type]
    return TestClient(create_app(Clarity(world=build_demo_world(), settings=settings)))


@pytest.fixture
def configured() -> TestClient:
    return _api(
        CLARITY_KEYCLOAK_ISSUER=ISSUER,
        CLARITY_OIDC_CLIENT_SECRET="development-only",
        CLARITY_OIDC_REDIRECT_URI="http://127.0.0.1:8000/v1/auth/staff/oidc/callback",
        CLARITY_CONSOLE_BASE_URL="http://127.0.0.1:3101",
    )


@pytest.fixture
def unconfigured() -> TestClient:
    return _api()


# --------------------------------------------------------------------------- #
# Off
# --------------------------------------------------------------------------- #


def test_the_sso_routes_do_not_exist_until_sso_is_configured(unconfigured: TestClient) -> None:
    assert unconfigured.get("/v1/auth/staff/oidc/start", follow_redirects=False).status_code == 404
    assert unconfigured.get("/v1/auth/staff/oidc/callback?code=x&state=y").status_code == 404


def test_a_secret_is_required_not_optional() -> None:
    """A confidential client with no secret is a public client nobody decided
    to make public, so the half-configured case is off rather than weaker."""
    half = _api(
        CLARITY_KEYCLOAK_ISSUER=ISSUER,
        CLARITY_OIDC_REDIRECT_URI="http://127.0.0.1:8000/v1/auth/staff/oidc/callback",
    )

    assert half.get("/v1/auth/staff/oidc/start", follow_redirects=False).status_code == 404


# --------------------------------------------------------------------------- #
# On
# --------------------------------------------------------------------------- #


def test_starting_a_sign_in_redirects_to_the_provider(configured: TestClient) -> None:
    response = configured.get("/v1/auth/staff/oidc/start", follow_redirects=False)

    assert response.status_code == 303
    location = response.headers["location"]
    assert location.startswith(f"{ISSUER}/protocol/openid-connect/auth")
    query = {k: v[0] for k, v in parse_qs(urlparse(location).query).items()}
    assert query["code_challenge_method"] == "S256"
    assert query["state"]


def test_the_return_address_cannot_be_borrowed(configured: TestClient) -> None:
    """An open redirect on a sign-in route is how a phishing page borrows a
    real login screen. `return_to` is the one part a caller chooses."""
    for hostile in ("https://evil.example/steal", "//evil.example", "http://evil.example"):
        response = configured.get(
            "/v1/auth/staff/oidc/start",
            params={"return_to": hostile},
            follow_redirects=False,
        )
        assert response.status_code == 303
        # The hostile host must not appear in what the provider is told to
        # send the browser back to.
        assert "evil.example" not in response.headers["location"]


def test_a_callback_with_no_code_does_not_sign_anyone_in(configured: TestClient) -> None:
    response = configured.get(
        "/v1/auth/staff/oidc/callback", params={"error": "access_denied"}, follow_redirects=False
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith("http://127.0.0.1:3101")
    assert STAFF_COOKIE not in response.cookies


def test_a_forged_state_is_refused(configured: TestClient) -> None:
    """The state was never issued by this API, so there is no verifier for it
    and the exchange must not even be attempted."""
    response = configured.get(
        "/v1/auth/staff/oidc/callback",
        params={"code": "anything", "state": "forged"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "sso=failed" in response.headers["location"]
    assert STAFF_COOKIE not in response.cookies


def test_beginning_a_step_up_needs_a_session(configured: TestClient) -> None:
    assert configured.post("/v1/auth/staff/step-up").status_code == 401


# --------------------------------------------------------------------------- #
# Logout
# --------------------------------------------------------------------------- #


def test_signing_out_clears_the_cookies(configured: TestClient) -> None:
    response = configured.post("/v1/auth/logout")

    assert response.status_code == 200
    assert response.json()["signed_out"] is True
    # Cleared by setting them empty and expired, which is how a cookie is
    # deleted; the browser is told about both.
    cleared = response.headers.get_list("set-cookie")
    assert any(STAFF_COOKIE in header for header in cleared)
    assert any(ID_TOKEN_COOKIE in header for header in cleared)


def test_signing_out_also_ends_the_session_at_the_provider(configured: TestClient) -> None:
    """Revoking locally and leaving the provider's cookie alone is not a
    sign-out: the next visit returns instantly with nothing asked for."""
    response = configured.post("/v1/auth/logout")

    assert response.json()["provider_logout"].startswith(f"{ISSUER}/protocol/openid-connect/logout")


def test_signing_out_twice_is_not_an_error(configured: TestClient) -> None:
    """Nobody leaving should be told their departure failed."""
    assert configured.post("/v1/auth/logout").status_code == 200
    assert configured.post("/v1/auth/logout").status_code == 200


def test_a_session_cookie_authenticates_a_request() -> None:
    """The whole point of the cookie: the console stops holding a bearer token.

    Minted directly here rather than through the provider, because what is
    being tested is that `principal_from` accepts the cookie at all.
    """
    clarity = Clarity(world=build_demo_world())
    api = TestClient(create_app(clarity))
    from clarity.platform.security.principal import Role

    issued = clarity.tokens.for_staff("sup-1", roles={Role.SUPERVISOR})

    api.cookies.set(STAFF_COOKIE, issued.value)
    me = api.get("/v1/auth/me")

    assert me.status_code == 200
    assert me.json()["subject"] == "sup-1"


def test_the_header_wins_over_a_stale_cookie() -> None:
    """A caller who sent a header is being explicit, and a stale cookie
    silently overriding it would be the harder bug to find."""
    clarity = Clarity(world=build_demo_world())
    api = TestClient(create_app(clarity))
    from clarity.platform.security.principal import Role

    good = clarity.tokens.for_staff("sup-1", roles={Role.SUPERVISOR})

    api.cookies.set(STAFF_COOKIE, "not-a-token")
    me = api.get("/v1/auth/me", headers={"Authorization": f"Bearer {good.value}"})

    assert me.status_code == 200
    assert me.json()["subject"] == "sup-1"


# --------------------------------------------------------------------------- #
# Seeing and ending your own sessions (B3)
# --------------------------------------------------------------------------- #


def _signed_in() -> tuple[TestClient, Clarity, str]:
    """A console signed in by cookie, as a browser is.

    Including the CSRF pair: a browser that holds a session cookie also holds
    the token it echoes, and a state-changing call without it is refused (B4).
    Setting only the session here would be testing a browser that cannot exist.
    """
    from clarity.platform.security.principal import Role

    clarity = Clarity(world=build_demo_world())
    api = TestClient(create_app(clarity))
    issued = clarity.tokens.for_staff("sup-1", roles={Role.SUPERVISOR})
    api.cookies.set(STAFF_COOKIE, issued.value)
    api.cookies.set(CSRF_COOKIE, "development-csrf-token")
    api.headers.update({CSRF_HEADER: "development-csrf-token"})
    return api, clarity, issued.value


def test_the_session_list_needs_a_session(configured: TestClient) -> None:
    assert configured.get("/v1/auth/sessions").status_code == 401
    assert configured.request("DELETE", "/v1/auth/sessions").status_code == 401


def test_a_person_sees_their_own_sessions_and_which_one_is_here() -> None:
    api, clarity, _ = _signed_in()
    from clarity.platform.security.principal import Role

    clarity.tokens.for_staff("sup-1", roles={Role.SUPERVISOR})

    listed = api.get("/v1/auth/sessions")

    assert listed.status_code == 200
    sessions = listed.json()["sessions"]
    assert len(sessions) == 2
    assert sum(1 for s in sessions if s["current"]) == 1


def test_the_session_list_hands_out_nothing_that_resumes_a_session() -> None:
    """A list read over somebody's shoulder must not also be a way in."""
    api, _, token = _signed_in()

    body = api.get("/v1/auth/sessions").text

    assert token not in body
    for field in ("token", "refresh_token", "jti"):
        assert field not in body


def test_signing_out_everywhere_keeps_this_device_by_default() -> None:
    api, clarity, _token = _signed_in()
    from clarity.platform.security.principal import Role

    clarity.tokens.for_staff("sup-1", roles={Role.SUPERVISOR})
    clarity.tokens.for_staff("sup-1", roles={Role.SUPERVISOR})

    ended = api.request("DELETE", "/v1/auth/sessions")

    assert ended.status_code == 200
    assert ended.json() == {"ended": 2, "kept_current": True}
    # Still signed in here.
    assert api.get("/v1/auth/sessions").status_code == 200


def test_signing_out_everywhere_can_include_this_device() -> None:
    api, clarity, _ = _signed_in()
    from clarity.platform.security.principal import Role

    clarity.tokens.for_staff("sup-1", roles={Role.SUPERVISOR})

    ended = api.request("DELETE", "/v1/auth/sessions", params={"keep_current": False})

    assert ended.json()["ended"] == 2
    assert api.get("/v1/auth/sessions").status_code == 401


def test_one_person_cannot_end_another_persons_sessions() -> None:
    api, clarity, _ = _signed_in()
    from clarity.platform.security.principal import Role

    theirs = clarity.tokens.for_staff("agent-1", roles={Role.AGENT})

    api.request("DELETE", "/v1/auth/sessions", params={"keep_current": False})

    assert clarity.tokens.verify(theirs.value).ref == "agent-1"


# --------------------------------------------------------------------------- #
# What the console asks before it draws a sign-in screen
# --------------------------------------------------------------------------- #


def test_sign_in_methods_reports_the_provider_when_configured(configured: TestClient) -> None:
    found = configured.get("/v1/auth/sign-in-methods")

    assert found.status_code == 200
    assert found.json()["provider"] is True


def test_sign_in_methods_reports_no_provider_when_it_is_not(unconfigured: TestClient) -> None:
    """The console must not offer a button that leads to a 404."""
    found = unconfigured.get("/v1/auth/sign-in-methods")

    assert found.json()["provider"] is False


def test_sign_in_methods_needs_no_session(unconfigured: TestClient) -> None:
    """It is read before anybody has signed in, which is the whole point."""
    assert unconfigured.get("/v1/auth/sign-in-methods").status_code == 200


def test_sign_in_methods_names_mechanisms_and_not_people(configured: TestClient) -> None:
    """Public, so it must say nothing about who can sign in."""
    body = configured.get("/v1/auth/sign-in-methods").json()

    assert set(body) == {"provider", "directory", "development_role_picker"}
    assert all(isinstance(value, bool) for value in body.values())
