"""Issuing and validating Clarity tokens (plan §19 identity, ADR-0010).

Two issuers, deliberately separate:

**Customers** get a short-lived token from Clarity itself, because a customer's
identity in production belongs to HUTCH and the issuer must be replaceable. The
subject is the ``subscriber_ref`` pseudonym, never the raw MSISDN - a token is
copied into logs and proxies, and a phone number there is a leak.

**Staff** get a token from the staff issuer. In production that is HUTCH SSO
(Keycloak federating AD/Entra); here it is a development issuer with seeded
users, which is why the Desk shows a role picker labelled as simulated.

Tokens are EdDSA (Ed25519), short-lived, and carry the assurance level
(``acr``) so a route can demand recent MFA for an approval without re-reading
the user store.
"""

from __future__ import annotations

import base64
import hashlib
import os
import secrets
import tempfile
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Protocol, runtime_checkable

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from clarity.kernel.common import utc_now
from clarity.platform.persistence import (
    MemoryStore,
    MemoryUnitOfWork,
    Repository,
    UnitOfWorkFactory,
)
from clarity.platform.security.principal import Assurance, Principal, Role

#: Customer tokens are short: long enough to finish a journey, short enough
#: that a captured one is near-useless. ASSUMPTION, pending HUTCH policy.
CUSTOMER_TOKEN_TTL = timedelta(minutes=10)

#: Staff sessions last a shift; anything that moves money needs step-up anyway.
STAFF_TOKEN_TTL = timedelta(hours=8)
REFRESH_TOKEN_TTL = timedelta(days=30)

#: The longest a session may live, counted from the authentication that started
#: it and never extended.
#:
#: `REFRESH_TOKEN_TTL` alone did not bound anything. It was recomputed on every
#: issue, including every refresh, so the window slid forward each time: a
#: session refreshed once a month never expired, and a stolen refresh token was
#: a permanent credential for an account whose owner had proved a one-time code
#: once, long ago. The sliding window is still what makes an idle session
#: expire; this is what makes an *active* one end (B3).
#:
#: **ASSUMPTION - REQUIRES HUTCH CONFIRMATION.** Thirty days matches the
#: refresh window that was already here, so a session that is used regularly
#: now ends where an idle one always did.
ABSOLUTE_SESSION_TTL = timedelta(days=30)

#: How recently MFA must have happened to count as step-up.
STEP_UP_WINDOW = timedelta(minutes=5)

_ALGORITHM = "EdDSA"
_ISSUER = "clarity"

SESSIONS = "iam.sessions"
REFRESH_TOKENS = "iam.refresh_tokens"


class TokenInvalid(ValueError):
    """A token was missing, malformed, expired or not meant for us.

    Every failure says the same thing to the caller: a token that reveals *why*
    it failed is a probing oracle.
    """

    def __init__(self, detail: str = "the token is not valid") -> None:
        super().__init__(detail)


@runtime_checkable
class TokenVerifier(Protocol):
    """Validate a bearer token and return its authenticated principal."""

    def verify(self, token: str, *, now: datetime | None = None) -> Principal: ...


def _strings(value: object) -> tuple[str, ...]:
    """The string members of a claim that should be a list of strings.

    Claims arrive inside a token, so their shape is attacker-influenced. A
    malformed claim yields nothing rather than raising, which denies rather
    than crashes.
    """
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str))


@dataclass(frozen=True)
class IssuedToken:
    value: str
    expires_at: datetime
    principal: Principal
    refresh_token: str | None = None


@dataclass
class SessionRecord:
    jti: str
    principal: Principal
    expires_at: datetime
    refresh_expires_at: datetime
    revoked: bool = False
    #: When the authentication that started this session happened. Carried
    #: across every refresh, never reset, so the absolute cap means something.
    #: Defaulted for records written before B3 added it, which read back as a
    #: session that started when it was last issued: the cap then applies from
    #: that point rather than retroactively signing everybody out.
    started_at: datetime | None = None

    def started(self) -> datetime:
        """When this session began, falling back to its own issue time."""
        return self.started_at or self.refresh_expires_at - REFRESH_TOKEN_TTL


