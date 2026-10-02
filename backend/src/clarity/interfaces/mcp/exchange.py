"""Downstream credentials for `clarity-mcp` (RFC 8693, ADR-0018).

ADR-0018 forbids token passthrough: the token an external MCP client presents
must never be replayed against `clarity-api`. A passed-through token carries the
client's full audience and scope set, so a compromised or over-privileged client
would reach everything that token can reach, and `clarity-api`'s audit would
record the client as the actor with no sign that MCP was in the path.

So a downstream call uses a **new** token, obtained by exchanging the client's
token for one with a narrowed audience, acting for the same subject.

**Not configured means refused, not forwarded.** If no exchange endpoint is set,
:class:`NoDownstreamCredential` is raised. The tempting fallback - "just use the
incoming token for now" - is exactly the behaviour the ADR prohibits, and it
would be invisible in tests that only check that the call succeeded.
"""

from __future__ import annotations

import httpx

GRANT_TYPE = "urn:ietf:params:oauth:grant-type:token-exchange"
TOKEN_TYPE = "urn:ietf:params:oauth:token-type:access_token"


class NoDownstreamCredential(RuntimeError):
    """No exchanged token could be obtained, so the call must not be made."""


class TokenExchange:
    """Exchange an inbound token for a narrowed downstream one (RFC 8693)."""

    def __init__(
        self,
        exchange_url: str | None,
        *,
        audience: str,
        client_id: str,
        client_secret: str | None = None,
        timeout_seconds: float = 3.0,
        client: httpx.Client | None = None,
    ) -> None:
        self._url = exchange_url
        self._audience = audience
        self._client_id = client_id
        self._client_secret = client_secret
        self._client = client or httpx.Client(timeout=timeout_seconds)

    def for_subject(self, inbound_token: str) -> str:
        """The token to send downstream, never the one that came in."""
        if not self._url:
            raise NoDownstreamCredential(
                "no token-exchange endpoint is configured, so there is no "
                "downstream credential. The inbound token is deliberately not "
                "forwarded (ADR-0018)."
            )
        form = {
            "grant_type": GRANT_TYPE,
            "subject_token": inbound_token,
            "subject_token_type": TOKEN_TYPE,
            "requested_token_type": TOKEN_TYPE,
            "audience": self._audience,
            "client_id": self._client_id,
        }
        if self._client_secret:
            form["client_secret"] = self._client_secret
        try:
            response = self._client.post(self._url, data=form)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise NoDownstreamCredential("the token exchange failed") from error

        token = payload.get("access_token") if isinstance(payload, dict) else None
        if not isinstance(token, str) or not token:
            raise NoDownstreamCredential("the token exchange returned no access token")
        if token == inbound_token:
            # An authorization server that echoes the subject token back has
            # not narrowed anything, and using it would be passthrough with
            # extra steps.
            raise NoDownstreamCredential(
                "the exchange returned the inbound token unchanged, which is passthrough"
            )
        return token


__all__ = ["GRANT_TYPE", "TOKEN_TYPE", "NoDownstreamCredential", "TokenExchange"]
