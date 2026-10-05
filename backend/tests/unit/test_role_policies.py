"""Role permission overrides (ADR-0045)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from clarity.app.container import Clarity
from clarity.interfaces.http.main import create_app
from clarity.modules.iam.public import RolePolicyRefused
from clarity.platform.security.principal import (
    Assurance,
    Permission,
    Principal,
    Role,
    permissions_for,
    set_role_override_provider,
)


@pytest.fixture
def clarity() -> Clarity:
    core = Clarity()
    yield core
    set_role_override_provider(None)


@pytest.fixture
def client(clarity: Clarity) -> TestClient:
    return TestClient(create_app(clarity))


def _admin_headers(clarity: Clarity) -> dict[str, str]:
    issued = clarity.tokens.for_staff(
        "admin-1",
        roles={Role.PLATFORM_ADMIN},
        assurance=Assurance.MFA_RECENT,
    )
    return {"Authorization": f"Bearer {issued.value}"}


def test_attach_gives_a_role_a_new_permission(clarity: Clarity) -> None:
    clarity.role_policies.attach(
        role=Role.AGENT,
        permission=Permission.FORESIGHT_READ,
        actor_ref="admin-1",
        reason="desk copilot may open foresight",
        idempotency_key="iam-attach-foresight-1",
    )
    allowed = permissions_for({Role.AGENT})
    assert Permission.FORESIGHT_READ in allowed


def test_detach_removes_a_baseline_permission(clarity: Clarity) -> None:
    clarity.role_policies.detach(
        role=Role.AGENT,
        permission=Permission.DESK_QUEUE_READ,
        actor_ref="admin-1",
        reason="agents no longer open the queue",
        idempotency_key="iam-detach-desk-1",
    )
    assert Permission.DESK_QUEUE_READ not in permissions_for({Role.AGENT})


def test_money_cannot_be_attached_to_an_admin_role(clarity: Clarity) -> None:
    with pytest.raises(RolePolicyRefused) as refused:
        clarity.role_policies.attach(
            role=Role.PLATFORM_ADMIN,
            permission=Permission.ACTION_APPROVE,
            actor_ref="admin-1",
            reason="should fail",
            idempotency_key="iam-attach-money-admin",
        )
    assert refused.value.code == "ADMIN_MONEY_DENIED"
    assert Permission.ACTION_APPROVE not in permissions_for({Role.PLATFORM_ADMIN})


def test_audit_assign_stays_locked(clarity: Clarity) -> None:
    with pytest.raises(RolePolicyRefused) as refused:
        clarity.role_policies.attach(
            role=Role.SUPERVISOR,
            permission=Permission.AUDIT_ASSIGN,
            actor_ref="admin-1",
            reason="should fail",
            idempotency_key="iam-attach-assign",
        )
    assert refused.value.code == "PERMISSION_LOCKED"


def test_idempotent_attach_replays(clarity: Clarity) -> None:
    first = clarity.role_policies.attach(
        role=Role.CX_ENGINEER,
        permission=Permission.MERCHANT_SUSPEND,
        actor_ref="admin-1",
        reason="cx may suspend for a pilot",
        idempotency_key="iam-idem-merchant-1",
    )
    second = clarity.role_policies.attach(
        role=Role.CX_ENGINEER,
        permission=Permission.MERCHANT_SUSPEND,
        actor_ref="admin-1",
        reason="cx may suspend for a pilot",
        idempotency_key="iam-idem-merchant-1",
    )
    assert first["replayed"] is False
    assert second["replayed"] is True
    assert second["effective"] == first["effective"]
    assert Permission.MERCHANT_SUSPEND in permissions_for({Role.CX_ENGINEER})


def test_http_catalogue_and_attach(client: TestClient, clarity: Clarity) -> None:
    headers = _admin_headers(clarity)
    listed = client.get("/v1/admin/iam/roles", headers=headers)
    assert listed.status_code == 200
    body = listed.json()
    assert "roles" in body
    assert "iam:role:manage" in body["permissions"]

    attached = client.post(
        "/v1/admin/iam/roles/attach",
        headers={**headers, "Idempotency-Key": "http-iam-attach-1"},
        json={
            "role": "agent",
            "permission": "foresight:read",
            "reason": "copilot foresight",
        },
    )
    assert attached.status_code == 200
    assert "foresight:read" in attached.json()["effective"]

    principal = Principal(
        ref="agent-1",
        roles=frozenset({Role.AGENT}),
        assurance=Assurance.MFA,
    )
    assert principal.has(Permission.FORESIGHT_READ)


def test_http_refuses_without_permission(client: TestClient, clarity: Clarity) -> None:
    issued = clarity.tokens.for_staff(
        "agent-1",
        roles={Role.AGENT},
        assurance=Assurance.MFA_RECENT,
    )
    response = client.get(
        "/v1/admin/iam/roles",
        headers={"Authorization": f"Bearer {issued.value}"},
    )
    assert response.status_code == 403