def _load_or_create_key(key_path: Path | None) -> Ed25519PrivateKey:
    """The issuer key: in memory, or loaded from ``key_path``, created once.

    Several processes (API, MCP, channel gateway) may start together on one
    shared key directory. Each writes a complete key to its own temporary file
    and publishes it with ``os.link``, which is atomic and fails if the key
    already exists. A reader therefore sees no key or a whole one, never a
    half-written file, and every process ends up with the same key.
    """
    if key_path is None:
        return Ed25519PrivateKey.generate()
    key_path.parent.mkdir(parents=True, exist_ok=True)
    if not key_path.exists():
        candidate = Ed25519PrivateKey.generate()
        fd, tmp = tempfile.mkstemp(dir=key_path.parent, prefix=".iam-issuer-")
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(
                    candidate.private_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PrivateFormat.PKCS8,
                        encryption_algorithm=serialization.NoEncryption(),
                    )
                )
            os.chmod(tmp, 0o600)
            try:
                os.link(tmp, key_path)
                return candidate
            except FileExistsError:
                pass  # another process published first: use its key
        finally:
            os.unlink(tmp)
    loaded = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
    if not isinstance(loaded, Ed25519PrivateKey):
        raise TypeError(f"{key_path} does not hold an Ed25519 private key")
    return loaded


