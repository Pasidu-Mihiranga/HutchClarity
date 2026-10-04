"""Scope to profile, the case binding, and downstream credentials (A04, #8).

These are the units behind the network tests in ``test_mcp_network.py``: what a
token is allowed to mean, and what `clarity-mcp` sends downstream.
"""

from __future__ import annotations

import httpx
import pytest

from clarity.interfaces.mcp.auth import (
    ANALYTICS_SCOPE,
    CASE_CLAIM,
    CUSTOMER_SCOPE,
    STAFF_SCOPE,
    TokenRejected,
    claims_of_verified_token,
    principal_from_claims,
    profile_for_scopes,
    scopes_of,
)
from clarity.interfaces.mcp.exchange import NoDownstreamCredential, TokenExchange
from clarity.interfaces.mcp.server import Profile

# --------------------------------------------------------------------------- #
# Scopes
# --------------------------------------------------------------------------- #


def test_a_space_delimited_scope_claim_is_read():
    """OAuth's own shape, and the one Keycloak emits."""
    assert scopes_of({"scope": "email profile clarity.staff-assist"}) == frozenset(
        {"email", "profile", STAFF_SCOPE}
    )


def test_a_list_scope_claim_is_read_too():
    """Some authorization servers emit a list. Both are accepted."""
    assert scopes_of({"scope": [CUSTOMER_SCOPE, "email"]}) == frozenset({CUSTOMER_SCOPE, "email"})


def test_a_missing_scope_claim_is_no_scopes_rather_than_an_error():
    assert scopes_of({}) == frozenset()


@pytest.mark.parametrize(
    ("scope", "profile"),
    [
        (CUSTOMER_SCOPE, Profile.CUSTOMER_ASSIST),
        (STAFF_SCOPE, Profile.STAFF_ASSIST),
        (ANALYTICS_SCOPE, Profile.ANALYTICS),
    ],
)
def test_each_profile_scope_selects_its_profile(scope: str, profile: Profile):
    assert profile_for_scopes(frozenset({scope})) is profile


def test_no_profile_scope_is_refused():
    """Deny by default: a token with only `email` gets no tool set at all."""
    with pytest.raises(TokenRejected) as error:
        profile_for_scopes(frozenset({"email", "profile"}))

    assert error.value.code == "NO_PROFILE_SCOPE"


def test_two_profile_scopes_are_refused_rather_than_narrowed():
    """A misconfigured client registration must fail loudly, not quietly.

    Choosing the narrowest profile would be safe for the request and bad for
    the operator: the client would work, with the wrong tool set, and nobody
    would find out until an audit.
    """
    with pytest.raises(TokenRejected) as error:
        profile_for_scopes(frozenset({CUSTOMER_SCOPE, STAFF_SCOPE}))

    assert error.value.code == "AMBIGUOUS_PROFILE"


def test_other_scopes_alongside_a_profile_scope_are_ignored():
    """`email` and `profile` ride along on every Keycloak token."""
    scopes = frozenset({"email", "profile", "openid", STAFF_SCOPE})

    assert profile_for_scopes(scopes) is Profile.STAFF_ASSIST


# --------------------------------------------------------------------------- #
# The principal
# --------------------------------------------------------------------------- #


def test_the_case_binding_comes_from_the_claim():
    principal = principal_from_claims(
        {"sub": "client-1", "scope": CUSTOMER_SCOPE, CASE_CLAIM: "CASE-7"}
    )

    assert principal.profile is Profile.CUSTOMER_ASSIST
    assert principal.case_id == "CASE-7"


def test_a_customer_token_may_carry_no_binding_and_is_stopped_at_the_call():
    """Translating is not authorizing.

    An unbound customer principal is a legal shape to build; the server refuses
    the call (``SESSION_NOT_BOUND``). Keeping the refusal in one place means
    there is one chokepoint to audit, not two.
    """
    principal = principal_from_claims({"sub": "client-1", "scope": CUSTOMER_SCOPE})

    assert principal.case_id is None


def test_a_token_with_no_subject_is_refused():
    with pytest.raises(TokenRejected) as error:
        principal_from_claims({"scope": STAFF_SCOPE})

    assert error.value.code == "NO_SUBJECT"


def test_a_non_string_case_claim_is_refused():
    with pytest.raises(TokenRejected) as error:
        principal_from_claims({"sub": "c", "scope": CUSTOMER_SCOPE, CASE_CLAIM: 7})

    assert error.value.code == "INVALID_CASE_CLAIM"


@pytest.mark.parametrize("subject", ["+94781234567", "94781234567", "0781234567"])
def test_a_subject_that_is_a_phone_number_is_refused(subject: str):
    """The subject is a pseudonym, never an MSISDN.

    Every audit row records the subject. If a raw number ever arrives as `sub`,
    the pseudonym boundary upstream has broken, and writing it into the audit
    would spread the breach rather than contain it.
    """
    with pytest.raises(TokenRejected) as error:
        principal_from_claims({"sub": subject, "scope": STAFF_SCOPE})

    assert error.value.code == "SUBJECT_NOT_PSEUDONYMOUS"


def test_a_pseudonymous_subject_is_accepted():
    """Guards the test above against a rule that refuses every subject."""
    principal = principal_from_claims(
        {"sub": "f3440094-c0f4-4455-81b7-80a8b7b527e8", "scope": STAFF_SCOPE}
    )

    assert principal.profile is Profile.STAFF_ASSIST


def test_a_malformed_token_cannot_be_read():
    with pytest.raises(TokenRejected) as error:
        claims_of_verified_token("not-a-jwt")

    assert error.value.code == "MALFORMED_TOKEN"


# --------------------------------------------------------------------------- #
# Downstream: no passthrough (ADR-0018)
# --------------------------------------------------------------------------- #


def test_with_no_exchange_configured_the_call_is_refused_not_forwarded():
    """The failure mode the ADR cares about.

    "Unconfigured" must not degrade into "use the client's token", because
    that is passthrough and a test asserting only that the call worked would
    never notice.
    """
    exchange = TokenExchange(None, audience="clarity-api", client_id="clarity-mcp")

    with pytest.raises(NoDownstreamCredential):
        exchange.for_subject("inbound-token")


def test_the_exchanged_token_is_sent_downstream():
    def handler(request: httpx.Request) -> httpx.Response:
        body = request.content.decode()
        assert "grant_type=urn%3Aietf%3Aparams%3Aoauth%3Agrant-type%3Atoken-exchange" in body
        assert "audience=clarity-api" in body
        return httpx.Response(200, json={"access_token": "narrowed-token"})

    exchange = TokenExchange(
        "https://idp.test/token",
        audience="clarity-api",
        client_id="clarity-mcp",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert exchange.for_subject("inbound-token") == "narrowed-token"


def test_an_exchange_that_echoes_the_inbound_token_is_refused():
    """Passthrough with extra steps is still passthrough."""

    def echo(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"access_token": "inbound-token"})

    exchange = TokenExchange(
        "https://idp.test/token",
        audience="clarity-api",
        client_id="clarity-mcp",
        client=httpx.Client(transport=httpx.MockTransport(echo)),
    )

    with pytest.raises(NoDownstreamCredential):
        exchange.for_subject("inbound-token")


def test_an_exchange_failure_refuses_rather_than_falling_back():
    def down(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    exchange = TokenExchange(
        "https://idp.test/token",
        audience="clarity-api",
        client_id="clarity-mcp",
        client=httpx.Client(transport=httpx.MockTransport(down)),
    )

    with pytest.raises(NoDownstreamCredential):
        exchange.for_subject("inbound-token")
