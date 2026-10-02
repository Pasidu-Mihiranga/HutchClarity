"""Authorization Policy port — Python driver (lite) / OPA (full)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from clarity.kernel.errors import ForbiddenError
from clarity.kernel.principal import Permission, Principal


class Policy(Protocol):
    def allow(self, principal: Principal, permission: Permission, *, resource: str | None = None) -> bool: ...

    def require(self, principal: Principal, permission: Permission, *, resource: str | None = None) -> None: ...


@dataclass
class PythonPolicy:
    """Deny-by-default in-process policy driver."""

    def allow(
        self,
        principal: Principal,
        permission: Permission,
        *,
        resource: str | None = None,
    ) -> bool:
        _ = resource
        return principal.has(permission)

    def require(
        self,
        principal: Principal,
        permission: Permission,
        *,
        resource: str | None = None,
    ) -> None:
        if not self.allow(principal, permission, resource=resource):
            raise ForbiddenError(f"denied: {permission.value}")


@dataclass
class OpaPolicy:
    """Full-profile OPA driver stub — calls OPA HTTP API when configured."""

    base_url: str
    fallback: PythonPolicy

    def allow(
        self,
        principal: Principal,
        permission: Permission,
        *,
        resource: str | None = None,
    ) -> bool:
        # Live OPA call is wired in Phase I; fallback keeps lite/full parity.
        try:
            import httpx

            resp = httpx.post(
                f"{self.base_url}/v1/data/clarity/authz/allow",
                json={
                    "input": {
                        "subject": principal.subject,
                        "roles": [r.value for r in principal.roles],
                        "permission": permission.value,
                        "resource": resource,
                    }
                },
                timeout=2.0,
            )
            if resp.status_code == 200:
                return bool(resp.json().get("result", False))
        except Exception:
            pass
        return self.fallback.allow(principal, permission, resource=resource)

    def require(
        self,
        principal: Principal,
        permission: Permission,
        *,
        resource: str | None = None,
    ) -> None:
        if not self.allow(principal, permission, resource=resource):
            raise ForbiddenError(f"denied: {permission.value}")
