"""The Keycloak driver against a real Keycloak (M-IAM, A04 prerequisite).

The driver was written and tested only against ``httpx.MockTransport``, which is
the same position the OPA and OpenBao drivers were in, and both of those turned
out to have real problems. This is the lane that runs it against the service.

It found two, recorded here because the tests exist to keep them fixed:

**The JWKS had more than one key.** Keycloak publishes an RS256 signing key and
an RSA-OAEP encryption key. The driver built its key map in one comprehension,
so ``PyJWK.from_dict`` raising on the encryption key aborted the whole set and
the driver rejected **every** token a real Keycloak issued. Staff SSO would have
refused every login. A mock JWKS publishing one signing key cannot show that up.

**The realm minted no audience for the API.** Keycloak's default audience is
``account``, so a resource server verifying its own name rejected everything.
The realm now carries an audience mapper, because a resource server that does
not check an audience naming itself will accept a token minted for a different
service.
"""

from __future__ import annotations

import base64
import json
import os
from collections.abc import Iterator
from dataclasses import dataclass

import httpx
import pytest

from clarity.modules.iam.keycloak import KeycloakTokenVerifier, _signing_keys
from clarity.modules.iam.tokens import TokenInvalid
from clarity.platform.security.principal import Assurance, Role

AUDIENCE = "clarity-api"
MCP_CLIENT = "clarity-mcp"
WANTED_ROLES = ("agent", "supervisor")


@dataclass(frozen=True)
class _Realm:
    """A live Keycloak with a service account that holds known roles."""

    base_url: str
    issuer: str
    token: str


#: The development secret from ``config/keycloak/clarity-realm.json``. Fixed on
#: purpose: the realm is only ever imported into a dev-mode Keycloak, and
#: production registers the client with a generated secret from the secrets
#: store.
MCP_SECRET = "clarity-development-only-mcp-secret"


@pytest.fixture(scope="module")
def realm() -> Iterator[_Realm]:
    """A real token from a real Keycloak, using no admin access.

    The realm file grants the service account its roles and fixes the client
    secret, so this only needs the realm's own token endpoint. An earlier
    version drove the admin API, which was both slower and fragile: Keycloak 26
    creates a *temporary* bootstrap admin, and its master realm refuses tokens
    over plain HTTP, so the fixture broke in two different ways before the realm
    was made self-contained.
    """
    base_url = os.environ.get("CLARITY_KEYCLOAK_URL")
    if not base_url:
        pytest.skip("set CLARITY_KEYCLOAK_URL to run against a real Keycloak")
    base_url = base_url.rstrip("/")

    with httpx.Client(timeout=20) as client:
        minted = client.post(
            f"{base_url}/realms/clarity/protocol/openid-connect/token",
            data={
                "client_id": MCP_CLIENT,
                "client_secret": MCP_SECRET,
                "grant_type": "client_credentials",
            },
        )
        assert minted.status_code == 200, (
            f"could not mint a token: {minted.text}. Is the clarity realm "
            "imported, and does it still carry the audience mapper and the "
            "service account's roles?"
        )
        yield _Realm(
            base_url=base_url,
            issuer=f"{base_url}/realms/clarity",
            token=str(minted.json()["access_token"]),
        )


def _claims(token: str) -> dict[str, object]:
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return dict(json.loads(base64.urlsafe_b64decode(payload)))


# -- the driver accepts a real token -------------------------------------- #


def test_a_real_keycloak_token_verifies(realm: _Realm) -> None:
    principal = KeycloakTokenVerifier(realm.issuer, AUDIENCE).verify(realm.token)

    assert principal.ref, "the subject must come through"
    assert Role.AGENT in principal.roles
    assert Role.SUPERVISOR in principal.roles


