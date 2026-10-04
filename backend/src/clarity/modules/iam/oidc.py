"""Staff sign-in through an OpenID Provider (B1, B2).

**Why the API does the code exchange and not the browser.** The console could
run the authorization code flow itself as a public client with PKCE, and that
is a supported pattern. It would also put an access token carrying staff roles
into JavaScript, on the one surface that approves refunds. So the API is the
confidential client: it performs the exchange, keeps what comes back, and hands
the browser a session cookie that is not a bearer token for anything else. The
current OAuth browser-apps guidance calls this a backend for frontend, and it
is the reason `clarity-console` is confidential rather than public in the realm.

**What this module is not.** It does not decide anything about a person. It
turns an authorization code into verified claims; the roles come from the
provider's token and are mapped by `KeycloakTokenVerifier` onto Clarity's
closed `Role` enum, where an unknown role grants nothing. Nothing here mints a
Clarity session either: the route does that, through `TokenIssuer`, so there is
one place that issues staff sessions whatever proved the identity.

**Step-up is the same flow with a level attached.** `acr_values` asks the
provider for a stronger authentication, and the realm's `acr.loa.map` is what
makes that request mean something: without it Keycloak ignores the parameter
and returns the session it already had, so a token would claim MFA for a
password-only sign-in. The verifier already reads `acr` and `auth_time` and
ages `MFA_RECENT` out after `STEP_UP_WINDOW`, so once the provider is asked
correctly the rest of the chain is in place.

Everything here is I16-labelled as simulated in the development realm: the
provider is a local Keycloak with synthetic accounts, and production federates
HUTCH SSO. **REQUIRES HUTCH CONFIRMATION.**
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import httpx

from clarity.kernel.common import utc_now
from clarity.platform.persistence import (
    MemoryStore,
    MemoryUnitOfWork,
    Repository,
    UnitOfWorkFactory,
)

#: The repository collection. Owned by the iam module (I6).
PENDING_LOGINS = "iam.pending_logins"

#: How long a started sign-in may take to come back. Longer than a person needs
#: to type a password and a code, short enough that an abandoned attempt is not
#: a credential sitting around. Not a policy value: it is the lifetime of a
#: protocol artefact, not a business rule.
LOGIN_TTL = timedelta(minutes=10)

#: Level names, matching the realm's `acr.loa.map`.
LOA_PASSWORD = "password"
LOA_MFA = "mfa"


class OidcError(RuntimeError):
    """The provider could not be used, or answered something unusable.

    One message, like `OtpRefused`: the detail belongs in the audit record and
    the log, never in the response. A sign-in that explains precisely why it
    failed is a sign-in that helps whoever is probing it.
    """

    def __init__(self, code: str = "OIDC_FAILED") -> None:
        super().__init__("sign-in failed")
        self.code = code


@dataclass(frozen=True)
class PendingLogin:
    """A sign-in that has been started and not yet come back.

    Held server side and keyed by `state`. The verifier `code_verifier` never
    leaves the API, which is what PKCE is for, and `nonce` is checked against
    the id token so a token minted for a different request cannot be replayed
    into this one.
    """

    state: str
    nonce: str
    code_verifier: str
    redirect_uri: str
    return_to: str
    requested_loa: str
    started_at: datetime
    expires_at: datetime
    #: Set when this is a step-up for an existing session rather than a sign-in.
    stepping_up: str | None = None

    def is_expired(self, now: datetime) -> bool:
        return now >= self.expires_at


@dataclass(frozen=True)
class ProviderTokens:
    """What the provider returned. Raw, unverified except for transport."""

    access_token: str
    id_token: str | None
    refresh_token: str | None
    expires_in: int


@dataclass(frozen=True)
class OidcSettings:
    """Where the provider is and who we are to it."""

    issuer: str
    client_id: str
    client_secret: str
    redirect_uri: str

    @property
    def authorization_endpoint(self) -> str:
        return f"{self.issuer.rstrip('/')}/protocol/openid-connect/auth"

    @property
    def token_endpoint(self) -> str:
        return f"{self.issuer.rstrip('/')}/protocol/openid-connect/token"

    @property
    def end_session_endpoint(self) -> str:
        return f"{self.issuer.rstrip('/')}/protocol/openid-connect/logout"


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def code_challenge_for(verifier: str) -> str:
    """S256, never plain. Plain offers no protection worth the parameter."""
    return _b64url(hashlib.sha256(verifier.encode("ascii")).digest())


class OidcLogin:
    """Starts and completes a sign-in against the provider.

    Pending logins go through the unit of work, not a dictionary on this
    object. They look like throwaway protocol state, and in one process they
    are, but the browser decides which replica receives the callback: with the
    state held in memory a sign-in started on one replica and returned to
    another fails, intermittently, in a way that looks like the provider
    misbehaving. `lite` gets the in-memory repository and `full` gets
    PostgreSQL, with no change here.

    Each record is claimed once and deleted on the way out, so a replayed
    callback finds nothing.
    """

    def __init__(
        self,
        settings: OidcSettings,
        *,
        client: httpx.Client | None = None,
        timeout_seconds: float = 5.0,
        ttl: timedelta = LOGIN_TTL,
        open_unit: UnitOfWorkFactory | None = None,
    ) -> None:
        if open_unit is None:
            store = MemoryStore()

            def open_memory_unit() -> MemoryUnitOfWork:
                return MemoryUnitOfWork(store)

            open_unit = open_memory_unit
        self._settings = settings
        self._client = client or httpx.Client(timeout=timeout_seconds)
        self._ttl = ttl
        self._open_unit = open_unit
        self._lock = threading.Lock()

    @property
    def settings(self) -> OidcSettings:
        return self._settings

    def start(
        self,
        *,
        return_to: str = "/",
        loa: str = LOA_PASSWORD,
        stepping_up: str | None = None,
        now: datetime | None = None,
    ) -> tuple[str, PendingLogin]:
        """Build the provider URL to send the browser to.

        Returns the URL and the pending record. `state` is the only part the
        browser carries, and it is a lookup key with no meaning of its own.
        """
        moment = now or utc_now()

        pending = PendingLogin(
            state=_b64url(secrets.token_bytes(32)),
            nonce=_b64url(secrets.token_bytes(32)),
            code_verifier=_b64url(secrets.token_bytes(64)),
            redirect_uri=self._settings.redirect_uri,
            return_to=return_to,
            requested_loa=loa,
            started_at=moment,
            expires_at=moment + self._ttl,
            stepping_up=stepping_up,
        )
        with self._lock, self._open_unit() as unit:
            self._expire(unit, moment)
            self._logins(unit).put(pending.state, pending)
            unit.commit()

        params = {
            "client_id": self._settings.client_id,
            "redirect_uri": pending.redirect_uri,
            "response_type": "code",
            # `openid` only. The realm declares its own `clientScopes`, and a
            # realm import treats that list as the whole set rather than an
            # addition, so Keycloak's stock `profile` and `email` scopes do not
            # exist here and asking for them is an `invalid_scope` refusal
            # before the login form ever renders. Nothing needs them either:
            # the identity Clarity uses is `sub` plus realm roles, which come
            # from the `basic` scope and the client's own role mapper.
            "scope": "openid",
            "state": pending.state,
            "nonce": pending.nonce,
            "code_challenge": code_challenge_for(pending.code_verifier),
            "code_challenge_method": "S256",
            # The level this sign-in has to reach. The realm's `acr.loa.map`
            # turns it into a condition on the OTP step.
            "acr_values": loa,
        }
        if stepping_up is not None:
            # A step-up must re-authenticate rather than hand back the session
            # already in the browser. Without this the provider would answer
            # from its cookie and the approval would rest on nothing new.
            params["prompt"] = "login"
            params["max_age"] = "0"

        url = f"{self._settings.authorization_endpoint}?{httpx.QueryParams(params)}"
        return url, pending

    def take(self, state: str, *, now: datetime | None = None) -> PendingLogin:
        """Claim a pending login, once.

        Removed on the way out, so a replayed callback finds nothing. A state
        that can be used twice is a state that can be used by someone else.
        """
        moment = now or utc_now()
        with self._lock, self._open_unit() as unit:
            logins = self._logins(unit)
            pending = logins.get(state)
            if pending is not None:
                logins.delete(state)
            self._expire(unit, moment)
            unit.commit()
        if pending is None or pending.is_expired(moment):
            raise OidcError("OIDC_UNKNOWN_STATE")
        return pending

    def exchange(self, code: str, pending: PendingLogin) -> ProviderTokens:
        """Trade the authorization code for tokens."""
        try:
            response = self._client.post(
                self._settings.token_endpoint,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": pending.redirect_uri,
                    "client_id": self._settings.client_id,
                    "client_secret": self._settings.client_secret,
                    "code_verifier": pending.code_verifier,
                },
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise OidcError("OIDC_EXCHANGE_FAILED") from error

        access_token = payload.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise OidcError("OIDC_NO_ACCESS_TOKEN")
        expires_in = payload.get("expires_in")
        return ProviderTokens(
            access_token=access_token,
            id_token=payload.get("id_token") if isinstance(payload.get("id_token"), str) else None,
            refresh_token=(
                payload.get("refresh_token")
                if isinstance(payload.get("refresh_token"), str)
                else None
            ),
            expires_in=int(expires_in) if isinstance(expires_in, int) else 0,
        )

    def end_session_url(self, *, id_token: str | None, redirect_to: str) -> str:
        """RP-initiated logout, so signing out of Clarity signs out of the IdP.

        Without this, "sign out" clears the Clarity session and the provider's
        cookie survives, so the next sign-in returns instantly with no
        credentials asked for. On a shared desk that is not a sign-out.
        """
        params: dict[str, str] = {
            "client_id": self._settings.client_id,
            "post_logout_redirect_uri": redirect_to,
        }
        if id_token:
            params["id_token_hint"] = id_token
        return f"{self._settings.end_session_endpoint}?{httpx.QueryParams(params)}"

    @staticmethod
    def _logins(unit: Any) -> Repository[str, PendingLogin]:
        repository: Repository[str, PendingLogin] = unit.repository(PENDING_LOGINS)
        return repository

    @staticmethod
    def _expire(unit: Any, now: datetime) -> None:
        """Housekeeping. `take` enforces the deadline, this clears the table."""
        logins = OidcLogin._logins(unit)
        # `keys()` is the Repository port's method, not a mapping's.
        stored: list[str] = logins.keys()
        for state in stored:
            found = logins.get(state)
            if found is not None and found.is_expired(now):
                logins.delete(state)

    def pending_count(self, *, now: datetime | None = None) -> int:
        """How many sign-ins are in flight. For the tests, never a route."""
        moment = now or utc_now()
        with self._open_unit() as unit:
            return sum(1 for item in self._logins(unit).values() if not item.is_expired(moment))


def nonce_matches(id_token: str, expected: str) -> bool:
    """Check the id token's nonce without verifying its signature.

    The signature is checked separately by the token verifier, against the
    provider's JWKS. This is the replay check: the claims are read only to
    compare one opaque value this process generated a moment ago, and nothing
    is trusted on the strength of it.
    """
    try:
        payload = id_token.split(".")[1]
        padded = payload + "=" * (-len(payload) % 4)
        claims: dict[str, Any] = json.loads(base64.urlsafe_b64decode(padded))
    except (IndexError, ValueError, TypeError):
        return False
    return secrets.compare_digest(str(claims.get("nonce", "")), expected)


__all__ = [
    "LOA_MFA",
    "LOA_PASSWORD",
    "LOGIN_TTL",
    "PENDING_LOGINS",
    "OidcError",
    "OidcLogin",
    "OidcSettings",
    "PendingLogin",
    "ProviderTokens",
    "code_challenge_for",
    "nonce_matches",
]
