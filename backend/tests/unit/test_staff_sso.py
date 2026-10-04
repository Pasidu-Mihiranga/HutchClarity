"""Staff sign-in through the provider (B1, B2, B3).

No Keycloak here. These cover the half that is ours: what the API sends to the
provider, what it does with what comes back, and what it refuses. The lane that
runs against a real Keycloak is `tests/integration/test_keycloak.py`, and the
realm's step-up flow is only exercised there.

The refusals are the point of most of this file. An authorization code flow is
a sequence of redirects an attacker can see and partly influence, so the tests
that matter are the ones where something is wrong.
"""

from __future__ import annotations

from datetime import timedelta
from urllib.parse import parse_qs, urlparse

import pytest

from clarity.kernel.common import utc_now
from clarity.modules.iam.public import (
    LOA_MFA,
    LOA_PASSWORD,
    OidcError,
    OidcLogin,
    OidcSettings,
    code_challenge_for,
    nonce_matches,
)

ISSUER = "http://127.0.0.1:8081/realms/clarity"


@pytest.fixture
def login() -> OidcLogin:
    return OidcLogin(
        OidcSettings(
            issuer=ISSUER,
            client_id="clarity-console",
            client_secret="development-only",
            redirect_uri="http://127.0.0.1:8000/v1/auth/staff/oidc/callback",
        )
    )


def _params(url: str) -> dict[str, str]:
    return {key: values[0] for key, values in parse_qs(urlparse(url).query).items()}


def test_the_authorization_request_carries_pkce_and_a_nonce(login: OidcLogin) -> None:
    url, pending = login.start()
    query = _params(url)

    assert url.startswith(f"{ISSUER}/protocol/openid-connect/auth")
    assert query["response_type"] == "code"
    assert query["client_id"] == "clarity-console"
    assert query["code_challenge_method"] == "S256"
    assert query["code_challenge"] == code_challenge_for(pending.code_verifier)
    assert query["state"] == pending.state
    assert query["nonce"] == pending.nonce


def test_the_verifier_never_leaves_the_api(login: OidcLogin) -> None:
    """PKCE is worth nothing if the verifier travels with the challenge."""
    url, pending = login.start()

    assert pending.code_verifier not in url


def test_two_sign_ins_share_nothing(login: OidcLogin) -> None:
    _, first = login.start()
    _, second = login.start()

    assert first.state != second.state
    assert first.nonce != second.nonce
    assert first.code_verifier != second.code_verifier


def test_a_plain_sign_in_asks_for_the_password_level(login: OidcLogin) -> None:
    url, _ = login.start()

    assert _params(url)["acr_values"] == LOA_PASSWORD
    assert "prompt" not in _params(url)


def test_a_step_up_demands_a_fresh_authentication(login: OidcLogin) -> None:
    """Without `prompt=login` the provider answers from its own cookie.

    The token would come back claiming MFA and the approval would rest on the
    password somebody typed an hour ago. This is the parameter that makes a
    step-up a step-up.
    """
    url, _ = login.start(loa=LOA_MFA, stepping_up="sup-1")
    query = _params(url)

    assert query["acr_values"] == LOA_MFA
    assert query["prompt"] == "login"
    assert query["max_age"] == "0"


def test_a_state_can_be_claimed_once(login: OidcLogin) -> None:
    """A replayed callback must find nothing.

    A state that can be used twice is a state somebody else can use.
    """
    _, pending = login.start()
    assert login.take(pending.state).state == pending.state

    with pytest.raises(OidcError):
        login.take(pending.state)


def test_an_unknown_state_is_refused(login: OidcLogin) -> None:
    with pytest.raises(OidcError):
        login.take("not-a-state-this-api-issued")


def test_an_abandoned_sign_in_expires(login: OidcLogin) -> None:
    now = utc_now()
    _, pending = login.start(now=now)

    with pytest.raises(OidcError):
        login.take(pending.state, now=now + timedelta(minutes=11))


def test_an_expired_sign_in_is_not_left_lying_around(login: OidcLogin) -> None:
    now = utc_now()
    login.start(now=now)
    assert login.pending_count(now=now) == 1

    login.start(now=now + timedelta(minutes=11))

    assert login.pending_count(now=now + timedelta(minutes=11)) == 1


def test_a_refusal_says_the_same_thing_however_it_failed(login: OidcLogin) -> None:
    """One message, like `OtpRefused`. The detail belongs in the trail."""
    unknown = OidcError("OIDC_UNKNOWN_STATE")
    exchange = OidcError("OIDC_EXCHANGE_FAILED")

    assert str(unknown) == str(exchange) == "sign-in failed"
    assert unknown.code != exchange.code


# --------------------------------------------------------------------------- #
# The nonce check
# --------------------------------------------------------------------------- #


def _id_token(nonce: str) -> str:
    """An unsigned id token. The signature is checked elsewhere, by the
    verifier, against the provider's JWKS: this is only the replay check."""
    import base64
    import json

    def segment(data: dict[str, object]) -> str:
        raw = json.dumps(data).encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    return f"{segment({'alg': 'RS256'})}.{segment({'nonce': nonce})}.signature"


def test_an_id_token_for_another_request_is_rejected() -> None:
    assert nonce_matches(_id_token("the-right-one"), "the-right-one")
    assert not nonce_matches(_id_token("a-different-request"), "the-right-one")


def test_an_id_token_with_no_nonce_is_rejected() -> None:
    import base64
    import json

    header = base64.urlsafe_b64encode(json.dumps({"alg": "RS256"}).encode()).decode().rstrip("=")
    body = base64.urlsafe_b64encode(json.dumps({"sub": "x"}).encode()).decode().rstrip("=")

    assert not nonce_matches(f"{header}.{body}.sig", "expected")


def test_a_malformed_id_token_is_rejected_not_raised() -> None:
    """A malformed token is an attacker's input, not an exception path."""
    assert not nonce_matches("not-a-jwt", "expected")
    assert not nonce_matches("", "expected")


# --------------------------------------------------------------------------- #
# Logout
# --------------------------------------------------------------------------- #


def test_the_logout_url_tells_the_provider_who_is_leaving(login: OidcLogin) -> None:
    """Without an `id_token_hint` the provider may prompt, and a sign-out that
    needs a confirmation click is one people skip."""
    url = login.end_session_url(id_token="an-id-token", redirect_to="http://127.0.0.1:3101")
    query = _params(url)

    assert url.startswith(f"{ISSUER}/protocol/openid-connect/logout")
    assert query["id_token_hint"] == "an-id-token"
    assert query["post_logout_redirect_uri"] == "http://127.0.0.1:3101"


def test_a_logout_without_an_id_token_still_works(login: OidcLogin) -> None:
    url = login.end_session_url(id_token=None, redirect_to="http://127.0.0.1:3101")

    assert "id_token_hint" not in _params(url)
    assert _params(url)["client_id"] == "clarity-console"