class TokenIssuer:
    """Mints and validates Clarity tokens.

    **Prototype note.** The key is generated in memory, or, with ``key_path``,
    kept in a file so sessions survive a restart or a redeploy. Production uses
    the KMS/HSM-backed signer and publishes the public key for validators,
    exactly as receipt signing does.
    """

    def __init__(
        self,
        *,
        audience: str = "clarity-api",
        kid: str = "clarity-iam-dev",
        open_unit: UnitOfWorkFactory | None = None,
        key_path: Path | None = None,
    ) -> None:
        self._private = _load_or_create_key(key_path)
        self._public = self._private.public_key()
        self._audience = audience
        self._kid = kid
        if open_unit is None:
            store = MemoryStore()

            def open_memory_unit() -> MemoryUnitOfWork:
                return MemoryUnitOfWork(store)

            open_unit = open_memory_unit
        self._open_unit = open_unit
        self._lock = threading.Lock()

    # -- minting ---------------------------------------------------------- #

    def for_customer(
        self,
        subscriber_ref: str,
        *,
        assurance: Assurance,
        channel: str,
        delegations: set[str] | None = None,
        now: datetime | None = None,
        started_at: datetime | None = None,
    ) -> IssuedToken:
        """A customer token. The subject is the pseudonym, never the number."""
        moment = now or utc_now()
        expires = moment + CUSTOMER_TOKEN_TTL
        claims = {
            "iss": _ISSUER,
            "aud": self._audience,
            "sub": subscriber_ref,
            "roles": [Role.CUSTOMER.value],
            "acr": assurance.value,
            "channel": channel,
            "delegations": sorted(delegations or set()),
            "iat": int(moment.timestamp()),
            "exp": int(expires.timestamp()),
            "jti": secrets.token_urlsafe(18),
        }
        return self._issue(claims, expires=expires, now=moment, started_at=started_at)

    def for_staff(
        self,
        user_ref: str,
        *,
        roles: set[Role],
        assurance: Assurance = Assurance.MFA,
        now: datetime | None = None,
        started_at: datetime | None = None,
    ) -> IssuedToken:
        moment = now or utc_now()
        expires = moment + STAFF_TOKEN_TTL
        claims = {
            "iss": _ISSUER,
            "aud": self._audience,
            "sub": user_ref,
            "roles": sorted(role.value for role in roles),
            "acr": assurance.value,
            "iat": int(moment.timestamp()),
            "exp": int(expires.timestamp()),
            "jti": secrets.token_urlsafe(18),
            # When MFA happened, so step-up can be judged at request time
            # rather than trusting a claim that never ages.
            "auth_time": int(moment.timestamp()),
        }
        return self._issue(claims, expires=expires, now=moment, started_at=started_at)

    def _issue(
        self,
        claims: dict[str, object],
        *,
        expires: datetime,
        now: datetime,
        started_at: datetime | None = None,
    ) -> IssuedToken:
        principal = self._to_principal(claims, now=now)
        refresh = secrets.token_urlsafe(32)
        refresh_hash = hashlib.sha256(refresh.encode("utf-8")).hexdigest()
        began = started_at or now
        # The idle window still slides, but never past the absolute deadline:
        # a refresh token handed out near the end of a session's life expires
        # with the session rather than outliving it.
        record = SessionRecord(
            jti=str(claims["jti"]),
            principal=principal,
            expires_at=expires,
            refresh_expires_at=min(now + REFRESH_TOKEN_TTL, began + ABSOLUTE_SESSION_TTL),
            started_at=began,
        )
        with self._lock, self._open_unit() as unit:
            sessions: Repository[str, SessionRecord] = unit.repository(SESSIONS)
            refreshes: Repository[str, str] = unit.repository(REFRESH_TOKENS)
            sessions.put(record.jti, record)
            refreshes.put(refresh_hash, record.jti)
            unit.commit()
        return IssuedToken(
            value=self._encode(claims),
            expires_at=expires,
            principal=principal,
            refresh_token=refresh,
        )

    def _encode(self, claims: dict[str, object]) -> str:
        return jwt.encode(
            claims,
            self._private,
            algorithm=_ALGORITHM,
            headers={"kid": self._kid},
        )

    # -- validating ------------------------------------------------------- #

    def verify(self, token: str, *, now: datetime | None = None) -> Principal:
        """Validate a token and build the principal it describes."""
        if not token:
            raise TokenInvalid

        try:
            claims = jwt.decode(
                token,
                self._public,
                # Only EdDSA is accepted, so a token claiming `alg: none` or a
                # symmetric algorithm is rejected rather than trusted.
                algorithms=[_ALGORITHM],
                audience=self._audience,
                issuer=_ISSUER,
                options={"require": ["exp", "iat", "sub", "aud", "iss", "jti"]},
            )
        except jwt.InvalidTokenError as error:
            raise TokenInvalid from error

        # PyJWT checks `exp` against the real clock. When a caller supplies its
        # own `now` the whole judgement must follow that clock, or an injected
        # time would age step-up while leaving expiry unchecked.
        if now is not None and int(claims["exp"]) <= int(now.timestamp()):
            raise TokenInvalid

        with self._open_unit() as unit:
            sessions: Repository[str, SessionRecord] = unit.repository(SESSIONS)
            session = sessions.get(str(claims["jti"]))
        if session is None or session.revoked:
            raise TokenInvalid

        return self._to_principal(claims, now=now)

    def revoke(self, token: str) -> None:
        """Revoke one access token and its refresh token immediately."""
        self.verify(token)
        claims = jwt.decode(token, options={"verify_signature": False})
        jti = str(claims["jti"])
        with self._lock, self._open_unit() as unit:
            sessions: Repository[str, SessionRecord] = unit.repository(SESSIONS)
            record = sessions.get(jti)
            if record is None:
                raise TokenInvalid
            record.revoked = True
            sessions.put(jti, record)
            unit.commit()

    def session_id(self, token: str) -> str | None:
        """The stored session a token belongs to, or None if it is not valid.

        Verified first, so an unverifiable token cannot name a session it does
        not own. Returning the id rather than the record keeps the caller from
        reading somebody's session out of a token they merely hold.
        """
        try:
            self.verify(token)
        except TokenInvalid:
            return None
        claims = jwt.decode(token, options={"verify_signature": False})
        return str(claims["jti"])

    def sessions_for(self, ref: str, *, now: datetime | None = None) -> list[SessionRecord]:
        """Every live session belonging to one subject, newest first.

        Scans the collection. That is honest for the sizes involved and wrong
        at HUTCH's: the `full` profile wants an index on the subject, which is
        a migration rather than a change here. Recorded so it is a decision and
        not an oversight.
        """
        moment = now or utc_now()
        with self._lock, self._open_unit() as unit:
            sessions: Repository[str, SessionRecord] = unit.repository(SESSIONS)
            live = [
                record
                for record in sessions.values()
                if record.principal.ref == ref
                and not record.revoked
                and moment < record.refresh_expires_at
            ]
        return sorted(live, key=lambda record: record.started(), reverse=True)

    def revoke_all(self, ref: str, *, keep: str | None = None) -> int:
        """End every session this subject holds. Returns how many were ended.

        `keep` spares one session id, which is what "sign out everywhere else"
        needs: somebody who has just discovered a session they do not recognise
        should not have to sign in again on the device they are holding.
        """
        ended = 0
        with self._lock, self._open_unit() as unit:
            sessions: Repository[str, SessionRecord] = unit.repository(SESSIONS)
            for record in sessions.values():
                if record.principal.ref != ref or record.revoked or record.jti == keep:
                    continue
                record.revoked = True
                sessions.put(record.jti, record)
                ended += 1
            unit.commit()
        return ended

    def refresh(self, refresh_token: str, *, now: datetime | None = None) -> IssuedToken:
        """Rotate a refresh token and issue a new access session."""
        moment = now or utc_now()
        digest = hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()
        with self._lock, self._open_unit() as unit:
            refreshes: Repository[str, str] = unit.repository(REFRESH_TOKENS)
            sessions: Repository[str, SessionRecord] = unit.repository(SESSIONS)
            jti = refreshes.get(digest)
            record = sessions.get(jti) if jti is not None else None
            if record is None or record.revoked or moment >= record.refresh_expires_at:
                raise TokenInvalid
            record.revoked = True
            sessions.put(record.jti, record)
            refreshes.delete(digest)
            unit.commit()

        began = record.started()
        if moment >= began + ABSOLUTE_SESSION_TTL:
            # The session has run its full life. Refreshing again would extend
            # it indefinitely, which is what this cap exists to stop: the
            # person signs in again and proves who they are.
            raise TokenInvalid

        principal = record.principal
        if Role.CUSTOMER in principal.roles:
            assert principal.subscriber_ref is not None
            return self.for_customer(
                principal.subscriber_ref,
                assurance=principal.assurance,
                channel=principal.channel or "web",
                delegations=set(principal.delegations),
                now=moment,
                started_at=began,
            )
        assurance = (
            Assurance.MFA if principal.assurance is Assurance.MFA_RECENT else principal.assurance
        )
        return self.for_staff(
            principal.ref,
            roles=set(principal.roles),
            assurance=assurance,
            now=moment,
            started_at=began,
        )

    def _to_principal(self, claims: dict[str, object], *, now: datetime | None = None) -> Principal:
        roles = frozenset(
            Role(value) for value in _strings(claims.get("roles")) if value in set(Role)
        )
        assurance = Assurance(str(claims.get("acr", Assurance.NONE.value)))

        # Step-up ages. A token minted with MFA hours ago is a valid session
        # but is not recent re-authentication, so it cannot approve.
        auth_time = claims.get("auth_time")
        if assurance is Assurance.MFA_RECENT and isinstance(auth_time, int):
            moment = now or utc_now()
            authenticated = datetime.fromtimestamp(auth_time, tz=moment.tzinfo)
            if moment - authenticated > STEP_UP_WINDOW:
                assurance = Assurance.MFA

        subject = str(claims["sub"])
        is_customer = Role.CUSTOMER in roles
        return Principal(
            ref=subject,
            roles=roles,
            assurance=assurance,
            subscriber_ref=subject if is_customer else None,
            channel=channel if isinstance(channel := claims.get("channel"), str) else None,
            delegations=frozenset(_strings(claims.get("delegations"))),
        )

    # -- publication ------------------------------------------------------ #

    def public_key_jwk(self) -> dict[str, str]:
        """The public key, for a validator that is not this process."""
        raw = self._public.public_bytes(
            encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
        )
        return {
            "kty": "OKP",
            "crv": "Ed25519",
            "kid": self._kid,
            "alg": _ALGORITHM,
            "use": "sig",
            "x": base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii"),
        }


def step_up(
    issuer: TokenIssuer, principal: Principal, *, now: datetime | None = None
) -> IssuedToken:
    """Re-authenticate a staff member for an approval.

    In production this is a real re-authentication against the IdP. Here it
    re-mints the token with recent MFA, which is why the Desk labels it as
    simulated.
    """
    return issuer.for_staff(
        principal.ref,
        roles=set(principal.roles),
        assurance=Assurance.MFA_RECENT,
        now=now,
    )
