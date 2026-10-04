"""Staff accounts for the synthetic profiles.

The Desk used to accept a role from the browser, with no password. A configured
directory closes that: the server looks up one account and assigns its role.
Production still federates HUTCH SSO; this file is the stand-in until then, and
the route that uses it does not exist in the prod profile (I9).

Passwords stay in the directory file (mode 0600 on a deployment). They are
compared by digest so a missing username and a wrong password take the same
path. The file is simulated staff, never a copy of a HUTCH directory.
"""

from __future__ import annotations

import hashlib
import hmac
import json
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
    """The person the directory says just signed in. The role is not a choice."""

    user_ref: str
    role: Role
    assurance: Assurance


@dataclass(frozen=True)
class _Account:
    username: str
    user_ref: str
    role: Role
    password: str
    step_up_code: str


def _digest(value: str) -> bytes:
    return hashlib.sha256(value.encode("utf-8")).digest()


def _same(left: str, right: str) -> bool:
    return hmac.compare_digest(_digest(left), _digest(right))


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
            role_name = str(row.get("role", "")).strip()
            password = row.get("password")
            step_up_code = row.get("step_up_code")
            if not username or not user_ref or not isinstance(password, str) or not password:
                raise StaffDirectoryInvalid("each staff account needs username, user_ref, password")
            if not isinstance(step_up_code, str) or not step_up_code:
                raise StaffDirectoryInvalid(f"{username} needs a step-up code")
            if username in seen_users or user_ref in seen_refs:
                raise StaffDirectoryInvalid(f"duplicate staff account: {username}")
            try:
                role = Role(role_name)
            except ValueError as error:
                raise StaffDirectoryInvalid(f"unknown role for {username}") from error
            if role is Role.CUSTOMER:
                raise StaffDirectoryInvalid(f"{username} cannot be a customer")
            seen_users.add(username)
            seen_refs.add(user_ref)
            accounts.append(
                _Account(
                    username=username,
                    user_ref=user_ref,
                    role=role,
                    password=password,
                    step_up_code=step_up_code,
                )
            )
        return cls(tuple(accounts))

    def authenticate(self, username: str, password: str, step_up_code: str) -> StaffIdentity:
        """Check the secret and return the account's own role.

        A wrong step-up code refuses the sign-in. Leaving the code empty signs
        in at ordinary MFA, which cannot approve above the cap.
        """
        account = self._by_username.get(username.strip())
        expected_password = account.password if account is not None else "\0"
        if account is None or not _same(password, expected_password):
            raise LoginRefused("sign-in failed")
        code = step_up_code.strip()
        if code and not _same(code, account.step_up_code):
            raise LoginRefused("sign-in failed")
        assurance = Assurance.MFA_RECENT if code else Assurance.MFA
        return StaffIdentity(user_ref=account.user_ref, role=account.role, assurance=assurance)
