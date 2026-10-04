"""Staff accounts for the synthetic profiles.

The Desk used to accept a role from the browser, with no password. A configured
directory closes that: the server looks up one account and assigns its role.
Production still federates HUTCH SSO; this file is the stand-in until then, and
the route that uses it does not exist in the prod profile (I9).

The file holds salted scrypt hashes, never passwords or step-up codes
(`scripts/staff_password.py` makes them), and a plaintext field is refused at
load. A missing username is checked against a dummy hash, so it takes as long
as a wrong password. The file is simulated staff, never a copy of a HUTCH
directory.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass

from clarity.platform.security.principal import Assurance, Role


class StaffDirectoryInvalid(ValueError):
    """The directory file cannot be loaded. Startup should stop."""


class LoginRefused(Exception):
    """The username, password, or step-up code did not match.

    One exception for every failure, so a caller cannot tell which field was
    wrong.
    """


@dataclass(frozen=True)
class StaffIdentity:
    """The person the directory says just signed in. The roles are not a choice."""

    user_ref: str
    roles: frozenset[Role]
    assurance: Assurance

    @property
    def role(self) -> Role:
        """The only role, when the account holds one."""
        return next(iter(self.roles))


@dataclass(frozen=True)
class _Account:
    username: str
    user_ref: str
    roles: frozenset[Role]
    password_hash: str
    step_up_hash: str


# scrypt cost: 2**14 x 8 needs about 16 MB and tens of milliseconds per check,
# which is what makes a stolen file slow to brute-force.
_N, _R, _P = 2**14, 8, 1


def hash_secret(secret: str) -> str:
    """A salted scrypt hash in the directory's `scrypt$N$r$p$salt$hash` form."""
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(secret.encode("utf-8"), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    encode = base64.urlsafe_b64encode
    return f"scrypt${_N}${_R}${_P}${encode(salt).decode()}${encode(digest).decode()}"


def _valid_hash(value: object) -> bool:
    parts = value.split("$") if isinstance(value, str) else []
    return len(parts) == 6 and parts[0] == "scrypt" and all(parts[1:])


def _matches(secret: str, stored: str) -> bool:
    _, n, r, p, salt, expected = stored.split("$")
    decode = base64.urlsafe_b64decode
    digest = hashlib.scrypt(
        secret.encode("utf-8"), salt=decode(salt), n=int(n), r=int(r), p=int(p), dklen=32
    )
    return hmac.compare_digest(digest, decode(expected))


# Checked when the username does not exist, so that path costs one scrypt too.
_DUMMY_HASH = hash_secret(secrets.token_urlsafe(16))


class StaffDirectory:
    """Username and password in, one staff identity out."""

    def __init__(self, accounts: tuple[_Account, ...]) -> None:
        self._by_username = {account.username: account for account in accounts}

    @classmethod
    def load(cls, raw: str) -> StaffDirectory:
        """Parse the JSON document. Raises :class:`StaffDirectoryInvalid`."""
        try:
            document = json.loads(raw)
        except json.JSONDecodeError as error:
            raise StaffDirectoryInvalid("staff directory is not JSON") from error
        rows = document.get("accounts") if isinstance(document, dict) else None
        if not isinstance(rows, list) or not rows:
            raise StaffDirectoryInvalid("staff directory needs a non-empty accounts list")

        accounts: list[_Account] = []
        seen_users: set[str] = set()
        seen_refs: set[str] = set()
        for row in rows:
            if not isinstance(row, dict):
                raise StaffDirectoryInvalid("each staff account must be an object")
            username = str(row.get("username", "")).strip()
            user_ref = str(row.get("user_ref", "")).strip()
            if "password" in row or "step_up_code" in row:
                raise StaffDirectoryInvalid(
                    f"{username or 'an account'} stores a plaintext secret; "
                    "use password_hash and step_up_hash"
                )
            password_hash = row.get("password_hash")
            step_up_hash = row.get("step_up_hash")
            if not username or not user_ref or not _valid_hash(password_hash):
                raise StaffDirectoryInvalid(
                    "each staff account needs username, user_ref, password_hash"
                )
            if not _valid_hash(step_up_hash):
                raise StaffDirectoryInvalid(f"{username} needs a step_up_hash")
            if username in seen_users or user_ref in seen_refs:
                raise StaffDirectoryInvalid(f"duplicate staff account: {username}")
            roles = _roles_for(row, username or "an account")
            seen_users.add(username)
            seen_refs.add(user_ref)
            accounts.append(
                _Account(
                    username=username,
                    user_ref=user_ref,
                    roles=roles,
                    password_hash=str(password_hash),
                    step_up_hash=str(step_up_hash),
                )
            )
        return cls(tuple(accounts))

    def authenticate(self, username: str, password: str, step_up_code: str) -> StaffIdentity:
        """Check the secret and return the account's own role.

        A wrong step-up code refuses the sign-in. Leaving the code empty signs
        in at ordinary MFA, which cannot approve above the cap.
        """
        account = self._by_username.get(username.strip())
        stored = account.password_hash if account is not None else _DUMMY_HASH
        if not _matches(password, stored) or account is None:
            raise LoginRefused("sign-in failed")
        code = step_up_code.strip()
        if code and not _matches(code, account.step_up_hash):
            raise LoginRefused("sign-in failed")
        assurance = Assurance.MFA_RECENT if code else Assurance.MFA
        return StaffIdentity(user_ref=account.user_ref, roles=account.roles, assurance=assurance)


def _roles_for(row: dict[str, object], username: str) -> frozenset[Role]:
    """One `role`, or a `roles` list. Both name existing jobs; neither is invented."""
    listed = row.get("roles")
    if isinstance(listed, list) and listed:
        names = [str(item).strip() for item in listed]
    else:
        names = [str(row.get("role", "")).strip()]
    if not names or any(not name for name in names):
        raise StaffDirectoryInvalid(f"{username} needs a role")
    found: set[Role] = set()
    for name in names:
        try:
            role = Role(name)
        except ValueError as error:
            raise StaffDirectoryInvalid(f"unknown role for {username}") from error
        if role is Role.CUSTOMER:
            raise StaffDirectoryInvalid(f"{username} cannot be a customer")
        found.add(role)
    return frozenset(found)
