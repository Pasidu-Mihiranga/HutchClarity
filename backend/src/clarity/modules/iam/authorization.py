"""Authorization policy ports and drivers.

The Python driver is the reference implementation used by the lite profile.
The OPA driver sends the same small, explicit input document to a Rego policy
in the full profile. Any network error or malformed OPA response denies the
request.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import httpx

from clarity.platform.security.principal import (
    STEP_UP_PERMISSIONS,
    Permission,
    Principal,
    role_override_maps,
)


@runtime_checkable
class AuthorizationPolicy(Protocol):
    """Decide one permission for one authenticated principal."""

    def allows(self, principal: Principal, permission: Permission) -> bool: ...


class PythonAuthorizationPolicy:
    """Reference driver over the checked-in role-permission catalogue."""

    def allows(self, principal: Principal, permission: Permission) -> bool:
        if not principal.has(permission):
            return False
        return permission not in STEP_UP_PERMISSIONS or principal.assurance.is_step_up


class OpaAuthorizationPolicy:
    """OPA REST driver. Failure is a denial, never an implicit allow."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = 2.0,
        client: httpx.Client | None = None,
    ) -> None:
        self._client = client or httpx.Client(timeout=timeout_seconds)
        self._url = f"{base_url.rstrip('/')}/v1/data/clarity/authz/allow"

    def allows(self, principal: Principal, permission: Permission) -> bool:
        attached, detached = role_override_maps()
        try:
            response = self._client.post(
                self._url,
                json={
                    "input": {
                        "subject": principal.ref,
                        "roles": sorted(role.value for role in principal.roles),
                        "permission": permission.value,
                        "assurance": principal.assurance.value,
                        # The Rego reads `input.granted` and the driver did not
                        # send it, so the branch that stops a holder of a
                        # granted audit duty from moving money could never
                        # fire. `GrantAwareAuthorizationPolicy` enforces the
                        # same rule in Python first, so nothing was reachable
                        # through it; what was wrong is that the two drivers
                        # were only in parity because one of them was wrapped.
                        # Remove the wrapper and the Rego would quietly stop
                        # enforcing rule 1. Now it stands on its own.
                        "granted": sorted(granted.value for granted in principal.granted),
                        # Role matrix overrides (ADR-0045). Empty when none.
                        "role_attached": attached,
                        "role_detached": detached,
                    }
                },
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError, TypeError):
            return False
        return payload.get("result") is True


__all__ = ["AuthorizationPolicy", "OpaAuthorizationPolicy", "PythonAuthorizationPolicy"]
