"""OPA and Python authorization drivers grant the same role-permission pairs.

Two lanes, because one of them proves much less than it looks.

**Against a real OPA** (``CLARITY_OPA_URL``, the ``full`` lane): the Rego in
``config/opa/authz.rego`` is evaluated by OPA itself. This is the lane that can
catch a mistake in the policy, and it is the one M-IAM's acceptance test means.

**Against a local stand-in** (the default, no OPA needed): the transport
reimplements the rules in Python from the same ``data.json``. It checks that the
data file and the Python driver agree, and it keeps the ``demo`` profile free of
infrastructure (ADR-0006). What it cannot do is notice that the Rego says
something different, because no Rego is involved. The stand-in is named for what
it is rather than called "opa", so the limit is visible at the call site.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
import pytest

from clarity.modules.iam.public import OpaAuthorizationPolicy, PythonAuthorizationPolicy
from clarity.platform.security.principal import Assurance, Permission, Principal, Role

DATA = json.loads(
    (Path(__file__).parents[3] / "config" / "opa" / "data.json").read_text(encoding="utf-8")
)["clarity"]


def _reimplemented_in_python(request: httpx.Request) -> httpx.Response:
    """The rules again, in Python, over the real ``data.json``.

    Deliberately not the Rego: see the module docstring for what this does and
    does not prove.
    """
    document = json.loads(request.content)["input"]
    roles = set(document["roles"])
    permission = document["permission"]
    granted = any(permission in DATA["role_permissions"].get(role, []) for role in roles)
    admin_money = bool(roles & set(DATA["admin_roles"])) and permission in DATA["money_permissions"]
    duties = set(DATA["audit_duty_permissions"])
    holds_duty = any(
        duties & set(DATA["role_permissions"].get(role, [])) for role in roles
    ) or bool(duties & set(document.get("granted", [])))
    duty_money = holds_duty and permission in DATA["money_permissions"]
    missing_step_up = (
        permission in DATA["step_up_permissions"]
        and document["assurance"] != Assurance.MFA_RECENT.value
    )
    return httpx.Response(
        200,
        json={"result": granted and not admin_money and not duty_money and not missing_step_up},
    )


def _opa_url() -> str | None:
    """The address of a running OPA, if this lane has one."""
    return os.environ.get("CLARITY_OPA_URL")


@pytest.fixture(params=["python-stand-in", "real-opa"])
def authorization(request: pytest.FixtureRequest) -> OpaAuthorizationPolicy:
    """The OPA driver, backed by the stand-in or by a real OPA server."""
    if request.param == "real-opa":
        url = _opa_url()
        if not url:
            pytest.skip("set CLARITY_OPA_URL to evaluate the real Rego policy")
        return OpaAuthorizationPolicy(url)
    return OpaAuthorizationPolicy(
        "http://opa",
        client=httpx.Client(transport=httpx.MockTransport(_reimplemented_in_python)),
    )


@pytest.mark.parametrize("role", list(Role))
@pytest.mark.parametrize("permission", list(Permission))
@pytest.mark.parametrize("assurance", [Assurance.MFA, Assurance.MFA_RECENT])
def test_python_and_opa_authorization_are_equivalent(
    role: Role,
    permission: Permission,
    assurance: Assurance,
    authorization: OpaAuthorizationPolicy,
) -> None:
    principal = Principal(ref="parity", roles=frozenset({role}), assurance=assurance)
    python = PythonAuthorizationPolicy()

    assert authorization.allows(principal, permission) is python.allows(principal, permission)


def test_the_real_rego_is_actually_reachable_when_this_lane_runs() -> None:
    """Guard against the whole point of the full lane being silently skipped.

    A parity suite that skips is indistinguishable from one that passes, and
    this is the suite standing between a mistake in the Rego and production.
    """
    url = _opa_url()
    if not url:
        pytest.skip("set CLARITY_OPA_URL to evaluate the real Rego policy")

    principal = Principal(
        ref="reachability",
        roles=frozenset({Role.AGENT}),
        assurance=Assurance.MFA,
    )
    assert OpaAuthorizationPolicy(url).allows(principal, Permission.CASE_READ), (
        "an agent must be allowed to read a case; if this fails, OPA answered "
        "but the policy or the data it loaded is not the one in config/opa"
    )


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


# --------------------------------------------------------------------------- #
# Audit duties held by grant (B7)
#
# The Rego has always read `input.granted`, and the driver never sent it, so
# the branch that stops a holder of a granted audit duty from moving money
# could not fire. Nothing was reachable through the gap, because
# `GrantAwareAuthorizationPolicy` enforces the same rule in Python before the
# request reaches OPA. What was wrong is subtler: the two drivers were only in
# parity because one of them was wrapped, so removing the wrapper would have
# left the Rego quietly not enforcing rule 1.
#
# Measured against the real Rego with the field omitted: a supervisor holding
# `audit:read` by grant was allowed `action:approve`. With it sent: denied.
# --------------------------------------------------------------------------- #


def _granted_principal(permission: Permission) -> Principal:
    """A supervisor who also holds an audit duty by grant."""
    return Principal(
        ref="parity-granted",
        roles=frozenset({Role.SUPERVISOR}),
        assurance=Assurance.MFA_RECENT,
        granted=frozenset({permission}),
    )


def test_a_granted_audit_duty_blocks_money_in_the_policy_itself(
    authorization: OpaAuthorizationPolicy,
) -> None:
    """Rule 1, decided by the policy rather than by the wrapper around it."""
    holder = _granted_principal(Permission.AUDIT_READ)

    assert authorization.allows(holder, Permission.ACTION_APPROVE) is False


def test_without_a_grant_the_same_supervisor_may_approve(
    authorization: OpaAuthorizationPolicy,
) -> None:
    """The denial above has to come from the grant, not from something else."""
    plain = Principal(
        ref="parity-granted",
        roles=frozenset({Role.SUPERVISOR}),
        assurance=Assurance.MFA_RECENT,
    )

    assert authorization.allows(plain, Permission.ACTION_APPROVE) is True


def test_the_driver_sends_the_grants_the_policy_reads() -> None:
    """The defect was one missing key, so the key itself is worth asserting."""
    seen: dict[str, object] = {}

    def capture(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content)["input"])
        return httpx.Response(200, json={"result": False})

    driver = OpaAuthorizationPolicy(
        "http://opa", client=httpx.Client(transport=httpx.MockTransport(capture))
    )
    driver.allows(_granted_principal(Permission.AUDIT_READ), Permission.ACTION_APPROVE)

    assert seen["granted"] == [Permission.AUDIT_READ.value]
