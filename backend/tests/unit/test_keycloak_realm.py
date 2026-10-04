"""The shipped realm carries what staff sign-in needs (B1, B2).

These read `config/keycloak/clarity-realm.json` and run everywhere, which is
the point. The integration lane proves the same things against a real Keycloak
but needs one running, and two of its checks need the password grant enabled,
which the realm deliberately leaves off. A test that skips in CI protects
nothing.

Each assertion here exists because the thing it checks was missing, and missing
silently: the realm imported cleanly, the provider issued tokens, and the
failure only appeared when somebody tried to sign in.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REALM = Path(__file__).resolve().parents[3] / "config" / "keycloak" / "clarity-realm.json"


@pytest.fixture(scope="module")
def realm() -> dict:
    return json.loads(REALM.read_text(encoding="utf-8"))


def _client(realm: dict, client_id: str) -> dict:
    found = next((c for c in realm["clients"] if c["clientId"] == client_id), None)
    assert found is not None, f"the realm has no {client_id} client"
    return found


def test_the_realm_declares_the_basic_scope(realm: dict) -> None:
    """`basic` is what emits `sub`, and `KeycloakTokenVerifier` requires `sub`.

    A realm import treats `clientScopes` as the whole set rather than an
    addition, so declaring the three Clarity scopes removed Keycloak's built-in
    ones. Every staff token arrived without a subject and our own verifier
    rejected it. Nothing in the import or the provider complained.
    """
    names = {scope["name"] for scope in realm["clientScopes"]}

    assert "basic" in names, "no basic scope: tokens carry no sub and the API refuses them all"


def test_the_realm_declares_the_acr_scope(realm: dict) -> None:
    """`acr` is what carries the level of assurance.

    Without it a stepped-up session is indistinguishable from a password one,
    so a step-up asks for a one-time code and grants nothing for it.
    """
    names = {scope["name"] for scope in realm["clientScopes"]}

    assert "acr" in names


@pytest.mark.parametrize("client_id", ["clarity-api", "clarity-mcp", "clarity-console"])
def test_every_client_gets_the_subject_and_the_level(realm: dict, client_id: str) -> None:
    """Declaring a scope is not enough; a client has to be given it."""
    defaults = _client(realm, client_id).get("defaultClientScopes", [])

    assert "basic" in defaults, f"{client_id} mints tokens with no sub"
    assert "acr" in defaults, f"{client_id} mints tokens with no acr"


def test_the_console_client_is_confidential(realm: dict) -> None:
    """The browser never holds a provider token, so the API needs a secret."""
    console = _client(realm, "clarity-console")

    assert console.get("publicClient") is False
    assert console.get("secret")
    assert console.get("standardFlowEnabled") is True


def test_the_console_client_requires_pkce(realm: dict) -> None:
    console = _client(realm, "clarity-console")

    assert console["attributes"]["pkce.code.challenge.method"] == "S256"


def test_the_console_client_cannot_take_a_password_directly(realm: dict) -> None:
    """The direct access grant bypasses the browser flow, and with it the
    step-up condition. A browser client has no business accepting one."""
    console = _client(realm, "clarity-console")

    assert console.get("directAccessGrantsEnabled") is False


def test_the_realm_maps_levels_of_assurance(realm: dict) -> None:
    """Without `acr.loa.map` Keycloak ignores `acr_values` entirely.

    It answers from the session it already has, the token comes back claiming
    the level, and the approval rests on a password typed an hour ago. This map
    is what makes a step-up request mean anything.
    """
    mapped = json.loads(realm["attributes"]["acr.loa.map"])

    assert mapped == {"password": "1", "mfa": "2"}


def test_the_step_up_flow_is_the_browser_flow(realm: dict) -> None:
    """A flow nothing uses is a flow that is not running."""
    assert realm["browserFlow"] == "clarity-browser-stepup"

    aliases = {flow["alias"] for flow in realm["authenticationFlows"]}
    assert {"clarity-browser-stepup", "clarity-loa-1", "clarity-loa-2"} <= aliases


def test_the_second_factor_is_conditional_on_the_requested_level(realm: dict) -> None:
    """Level 2 runs the OTP form, and only when the client asked for level 2."""
    loa2 = next(f for f in realm["authenticationFlows"] if f["alias"] == "clarity-loa-2")
    authenticators = [e.get("authenticator") for e in loa2["authenticationExecutions"]]

    assert "conditional-level-of-authentication" in authenticators
    assert "auth-otp-form" in authenticators

    config = next(
        c for c in realm["authenticatorConfig"] if c["alias"] == "clarity-loa-2-condition"
    )
    assert config["config"]["loa-condition-level"] == "2"


def test_every_role_has_somebody_who_can_exercise_it(realm: dict) -> None:
    """Otherwise a permission path has no way to be driven end to end."""
    roles = {role["name"] for role in realm["roles"]["realm"]}
    held = {role for user in realm["users"] for role in user.get("realmRoles", [])}

    assert roles <= held, f"no staff account holds: {sorted(roles - held)}"


def test_the_accounts_that_move_money_carry_a_second_factor(realm: dict) -> None:
    """A step-up against an account with no OTP credential loops rather than
    refusing, so the roles that can be asked for one must have one."""
    needs_otp = {"supervisor", "finance", "compliance", "platform_admin", "security_admin"}

    for user in realm["users"]:
        # Service accounts are machine identities. They never see a browser, so
        # they cannot be stepped up and must not be expected to carry a second
        # factor; what bounds them is the tool allowlist and their audience.
        if user["username"].startswith("service-account"):
            continue
        if needs_otp & set(user.get("realmRoles", [])):
            kinds = {credential["type"] for credential in user.get("credentials", [])}
            assert "otp" in kinds, f"{user['username']} can be asked to step up and cannot"


def test_the_simulated_accounts_are_labelled(realm: dict) -> None:
    """I16: a synthetic identity is never presented as a real one."""
    staff = [u for u in realm["users"] if not u["username"].startswith("service-account")]

    assert staff
    for user in staff:
        assert user.get("attributes", {}).get("simulated") == ["yes"]