def test_keycloaks_own_roles_are_not_granted(realm: _Realm) -> None:
    """The role enum is closed: `offline_access` and friends grant nothing.

    Keycloak adds `offline_access`, `uma_authorization` and
    `default-roles-clarity` to every token. A system that mapped unknown role
    names onto permissions would be letting Keycloak's defaults widen access.
    """
    claims = _claims(realm.token)
    realm_roles = set(claims.get("realm_access", {}).get("roles", []))  # type: ignore[union-attr]
    assert "offline_access" in realm_roles, "this test needs Keycloak's defaults present"

    principal = KeycloakTokenVerifier(realm.issuer, AUDIENCE).verify(realm.token)

    assert {role.value for role in principal.roles} == set(WANTED_ROLES)


def test_a_machine_token_is_recognised_as_mcp(realm: _Realm) -> None:
    """A client-credentials token is an agent, not a person at a browser."""
    assert KeycloakTokenVerifier(realm.issuer, AUDIENCE).verify(realm.token).channel == "mcp"


def test_a_client_credentials_token_carries_no_step_up(realm: _Realm) -> None:
    """A machine has not passed MFA, so it must not be treated as if it had."""
    principal = KeycloakTokenVerifier(realm.issuer, AUDIENCE).verify(realm.token)

    assert principal.assurance is not Assurance.MFA_RECENT


# -- the two bugs this lane found ----------------------------------------- #


def test_the_published_jwks_has_more_than_one_key(realm: _Realm) -> None:
    """The first bug, pinned at its source.

    If Keycloak ever published only a signing key this test would pass for the
    wrong reason, so it asserts the condition that broke the driver is present.
    """
    published = httpx.get(f"{realm.issuer}/protocol/openid-connect/certs", timeout=10).json()[
        "keys"
    ]

    uses = {key.get("use") for key in published}
    assert len(published) > 1, "Keycloak used to publish a signing and an encryption key"
    assert "enc" in uses, "the encryption key is what aborted the key map"

    usable = _signing_keys(published)
    assert usable, "no signing key survived, so no token can ever verify"
    encryption_kids = {key["kid"] for key in published if key.get("use") == "enc"}
    assert not (encryption_kids & set(usable)), (
        "an encryption key was accepted as a verification key"
    )


def test_the_token_names_the_api_as_an_audience(realm: _Realm) -> None:
    """The second bug. Keycloak's default audience is `account`, not the API."""
    audience = _claims(realm.token).get("aud")
    audiences = {audience} if isinstance(audience, str) else set(audience or ())

    assert AUDIENCE in audiences, (
        f"the realm minted {audiences} and not {AUDIENCE!r}; the audience mapper "
        "on the clarity-mcp client is missing, and a resource server that does "
        "not verify its own audience accepts tokens minted for other services"
    )


# -- the refusals ---------------------------------------------------------- #


def test_a_token_for_another_audience_is_refused(realm: _Realm) -> None:
    with pytest.raises(TokenInvalid):
        KeycloakTokenVerifier(realm.issuer, "some-other-service").verify(realm.token)


def test_a_token_from_another_issuer_is_refused(realm: _Realm) -> None:
    with pytest.raises(TokenInvalid):
        KeycloakTokenVerifier("http://localhost:8081/realms/not-clarity", AUDIENCE).verify(
            realm.token
        )


def test_a_tampered_token_is_refused(realm: _Realm) -> None:
    header, payload, signature = realm.token.split(".")
    tampered = f"{header}.{payload}.{signature[:-4]}AAAA"

    with pytest.raises(TokenInvalid):
        KeycloakTokenVerifier(realm.issuer, AUDIENCE).verify(tampered)


def test_an_unsigned_token_is_refused(realm: _Realm) -> None:
    """`alg: none` is the oldest JWT attack and must not be in the allow list."""
    header = base64.urlsafe_b64encode(
        json.dumps({"alg": "none", "typ": "JWT", "kid": "x"}).encode()
    ).rstrip(b"=")
    payload = realm.token.split(".")[1].encode()

    with pytest.raises(TokenInvalid):
        KeycloakTokenVerifier(realm.issuer, AUDIENCE).verify(
            f"{header.decode()}.{payload.decode()}."
        )
