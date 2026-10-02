"""OAuth 2.1 resource-server authentication for the MCP deployable (A04, ADR-0018).

This is the layer that decides *who is calling* when the caller is on the other
end of a network connection rather than inside the process.

While MCP was in-process, :class:`~clarity.interfaces.mcp.server.Principal` was
built by the orchestrator and could be trusted by construction. Over the
network the orchestrator is an external client, so every field of the principal
has to come from a token this server verified. Two properties matter most:

**The profile comes from a scope, not from the request.** A client cannot widen
itself by asking; it gets the profile its token was issued for. Exactly one
profile scope is required: none is a denial, and more than one is a denial
rather than a silent narrowing, so a misconfigured client registration fails
loudly instead of quietly getting the wrong tool set (I9).

**The case binding comes from a claim, not from the arguments.** A
customer-assist token is bound to one case by the authorization server. The
server refuses a case-scoped call from an unbound customer session, so a token
minted without the claim reaches nothing.

The server is a resource server only: it never issues tokens, and it never
forwards the client's token downstream (see :mod:`.exchange`).
"""

from __future__ import annotations

from typing import Any

import jwt

from clarity.interfaces.mcp.server import Principal, Profile
from clarity.modules.iam.public import TokenInvalid

#: Scope that selects each tool profile (plan 07 section 10.7).
CUSTOMER_SCOPE = "clarity.customer-assist"
STAFF_SCOPE = "clarity.staff-assist"
ANALYTICS_SCOPE = "clarity.analytics"

PROFILE_SCOPES: dict[str, Profile] = {
    CUSTOMER_SCOPE: Profile.CUSTOMER_ASSIST,
    STAFF_SCOPE: Profile.STAFF_ASSIST,
    ANALYTICS_SCOPE: Profile.ANALYTICS,
}

#: Claim carrying the case a customer-assist token is bound to.
CASE_CLAIM = "clarity_case_id"


class TokenRejected(PermissionError):
    """A bearer token was refused. The code is stable and safe to log."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code


def scopes_of(claims: dict[str, Any]) -> frozenset[str]:
    """The granted scopes, from OAuth's space-delimited ``scope`` claim.

    Accepts a list as well, which some authorization servers emit, so the
    caller does not have to care which shape its IdP uses.
    """
    raw = claims.get("scope")
    if isinstance(raw, str):
        return frozenset(raw.split())
    if isinstance(raw, list):
        return frozenset(value for value in raw if isinstance(value, str))
    return frozenset()


def profile_for_scopes(scopes: frozenset[str]) -> Profile:
    """The one profile a token's scopes select.

    Ambiguity is refused rather than resolved. Picking the narrowest profile
    would be defensible, but it would also mean a client registered with two
    profile scopes by mistake silently runs with the wrong tool set, and nobody
    finds out. A denial is noisy, and noisy is correct here.
    """
    present = sorted(scopes & PROFILE_SCOPES.keys())
    if not present:
        raise TokenRejected(
            "NO_PROFILE_SCOPE",
            f"a token needs exactly one of {sorted(PROFILE_SCOPES)}",
        )
    if len(present) > 1:
        raise TokenRejected(
            "AMBIGUOUS_PROFILE",
            f"a token must carry one profile scope, got {present}",
        )
    return PROFILE_SCOPES[present[0]]


def principal_from_claims(claims: dict[str, Any]) -> Principal:
    """Build the MCP principal from the claims of an already verified token.

    The caller must have verified the token's signature, issuer, audience and
    expiry first; this function only translates claims it is given.
    """
    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject:
        raise TokenRejected("NO_SUBJECT", "a token must identify its subject")
    if _looks_like_an_msisdn(subject):
        # A subject is a pseudonym (a Keycloak `sub` or a subscriber_ref), never
        # a phone number. If one ever arrives, the pseudonym boundary upstream
        # has broken and the number would be written into every audit row.
        raise TokenRejected("SUBJECT_NOT_PSEUDONYMOUS", "a subject must not be an MSISDN")

    case_id = claims.get(CASE_CLAIM)
    if case_id is not None and not isinstance(case_id, str):
        raise TokenRejected("INVALID_CASE_CLAIM", f"{CASE_CLAIM} must be a string")

    return Principal(
        ref=subject,
        profile=profile_for_scopes(scopes_of(claims)),
        case_id=case_id,
    )


def _looks_like_an_msisdn(value: str) -> bool:
    digits = value.lstrip("+")
    return digits.isdigit() and len(digits) >= 9


def claims_of_verified_token(token: str) -> dict[str, Any]:
    """Read the claims of a token whose signature has **already** been verified.

    Call this only after the authoritative verifier has accepted the token.

    The signature is deliberately not checked a second time. The alternative
    was to have this module decode and validate the token itself, which would
    mean two independent JWKS implementations: the one in
    :mod:`clarity.modules.iam.keycloak`, which is tested against a real
    Keycloak, and a copy here that is not. A copy is how the multi-key JWKS
    defect found in M-IAM would have survived in one path while being fixed in
    the other. One verifier, used by everything, is the safer shape even though
    it costs a second decode of the same string.
    """
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
    except jwt.PyJWTError as error:
        raise TokenRejected("MALFORMED_TOKEN", "the token could not be read") from error
    if not isinstance(payload, dict):
        raise TokenRejected("MALFORMED_TOKEN", "the token payload is not an object")
    return payload


__all__ = [
    "ANALYTICS_SCOPE",
    "CASE_CLAIM",
    "CUSTOMER_SCOPE",
    "PROFILE_SCOPES",
    "STAFF_SCOPE",
    "TokenInvalid",
    "TokenRejected",
    "claims_of_verified_token",
    "principal_from_claims",
    "profile_for_scopes",
    "scopes_of",
]
