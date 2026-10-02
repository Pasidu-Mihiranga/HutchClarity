"""The MCP resource server against a real Keycloak (A04, #8).

``tests/unit/test_mcp_network.py`` drives the whole network path with a token
issuer local to the test, which proves everything above the signature check.
What it cannot prove is that a **real** authorization server issues tokens in
the shape this server reads: the scope claim in particular is configuration, in
``config/keycloak/clarity-realm.json``, and configuration is exactly the kind of
thing a mock agrees with by construction.

So this lane asks Keycloak for each profile scope in turn and checks that the
resource server maps it onto the profile that scope is meant to select. It runs
in the `full` lane and skips without ``CLARITY_KEYCLOAK_URL``.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Iterator

import httpx
import pytest

from clarity.interfaces.mcp.auth import (
    ANALYTICS_SCOPE,
    CUSTOMER_SCOPE,
    STAFF_SCOPE,
    principal_from_claims,
)
from clarity.interfaces.mcp.resource_server import ClarityResourceServer
from clarity.interfaces.mcp.server import Profile
from clarity.modules.iam.public import KeycloakTokenVerifier

AUDIENCE = "clarity-api"
MCP_CLIENT = "clarity-mcp"
MCP_SECRET = "clarity-development-only-mcp-secret"
RESOURCE = "http://localhost:8081/mcp"


@pytest.fixture(scope="module")
def keycloak() -> Iterator[str]:
    base_url = os.environ.get("CLARITY_KEYCLOAK_URL")
    if not base_url:
        pytest.skip("set CLARITY_KEYCLOAK_URL to run against a real Keycloak")
    yield base_url.rstrip("/")


def _token(base_url: str, scope: str | None) -> str:
    form = {
        "client_id": MCP_CLIENT,
        "client_secret": MCP_SECRET,
        "grant_type": "client_credentials",
    }
    if scope:
        form["scope"] = scope
    with httpx.Client(timeout=20) as client:
        minted = client.post(f"{base_url}/realms/clarity/protocol/openid-connect/token", data=form)
    assert minted.status_code == 200, (
        f"Keycloak refused scope {scope!r}: {minted.text}. Is the client scope "
        "still declared in config/keycloak/clarity-realm.json and listed as an "
        "optional scope on clarity-mcp?"
    )
    return str(minted.json()["access_token"])


def _verified(base_url: str, scope: str | None) -> Profile:
    """Put a real token through the resource server and read its profile."""
    verifier = KeycloakTokenVerifier(f"{base_url}/realms/clarity", AUDIENCE)
    server = ClarityResourceServer(verifier, resource_url=RESOURCE)
    access = asyncio.run(server.verify_token(_token(base_url, scope)))
    assert access is not None, "a real Keycloak token must be accepted"
    return principal_from_claims(access.claims or {}).profile


@pytest.mark.parametrize(
    ("scope", "profile"),
    [
        (CUSTOMER_SCOPE, Profile.CUSTOMER_ASSIST),
        (STAFF_SCOPE, Profile.STAFF_ASSIST),
        (ANALYTICS_SCOPE, Profile.ANALYTICS),
    ],
)
def test_a_real_token_for_a_scope_selects_its_profile(
    keycloak: str, scope: str, profile: Profile
) -> None:
    """The realm, the token endpoint and the scope mapping, end to end."""
    assert _verified(keycloak, scope) is profile


def test_a_real_token_with_no_profile_scope_is_refused(keycloak: str) -> None:
    """Keycloak's default token carries `email profile` and nothing of ours.

    This is the shape an external client gets by simply authenticating without
    asking for a profile, so it is the most likely way a misconfigured client
    arrives. It must reach no tool set at all.
    """
    from clarity.interfaces.mcp.auth import TokenRejected

    with pytest.raises(TokenRejected) as error:
        _verified(keycloak, None)

    assert error.value.code == "NO_PROFILE_SCOPE"


def test_the_scopes_really_come_from_the_realm_and_not_from_the_test(
    keycloak: str,
) -> None:
    """Guard against this lane passing because Keycloak ignores the request.

    If the client scopes were removed from the realm, Keycloak would mint a
    token with ``email profile`` whatever was asked for, and the mapping tests
    above would fail on NO_PROFILE_SCOPE rather than silently pass. This states
    it directly so the reason is obvious when it breaks.
    """
    from clarity.interfaces.mcp.auth import scopes_of

    verifier = KeycloakTokenVerifier(f"{keycloak}/realms/clarity", AUDIENCE)
    server = ClarityResourceServer(verifier, resource_url=RESOURCE)
    access = asyncio.run(server.verify_token(_token(keycloak, STAFF_SCOPE)))
    assert access is not None

    assert STAFF_SCOPE in scopes_of(access.claims or {}), (
        "Keycloak did not put the requested scope in the token; the client "
        "scope is missing from the realm or not optional on clarity-mcp"
    )
