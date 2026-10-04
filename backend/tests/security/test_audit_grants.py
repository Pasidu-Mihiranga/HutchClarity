"""Audit duties by grant, under separation of duties (audit assurance Phase 3).

Each rule from the plan (section 5.6) is tested as the refusal it produces,
and the lifecycle as the states a grant moves through. The HTTP tests drive the
whole thing the way an admin would: one security admin asks, a second approves,
the named supervisor can then read the trail, and can no longer approve money.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from clarity.app.container import Clarity
from clarity.integration.drivers.mock.world import build_demo_world
from clarity.interfaces.http.main import create_app
from clarity.modules.iam.public import (
    AuditGrants,
    GrantAwareAuthorizationPolicy,
    GrantRefused,
    GrantState,
    SubjectKind,
)
from clarity.platform.audit.ledger import AuditEventType, AuditLedger
from clarity.platform.persistence.memory import MemoryStore, MemoryUnitOfWork
from clarity.platform.security.principal import (
    MONEY_PERMISSIONS,
    Assurance,
    Permission,
    Principal,
    Role,
)

from ..acceptance.conftest import PRIYA


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 10, 4, 9, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, by: timedelta) -> None:
        self.now += by


def staff(ref: str, *roles: Role, step_up: bool = True) -> Principal:
    return Principal(
        ref=ref,
        roles=frozenset(roles),
        assurance=Assurance.MFA_RECENT if step_up else Assurance.MFA,
    )


ALICE = staff("sec:alice", Role.SECURITY_ADMIN)
BOB = staff("sec:bob", Role.SECURITY_ADMIN)
RUWAN = staff("sup:ruwan", Role.SUPERVISOR)


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def ledger(clock: Clock) -> AuditLedger:
    """On the same clock as the grants, as the container wires them."""
    return AuditLedger(clock=clock)


@pytest.fixture
def grants(clock: Clock, ledger: AuditLedger) -> AuditGrants:
    store = MemoryStore()
    return AuditGrants(
        lambda: MemoryUnitOfWork(store),
        audit=ledger,
        max_duration=lambda: timedelta(days=90),
        review_interval=lambda: timedelta(days=30),
        break_glass_duration=lambda: timedelta(hours=4),
        clock=clock,
    )


def granted_read(grants: AuditGrants, *, days: int = 60) -> str:
    grant = grants.request(
        ALICE,
        subject_kind=SubjectKind.USER,
        subject_ref="sup:ruwan",
        permission=Permission.AUDIT_READ,
        reason="monitor refunds for October",
        duration=timedelta(days=days),
    )
    grants.approve(BOB, grant.grant_id)
    return grant.grant_id


def code_of(error: pytest.ExceptionInfo[GrantRefused]) -> str:
    return error.value.code


# --------------------------------------------------------------------------- #
# The rules
# --------------------------------------------------------------------------- #


def test_rule_1_a_granted_monitor_cannot_approve_money(grants: AuditGrants):
    granted_read(grants)
    ruwan = grants.apply(RUWAN)

    assert ruwan.has(Permission.AUDIT_READ)
    assert not (ruwan.permissions & MONEY_PERMISSIONS)


def test_rule_1_holds_under_a_policy_that_only_sees_roles(grants: AuditGrants):
    """The OPA driver sees roles; the wrapper must still refuse money and allow the grant."""

    class RolesOnly:
        def allows(self, principal: Principal, permission: Permission) -> bool:
            return permission in {Permission.ACTION_APPROVE, Permission.CASE_READ}

    granted_read(grants)
    policy = GrantAwareAuthorizationPolicy(RolesOnly())
    ruwan = grants.apply(RUWAN)

    assert not policy.allows(ruwan, Permission.ACTION_APPROVE)
    assert policy.allows(ruwan, Permission.AUDIT_READ)
    assert policy.allows(ruwan, Permission.CASE_READ)


def test_rule_3_the_requester_cannot_approve(grants: AuditGrants):
    grant = grants.request(
        ALICE,
        subject_kind=SubjectKind.USER,
        subject_ref="sup:ruwan",
        permission=Permission.AUDIT_READ,
        reason="r",
        duration=timedelta(days=1),
    )

    with pytest.raises(GrantRefused) as refused:
        grants.approve(ALICE, grant.grant_id)

    assert code_of(refused) == "FOUR_EYES"


def test_rule_4_nobody_grants_themselves_by_name(grants: AuditGrants):
    with pytest.raises(GrantRefused) as refused:
        grants.request(
            ALICE,
            subject_kind=SubjectKind.USER,
            subject_ref="sec:alice",
            permission=Permission.AUDIT_EXPORT,
            reason="r",
            duration=timedelta(days=1),
        )
    assert code_of(refused) == "SELF_GRANT"


def test_rule_4_nobody_grants_a_role_they_hold(grants: AuditGrants):
    with pytest.raises(GrantRefused) as refused:
        grants.request(
            ALICE,
            subject_kind=SubjectKind.ROLE,
            subject_ref="security_admin",
            permission=Permission.AUDIT_EXPORT,
            reason="r",
            duration=timedelta(days=1),
        )
    assert code_of(refused) == "SELF_GRANT"


def test_rule_4_the_approver_cannot_be_the_subject(grants: AuditGrants):
    grant = grants.request(
        ALICE,
        subject_kind=SubjectKind.USER,
        subject_ref="sec:bob",
        permission=Permission.AUDIT_EXPORT,
        reason="r",
        duration=timedelta(days=1),
    )
    with pytest.raises(GrantRefused) as refused:
        grants.approve(BOB, grant.grant_id)
    assert code_of(refused) == "SELF_GRANT"


@pytest.mark.parametrize("permission", sorted(MONEY_PERMISSIONS | {Permission.AUDIT_ASSIGN}))
def test_money_and_the_authority_to_grant_are_never_grantable(
    grants: AuditGrants, permission: Permission
):
    with pytest.raises(GrantRefused) as refused:
        grants.request(
            ALICE,
            subject_kind=SubjectKind.USER,
            subject_ref="sup:ruwan",
            permission=permission,
            reason="r",
            duration=timedelta(days=1),
        )
    assert code_of(refused) == "NOT_GRANTABLE"


def test_only_a_holder_of_audit_assign_may_request(grants: AuditGrants):
    with pytest.raises(GrantRefused) as refused:
        grants.request(
            RUWAN,
            subject_kind=SubjectKind.USER,
            subject_ref="agent:nadeesha",
            permission=Permission.AUDIT_READ,
            reason="r",
            duration=timedelta(days=1),
        )
    assert code_of(refused) == "NOT_PERMITTED"


def test_a_grant_cannot_outlast_the_policy_maximum(grants: AuditGrants):
    with pytest.raises(GrantRefused) as refused:
        grants.request(
            ALICE,
            subject_kind=SubjectKind.USER,
            subject_ref="sup:ruwan",
            permission=Permission.AUDIT_READ,
            reason="r",
            duration=timedelta(days=365),
        )
    assert code_of(refused) == "DURATION_OUT_OF_RANGE"


# --------------------------------------------------------------------------- #
# The lifecycle
# --------------------------------------------------------------------------- #


def test_a_pending_grant_gives_nothing(grants: AuditGrants):
    grants.request(
        ALICE,
        subject_kind=SubjectKind.USER,
        subject_ref="sup:ruwan",
        permission=Permission.AUDIT_READ,
        reason="r",
        duration=timedelta(days=1),
    )

    assert not grants.apply(RUWAN).has(Permission.AUDIT_READ)


def test_a_grant_to_a_role_reaches_everyone_in_it(grants: AuditGrants):
    grant = grants.request(
        ALICE,
        subject_kind=SubjectKind.ROLE,
        subject_ref="auditor",
        permission=Permission.AUDIT_EXPORT,
        reason="quarterly review",
        duration=timedelta(days=7),
    )
    grants.approve(BOB, grant.grant_id)

    assert grants.apply(staff("aud:kamal", Role.AUDITOR)).has(Permission.AUDIT_EXPORT)
    assert not grants.apply(RUWAN).has(Permission.AUDIT_EXPORT)


def test_an_unreviewed_grant_lapses_and_recertification_keeps_it(grants: AuditGrants, clock: Clock):
    kept = granted_read(grants)
    clock.advance(timedelta(days=29))
    grants.recertify(BOB, kept)

    clock.advance(timedelta(days=2))
    assert grants.apply(RUWAN).has(Permission.AUDIT_READ), "recertified, still live"

    clock.advance(timedelta(days=29))
    assert not grants.apply(RUWAN).has(Permission.AUDIT_READ), "not reviewed again, lapsed"


def test_a_grant_expires(grants: AuditGrants, clock: Clock):
    granted_read(grants, days=10)
    clock.advance(timedelta(days=11))

    assert not grants.apply(RUWAN).has(Permission.AUDIT_READ)


def test_a_revoked_grant_stops_at_once(grants: AuditGrants):
    grant_id = granted_read(grants)

    grants.revoke(BOB, grant_id, reason="left the team")

    assert not grants.apply(RUWAN).has(Permission.AUDIT_READ)
    assert grants.get(grant_id).state is GrantState.REVOKED


def test_break_glass_is_immediate_short_and_recorded(
    grants: AuditGrants, ledger: AuditLedger, clock: Clock
):
    platform = staff("plat:nuwan", Role.PLATFORM_ADMIN)

    grant = grants.break_glass(
        platform, permission=Permission.ALERT_DISPOSE, reason="incident INC-42"
    )

    assert grants.apply(platform).has(Permission.ALERT_DISPOSE)
    assert grant.break_glass is True
    assert ledger.of_type(AuditEventType.BREAK_GLASS_USED)[-1].actor_ref == "plat:nuwan"
    clock.advance(timedelta(hours=5))
    assert not grants.apply(platform).has(Permission.ALERT_DISPOSE)


def test_break_glass_is_for_admins_only(grants: AuditGrants):
    with pytest.raises(GrantRefused) as refused:
        grants.break_glass(RUWAN, permission=Permission.AUDIT_READ, reason="r")
    assert code_of(refused) == "NOT_PERMITTED"


def test_every_step_of_a_grant_is_in_the_trail(grants: AuditGrants, ledger: AuditLedger):
    grant_id = granted_read(grants)
    grants.recertify(BOB, grant_id)
    grants.revoke(ALICE, grant_id, reason="done")

    steps = [r.event_type for r in ledger.records if r.object_ref == grant_id]
    assert steps == [
        AuditEventType.GRANT_REQUESTED,
        AuditEventType.GRANT_APPROVED,
        AuditEventType.GRANT_RECERTIFIED,
        AuditEventType.GRANT_REVOKED,
    ]
    assert ledger.verify().intact


# --------------------------------------------------------------------------- #
# Over HTTP
# --------------------------------------------------------------------------- #


@pytest.fixture
def clarity() -> Clarity:
    return Clarity(world=build_demo_world())


@pytest.fixture
def api(clarity: Clarity) -> TestClient:
    return TestClient(create_app(clarity))


def session(
    api: TestClient, user: str, roles: list[str], *, step_up: bool = True
) -> dict[str, str]:
    made = api.post(
        "/v1/auth/staff/session", json={"user_ref": user, "roles": roles, "step_up": step_up}
    )
    assert made.status_code == 200, made.text
    return {"Authorization": f"Bearer {made.json()['token']}"}


def test_assigning_a_monitor_end_to_end(api: TestClient, clarity: Clarity):
    alice = session(api, "sec:alice", ["security_admin"])
    bob = session(api, "sec:bob", ["security_admin"])
    ruwan = session(api, "sup:ruwan", ["supervisor"])

    assert api.get("/v1/audit", headers=ruwan).status_code == 403, "no duty yet"

    asked = api.post(
        "/v1/audit/grants",
        json={
            "subject_kind": "user",
            "subject_ref": "sup:ruwan",
            "permission": "audit:read",
            "reason": "monitor refunds for October",
            "duration": "P30D",
        },
        headers=alice,
    )
    assert asked.status_code == 201, asked.text
    grant_id = asked.json()["grant_id"]

    own = api.post(f"/v1/audit/grants/{grant_id}/approve", headers=alice)
    assert own.status_code == 403 and "FOUR_EYES" in own.json()["detail"]

    approved = api.post(f"/v1/audit/grants/{grant_id}/approve", headers=bob)
    assert approved.status_code == 200, approved.text

    read = api.get("/v1/audit", params={"limit": 5}, headers=ruwan)
    assert read.status_code == 200, read.text
    body = read.json()
    assert body["verification"]["intact"] is True
    assert all("payload" not in record for record in body["records"])
    assert body["next_after_seq"] is not None

    me = api.get("/v1/auth/me", headers=ruwan).json()
    assert "audit:read" in me["permissions"]
    assert "action:approve" not in me["permissions"], "rule 1 over HTTP"

    reads = clarity.audit.of_type(AuditEventType.AUDIT_READ)
    assert reads[-1].actor_ref == "sup:ruwan"
    assert reads[-1].detail["returned"] == 5
    denied = [
        r
        for r in clarity.audit.of_type(AuditEventType.ACCESS_DENIED)
        if "FOUR_EYES" in r.detail["reason"]
    ]
    assert denied and denied[-1].actor_ref == "sec:alice"


def test_a_monitor_is_refused_an_approval_they_could_make_before(api: TestClient, clarity: Clarity):
    agent = session(api, "agent:nadeesha", ["agent"])
    case_id = api.post("/v1/cases", json={"msisdn": PRIYA}, headers=agent).json()["case_id"]
    api.post(f"/v1/cases/{case_id}/evaluate", headers=agent)
    plan_id = api.post(
        f"/v1/cases/{case_id}/proposals", json={"created_by": "agent:nadeesha"}, headers=agent
    ).json()["plan_id"]

    alice = session(api, "sec:alice", ["security_admin"])
    bob = session(api, "sec:bob", ["security_admin"])
    grant_id = api.post(
        "/v1/audit/grants",
        json={
            "subject_kind": "user",
            "subject_ref": "sup:ruwan",
            "permission": "audit:read",
            "reason": "watch the desk",
            "duration": "P7D",
        },
        headers=alice,
    ).json()["grant_id"]
    api.post(f"/v1/audit/grants/{grant_id}/approve", headers=bob)

    ruwan = session(api, "sup:ruwan", ["supervisor"])
    refused = api.post(
        f"/v1/cases/{case_id}/approve",
        json={"plan_id": plan_id, "role": "supervisor"},
        headers=ruwan,
    )

    # The same session approved this kind of case before it held the duty
    # (test_audit_coverage); the refusal is rule 1, not a missing step-up.
    assert refused.status_code == 403, refused.text
    assert "action:approve" in refused.json()["detail"]


def test_reading_the_trail_without_the_duty_is_refused_and_recorded(
    api: TestClient, clarity: Clarity
):
    agent = session(api, "agent:nadeesha", ["agent"])

    assert api.get("/v1/audit", headers=agent).status_code == 403
    denied = clarity.audit.of_type(AuditEventType.ACCESS_DENIED)[-1]
    assert denied.object_ref == "GET /v1/audit"
    assert denied.actor_ref == "agent:nadeesha"


def test_granting_needs_a_stepped_up_session(api: TestClient):
    alice = session(api, "sec:alice", ["security_admin"], step_up=False)

    refused = api.post(
        "/v1/audit/grants",
        json={
            "subject_kind": "user",
            "subject_ref": "sup:ruwan",
            "permission": "audit:read",
            "reason": "r",
            "duration": "P1D",
        },
        headers=alice,
    )

    assert refused.status_code == 403
    assert "step-up" in refused.json()["detail"]


# --------------------------------------------------------------------------- #
# Endings: expiry and lapse recorded at the moment they happen
# --------------------------------------------------------------------------- #


def endings(ledger: AuditLedger) -> list[object]:
    return ledger.of_type(AuditEventType.GRANT_EXPIRED) + ledger.of_type(
        AuditEventType.GRANT_LAPSED
    )


def test_an_expiry_is_recorded_with_the_moment_it_happened(
    grants: AuditGrants, ledger: AuditLedger, clock: Clock
):
    grant_id = granted_read(grants, days=10)
    expires_at = grants.get(grant_id).expires_at

    clock.advance(timedelta(days=12))  # noticed two days late
    grants.record_endings()

    record = ledger.of_type(AuditEventType.GRANT_EXPIRED)[-1]
    assert record.object_ref == grant_id
    assert record.occurred_at == expires_at, "the trail states when it ended"
    assert record.recorded_at == clock.now, "and separately when it was noticed"
    assert record.detail["end_reason"] == "expired"
    assert ledger.verify().intact


def test_a_missed_recertification_is_recorded_as_a_lapse(
    grants: AuditGrants, ledger: AuditLedger, clock: Clock
):
    grant_id = granted_read(grants, days=60)
    review_by = grants.get(grant_id).review_by

    clock.advance(timedelta(days=31))
    grants.record_endings()

    record = ledger.of_type(AuditEventType.GRANT_LAPSED)[-1]
    assert record.occurred_at == review_by
    assert grants.get(grant_id).end_reason == "lapsed"


def test_an_ending_is_recorded_once(grants: AuditGrants, ledger: AuditLedger, clock: Clock):
    granted_read(grants, days=10)
    clock.advance(timedelta(days=11))

    grants.record_endings()
    grants.record_endings()

    assert len(endings(ledger)) == 1


def test_two_processes_on_one_store_record_an_ending_once(clock: Clock, ledger: AuditLedger):
    """The API and the MCP server both sweep in ``full``: one record, not two."""
    store = MemoryStore()

    def build() -> AuditGrants:
        return AuditGrants(
            lambda: MemoryUnitOfWork(store),
            audit=ledger,
            max_duration=lambda: timedelta(days=90),
            review_interval=lambda: timedelta(days=30),
            break_glass_duration=lambda: timedelta(hours=4),
            clock=clock,
        )

    api, mcp = build(), build()
    granted_read(api, days=10)
    clock.advance(timedelta(days=11))

    first = api.record_endings()
    second = mcp.record_endings()

    assert len(first) == 1 and second == []
    assert len(endings(ledger)) == 1


def test_a_revoked_or_still_live_grant_records_no_ending(
    grants: AuditGrants, ledger: AuditLedger, clock: Clock
):
    revoked = granted_read(grants, days=10)
    grants.revoke(BOB, revoked, reason="moved team")
    granted_read(grants, days=60)

    clock.advance(timedelta(days=11))
    grants.record_endings()

    assert endings(ledger) == []


def test_a_failed_record_releases_its_claim_for_the_next_sweep(
    grants: AuditGrants, ledger: AuditLedger, clock: Clock, monkeypatch: pytest.MonkeyPatch
):
    grant_id = granted_read(grants, days=10)
    clock.advance(timedelta(days=11))
    real = ledger.append

    def failing(*args: object, **kwargs: object) -> object:
        raise RuntimeError("trail unavailable")

    monkeypatch.setattr(ledger, "append", failing)
    with pytest.raises(RuntimeError):
        grants.record_endings()
    assert grants.get(grant_id).ended_at is None, "claim released"

    monkeypatch.setattr(ledger, "append", real)
    assert len(grants.record_endings()) == 1


def test_a_break_glass_ending_is_recorded(grants: AuditGrants, ledger: AuditLedger, clock: Clock):
    grants.break_glass(
        staff("plat:nuwan", Role.PLATFORM_ADMIN),
        permission=Permission.AUDIT_EXPORT,
        reason="INC-42",
    )
    clock.advance(timedelta(hours=5))

    grants.record_endings()

    record = ledger.of_type(AuditEventType.GRANT_EXPIRED)[-1]
    assert record.detail["break_glass"] is True


def _expired_grant(clarity: Clarity) -> str:
    """Put an already-expired active grant in the store: the demo clock is frozen."""
    from clarity.modules.iam.public import GRANTS, AuditGrant

    now = clarity.audit_grants._clock()
    grant = AuditGrant(
        grant_id="GRT-expired",
        subject_kind=SubjectKind.USER,
        subject_ref="sup:ruwan",
        permission=Permission.AUDIT_READ,
        reason="October",
        duration_seconds=3600,
        requested_by="sec:alice",
        requested_at=now - timedelta(hours=2),
        state=GrantState.ACTIVE,
        approved_by="sec:bob",
        approved_at=now - timedelta(hours=2),
        expires_at=now - timedelta(hours=1),
        review_by=now + timedelta(days=1),
    )
    with clarity.audit.open_unit() as unit:
        unit.repository(GRANTS).put(grant.grant_id, grant)
        unit.commit()
    return grant.grant_id


def test_any_signed_in_request_records_an_ending_first(api: TestClient, clarity: Clarity):
    grant_id = _expired_grant(clarity)
    ruwan = session(api, "sup:ruwan", ["supervisor"])

    assert api.get("/v1/audit", headers=ruwan).status_code == 403, "expired, so refused"

    recorded = clarity.audit.of_type(AuditEventType.GRANT_EXPIRED)
    assert [r.object_ref for r in recorded] == [grant_id]


def test_the_server_sweeps_endings_when_nobody_signs_in(
    clarity: Clarity, monkeypatch: pytest.MonkeyPatch
):
    """The background sweep, under a real lifespan, with nobody making requests."""
    import time

    grant_id = _expired_grant(clarity)
    monkeypatch.setattr(clarity, "grant_sweep_interval", lambda: timedelta(seconds=0))

    with TestClient(create_app(clarity)):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if clarity.audit.of_type(AuditEventType.GRANT_EXPIRED):
                break
            time.sleep(0.1)

    recorded = clarity.audit.of_type(AuditEventType.GRANT_EXPIRED)
    assert [r.object_ref for r in recorded] == [grant_id]


def test_the_sweep_interval_comes_from_policy(clarity: Clarity):
    assert clarity.grant_sweep_interval() == timedelta(minutes=1)
