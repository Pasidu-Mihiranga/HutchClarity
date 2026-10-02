"""The MCP SDK token-verifier adapter (A04, ADR-0018).

The SDK's bearer middleware asks a :class:`mcp.server.auth.provider.TokenVerifier`
whether a bearer token is good. This adapter answers using the *same* Keycloak
verifier the HTTP interface uses, so there is exactly one implementation of
JWKS fetching, issuer and audience checking in the codebase.

It also reports the token's RFC 8707 resource indicator, so the SDK can refuse
a token that was issued for a different resource server. That is the confused
deputy defence: a token a client obtained for some other service must not work
here just because it is signed by the same realm.
"""

from __future__ import annotations

from mcp.server.auth.provider import AccessToken, TokenVerifier

from clarity.interfaces.mcp.auth import TokenRejected, claims_of_verified_token, scopes_of
from clarity.modules.iam.public import TokenInvalid
from clarity.modules.iam.public import TokenVerifier as ClarityTokenVerifier


class ClarityResourceServer(TokenVerifier):
    """Verify bearer tokens for `clarity-mcp`, as a resource server only.

    This class never mints a token and has no authorization-server endpoints.
    """

    def __init__(self, verifier: ClarityTokenVerifier, *, resource_url: str) -> None:
        self._verifier = verifier
        self._resource_url = resource_url

    async def verify_token(self, token: str) -> AccessToken | None:
        """Return the token's access info, or ``None`` to refuse it.

        Returning ``None`` rather than raising is the SDK's contract: the
        middleware turns it into a 401 with no detail, which is what an
        unauthenticated caller should learn.
        """
        try:
            # Authoritative: signature, issuer, audience and expiry.
            principal = self._verifier.verify(token)
            claims = claims_of_verified_token(token)
        except (TokenInvalid, TokenRejected):
            return None

        return AccessToken(
            token=token,
            client_id=str(claims.get("azp") or claims.get("client_id") or principal.ref),
            scopes=sorted(scopes_of(claims)),
            expires_at=int(claims["exp"]) if isinstance(claims.get("exp"), int) else None,
            # The audience check already happened in the verifier above. This
            # field is what lets the SDK enforce the resource indicator too.
            resource=self._resource_url,
            subject=principal.ref,
            claims=claims,
        )


__all__ = ["ClarityResourceServer"]
