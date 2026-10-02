"""OPA and Python authorization drivers grant the same role-permission pairs."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from clarity.modules.iam.public import OpaAuthorizationPolicy, PythonAuthorizationPolicy
from clarity.platform.security.principal import Assurance, Permission, Principal, Role

DATA = json.loads(
    (Path(__file__).parents[3] / "config" / "opa" / "data.json").read_text(encoding="utf-8")
)["clarity"]


def _opa(request: httpx.Request) -> httpx.Response:
    document = json.loads(request.content)["input"]
    roles = set(document["roles"])
    permission = document["permission"]
    granted = any(permission in DATA["role_permissions"].get(role, []) for role in roles)
    admin_money = bool(roles & set(DATA["admin_roles"])) and permission in DATA["money_permissions"]
    missing_step_up = (
        permission in DATA["step_up_permissions"]
        and document["assurance"] != Assurance.MFA_RECENT.value
    )
    return httpx.Response(200, json={"result": granted and not admin_money and not missing_step_up})


@pytest.mark.parametrize("role", list(Role))
@pytest.mark.parametrize("permission", list(Permission))
@pytest.mark.parametrize("assurance", [Assurance.MFA, Assurance.MFA_RECENT])
def test_python_and_opa_authorization_are_equivalent(
    role: Role,
    permission: Permission,
    assurance: Assurance,
) -> None:
    principal = Principal(ref="parity", roles=frozenset({role}), assurance=assurance)
    python = PythonAuthorizationPolicy()
    opa = OpaAuthorizationPolicy(
        "http://opa",
        client=httpx.Client(transport=httpx.MockTransport(_opa)),
    )

    assert opa.allows(principal, permission) is python.allows(principal, permission)


def test_opa_driver_denies_when_the_policy_service_is_unavailable() -> None:
    def unavailable(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    policy = OpaAuthorizationPolicy(
        "http://opa",
        client=httpx.Client(transport=httpx.MockTransport(unavailable)),
    )
    principal = Principal(
        ref="agent-1",
        roles=frozenset({Role.AGENT}),
        assurance=Assurance.MFA,
    )

    assert not policy.allows(principal, Permission.CASE_READ)
