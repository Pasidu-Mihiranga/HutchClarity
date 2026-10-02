"""Keycloak OIDC token verification for staff and machine clients.

The driver trusts only a configured issuer, audience, signing algorithm and
JWKS key. Realm and client roles are mapped onto Clarity's closed role enum;
unknown roles grant nothing.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx
import jwt

from clarity.kernel.common import utc_now
from clarity.modules.iam.tokens import STEP_UP_WINDOW, TokenInvalid, TokenVerifier
from clarity.platform.security.principal import Assurance, Principal, Role

_ALGORITHMS = ("RS256", "ES256", "EdDSA")


def _role_names(claims: dict[str, Any], audience: str) -> set[str]:
    names: set[str] = set()
    realm_access = claims.get("realm_access")
    if isinstance(realm_access, dict):
        roles = realm_access.get("roles")
        if isinstance(roles, list):
            names.update(value for value in roles if isinstance(value, str))
    resource_access = claims.get("resource_access")
    if isinstance(resource_access, dict):
        client_access = resource_access.get(audience)
        if isinstance(client_access, dict):
            roles = client_access.get("roles")
            if isinstance(roles, list):
                names.update(value for value in roles if isinstance(value, str))
    return names


def _signing_keys(keys: list[Any]) -> dict[str, Any]:
    """The usable signing keys from a JWKS, skipping the rest.

    Keycloak publishes more than one key: an RS256 key for signatures and an
    RSA-OAEP key for encryption. ``PyJWK.from_dict`` has no algorithm for the
    encryption key and raises.

    This is loaded key by key, and a key that cannot be loaded is skipped. An
    earlier version built the whole map in one comprehension, so the encryption
    key's failure aborted the set and the driver rejected **every** token a real
    Keycloak issued, valid ones included. A mock JWKS publishing only a signing
    key cannot show that up, which is why this is tested against the real
    service.

    Encryption keys are skipped rather than merely tolerated: a key published
    for encrypting must never be accepted as proof of a signature.
    """
    usable: dict[str, Any] = {}
    for item in keys:
        if not isinstance(item, dict) or not isinstance(item.get("kid"), str):
            continue
        if item.get("use") not in (None, "sig"):
            continue
        if item.get("alg") is not None and item["alg"] not in _ALGORITHMS:
            continue
        try:
            usable[str(item["kid"])] = jwt.PyJWK.from_dict(item).key
        except jwt.PyJWTError:
            # Not a key this library can use for verification. Another key in
            # the set may still be the one that signed this token.
            continue
    if not usable:
        raise TokenInvalid
    return usable


class KeycloakTokenVerifier:
    """Validate Keycloak access tokens against its published JWKS."""

    def __init__(
        self,
        issuer: str,
        audience: str,
        *,
        jwks_url: str | None = None,
        timeout_seconds: float = 3.0,
        client: httpx.Client | None = None,
    ) -> None:
        self._issuer = issuer.rstrip("/")
        self._audience = audience
        self._jwks_url = jwks_url or f"{self._issuer}/protocol/openid-connect/certs"
        self._client = client or httpx.Client(timeout=timeout_seconds)
        self._keys: dict[str, Any] = {}

    def _key(self, kid: str) -> Any:
        if kid in self._keys:
            return self._keys[kid]
        try:
            response = self._client.get(self._jwks_url)
            response.raise_for_status()
            payload = response.json()
            keys = payload.get("keys") if isinstance(payload, dict) else None
            if not isinstance(keys, list):
                raise TokenInvalid
            self._keys = _signing_keys(keys)
            return self._keys[kid]
        except (httpx.HTTPError, KeyError, TypeError, ValueError, jwt.PyJWTError) as error:
            raise TokenInvalid from error

    def verify(self, token: str, *, now: datetime | None = None) -> Principal:
        if not token:
            raise TokenInvalid
        try:
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")
            algorithm = header.get("alg")
            if not isinstance(kid, str) or algorithm not in _ALGORITHMS:
                raise TokenInvalid
            claims = jwt.decode(
                token,
                self._key(kid),
                algorithms=[algorithm],
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["exp", "iat", "sub", "aud", "iss"]},
            )
        except (jwt.InvalidTokenError, KeyError, TypeError, ValueError) as error:
            raise TokenInvalid from error

        moment = now or utc_now()
        if int(claims["exp"]) <= int(moment.timestamp()):
            raise TokenInvalid

        role_names = _role_names(claims, self._audience)
        roles = frozenset(Role(name) for name in role_names if name in set(Role))
        acr = str(claims.get("acr", ""))
        assurance = Assurance.MFA if acr in {"mfa", "mfa-recent"} else Assurance.NONE
        auth_time = claims.get("auth_time")
        if acr == "mfa-recent" and isinstance(auth_time, int):
            authenticated = datetime.fromtimestamp(auth_time, tz=moment.tzinfo)
            if moment - authenticated <= STEP_UP_WINDOW:
                assurance = Assurance.MFA_RECENT

        return Principal(
            ref=str(claims["sub"]),
            roles=roles,
            assurance=assurance,
            channel="mcp" if claims.get("client_id") or claims.get("azp") else "staff-web",
        )


class CompositeTokenVerifier:
    """Try the local customer issuer, then the external staff issuer."""

    def __init__(self, *verifiers: TokenVerifier) -> None:
        if not verifiers:
            raise ValueError("at least one token verifier is required")
        self._verifiers = verifiers

    def verify(self, token: str, *, now: datetime | None = None) -> Principal:
        for verifier in self._verifiers:
            try:
                return verifier.verify(token, now=now)
            except TokenInvalid:
                continue
        raise TokenInvalid


__all__ = ["CompositeTokenVerifier", "KeycloakTokenVerifier"]
