"""Customer and staff token issuers (JWT via PyJWT when available)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from clarity.kernel.common import utc_now
from clarity.kernel.principal import Assurance, Principal, Role

try:
    import jwt as pyjwt

    _HAS_PYJWT = True
except ImportError:  # pragma: no cover
    _HAS_PYJWT = False

CUSTOMER_TOKEN_TTL = timedelta(minutes=10)
STAFF_TOKEN_TTL = timedelta(hours=8)
_ALGORITHM = "HS256"
_ISSUER = "clarity"
_DEFAULT_SECRET = b"clarity-lite-dev-secret-not-for-prod"


class TokenInvalid(ValueError):
    def __init__(self, detail: str = "the token is not valid") -> None:
        super().__init__(detail)


@dataclass(frozen=True, slots=True)
class IssuedToken:
    value: str
    expires_at: datetime
    principal: Principal


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _opaque_encode(claims: dict[str, Any], secret: bytes) -> str:
    """Fallback opaque session token when PyJWT is unavailable."""
    body = _b64url(json.dumps(claims, separators=(",", ":"), sort_keys=True).encode())
    sig = _b64url(hmac.new(secret, body.encode(), hashlib.sha256).digest())
    return f"clr.{body}.{sig}"


def _opaque_decode(token: str, secret: bytes) -> dict[str, Any]:
    try:
        prefix, body, sig = token.split(".", 2)
    except ValueError as error:
        raise TokenInvalid from error
    if prefix != "clr":
        raise TokenInvalid
    expected = _b64url(hmac.new(secret, body.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(expected, sig):
        raise TokenInvalid
    pad = "=" * (-len(body) % 4)
    try:
        return json.loads(base64.urlsafe_b64decode(body + pad))
    except (json.JSONDecodeError, ValueError) as error:
        raise TokenInvalid from error


class TokenIssuer:
    """Mints and validates Clarity session tokens."""

    def __init__(
        self,
        *,
        secret: bytes | None = None,
        audience: str = "clarity-api",
        kid: str = "clarity-iam-dev",
    ) -> None:
        self._secret = secret or _DEFAULT_SECRET
        self._audience = audience
        self._kid = kid

    def for_customer(
        self,
        subscriber_ref: str,
        *,
        assurance: Assurance = Assurance.OTP,
        channel: str = "web",
        delegations: set[str] | None = None,
        now: datetime | None = None,
    ) -> IssuedToken:
        moment = now or utc_now()
        expires = moment + CUSTOMER_TOKEN_TTL
        claims: dict[str, Any] = {
            "iss": _ISSUER,
            "aud": self._audience,
            "sub": subscriber_ref,
            "roles": [Role.CUSTOMER.value],
            "acr": assurance.value,
            "channel": channel,
            "delegations": sorted(delegations or set()),
            "iat": int(moment.timestamp()),
            "exp": int(expires.timestamp()),
        }
        return IssuedToken(
            value=self._encode(claims),
            expires_at=expires,
            principal=self._to_principal(claims),
        )

    def for_staff(
        self,
        user_ref: str,
        *,
        roles: set[Role],
        assurance: Assurance = Assurance.MFA,
        now: datetime | None = None,
    ) -> IssuedToken:
        moment = now or utc_now()
        expires = moment + STAFF_TOKEN_TTL
        claims: dict[str, Any] = {
            "iss": _ISSUER,
            "aud": self._audience,
            "sub": user_ref,
            "roles": sorted(role.value for role in roles),
            "acr": assurance.value,
            "iat": int(moment.timestamp()),
            "exp": int(expires.timestamp()),
            "auth_time": int(moment.timestamp()),
        }
        return IssuedToken(
            value=self._encode(claims),
            expires_at=expires,
            principal=self._to_principal(claims),
        )

    def verify(self, token: str, *, now: datetime | None = None) -> Principal:
        if not token:
            raise TokenInvalid
        claims = self._decode(token)
        if now is not None and int(claims["exp"]) <= int(now.timestamp()):
            raise TokenInvalid
        return self._to_principal(claims)

    def _encode(self, claims: dict[str, Any]) -> str:
        if _HAS_PYJWT:
            return pyjwt.encode(
                claims,
                self._secret,
                algorithm=_ALGORITHM,
                headers={"kid": self._kid},
            )
        return _opaque_encode(claims, self._secret)

    def _decode(self, token: str) -> dict[str, Any]:
        if _HAS_PYJWT and not token.startswith("clr."):
            try:
                return pyjwt.decode(
                    token,
                    self._secret,
                    algorithms=[_ALGORITHM],
                    audience=self._audience,
                    issuer=_ISSUER,
                    options={"require": ["exp", "iat", "sub", "aud", "iss"]},
                )
            except pyjwt.InvalidTokenError as error:
                raise TokenInvalid from error
        return _opaque_decode(token, self._secret)

    def _to_principal(self, claims: dict[str, Any]) -> Principal:
        role_values = claims.get("roles") or []
        roles = {Role(v) for v in role_values if isinstance(v, str) and v in set(Role)}
        assurance_raw = str(claims.get("acr", Assurance.ANONYMOUS.value))
        try:
            assurance = Assurance(assurance_raw)
        except ValueError:
            assurance = Assurance.ANONYMOUS
        subject = str(claims["sub"])
        is_customer = Role.CUSTOMER in roles
        delegations_raw = claims.get("delegations") or []
        delegations = {d for d in delegations_raw if isinstance(d, str)}
        return Principal.from_roles(
            subject=subject,
            roles=roles,
            subscriber_ref=subject if is_customer else None,
            assurance=assurance,
            delegations=delegations,
        )


def new_staff_ref() -> str:
    return f"staff_{secrets.token_hex(8)}"
