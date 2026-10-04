"""Identity and access events in the audit trail (audit assurance plan W2).

Before W2 the trail recorded "sup:ruwan approved" but never the moment a
session *became* sup:ruwan with step-up, nor the failed codes and refused
requests that come before an attack. These helpers record them from the HTTP
interface, which is the only place that sees sign-in, refresh and denial.

**Nothing secret or personal goes in.** No MSISDN: a number is identified by
its ``subscriber_ref`` pseudonym, or by its masked form when it matches no
account. No code, no token: a session is identified by ``session_ref``, a
truncated hash of the access token, which links a sign-in to everything later
done or refused with that token and cannot be turned back into the token.
"""

from __future__ import annotations

import hashlib
from typing import Any

from fastapi import Request

from clarity.app.container import Clarity
from clarity.platform.audit.ledger import ActorKind, AuditEventType
from clarity.platform.security.principal import ANONYMOUS, Principal


def session_ref_for(token: str | None) -> str | None:
    """A stable, non-reversible handle for one access token."""
    if not token:
        return None
    return "ses:" + hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]


def bearer_token(request: Request) -> str | None:
    header = request.headers.get("authorization") or ""
    if not header.lower().startswith("bearer "):
        return None
    return header.split(" ", 1)[1].strip() or None


def actor_kind_of(principal: Principal) -> ActorKind:
    if principal is ANONYMOUS or not principal.roles:
        return ActorKind.SYSTEM
    return ActorKind.CUSTOMER if principal.is_customer else ActorKind.STAFF


def route_of(request: Request) -> str:
    """``METHOD /path/{template}``: the route, not the ids in this request."""
    route = request.scope.get("route")
    path = getattr(route, "path", None) or request.url.path
    return f"{request.method} {path}"


def record(
    clarity: Clarity,
    event_type: AuditEventType,
    *,
    actor_ref: str,
    actor_kind: ActorKind,
    object_ref: str,
    detail: dict[str, Any],
    session_ref: str | None = None,
    case_id: str | None = None,
) -> None:
    """Append one identity or access record. The detail doubles as the payload.

    Failing to record raises, so an unauditable sign-in fails (ADR-0034).
    """
    clarity.audit.append(
        event_type,
        actor_ref=actor_ref,
        actor_kind=actor_kind,
        session_ref=session_ref,
        object_ref=object_ref,
        payload=detail,
        detail=detail,
        case_id=case_id,
    )


#: Methods that can change state. Every route answering one of these is
#: recorded as ``request.performed`` unless it is listed below with a reason.
STATE_CHANGING = frozenset({"POST", "PUT", "PATCH", "DELETE"})

#: Routes deliberately not recorded as ``request.performed``, and why. The
#: coverage contract (``tests/security/test_audit_coverage.py``) fails on any
#: state-changing route that is neither recorded nor listed here, so adding a
#: route is a decision about its audit, as adding one is about its permission.
NOT_RECORDED_AS_REQUESTS: dict[str, str] = {
    "POST /v1/auth/otp/request": "recorded as otp.requested, with its outcome",
    "POST /v1/auth/otp/verify": "recorded as otp.verified or otp.failed",
    "POST /v1/auth/staff/session": "recorded as staff.session_started, with roles and step-up",
    "POST /v1/auth/refresh": "recorded as token.refreshed or token.rejected",
    "POST /v1/receipts/{receipt_id}/verify": "read only: public verification changes nothing",
    "POST /v1/conversation/suggestions": "read only: returns suggestion chips",
    "POST /v1/clarity/route": "read only: classifies a question",
}


def records_request(method: str, route: str) -> bool:
    """Whether a request on this route is recorded as ``request.performed``."""
    return method in STATE_CHANGING and f"{method} {route}" not in NOT_RECORDED_AS_REQUESTS


#: Path parameters that name one customer or one of their records. A route with
#: one of these is about a person; a route without one is a list or a work queue.
SUBJECT_PARAMS = frozenset({"case_id", "subscriber_ref", "account_ref", "receipt_id"})


def records_data_read(method: str, route: str, principal: Principal) -> bool:
    """Whether this read is recorded as ``data.read``.

    Only staff, and only a route that names one subject. Two deliberate limits.

    **Staff only**, because a customer reading their own case is the product
    working, and recording it would bury the reads that matter in the ones that
    do not. A customer reaching another customer's case is a 403, which the
    refusal handler already records as ``access.denied``.

    **One subject only**, because recording every list request would multiply
    the trail by the console's polling and answer no question: the queue is
    public to the desk. Opening one person's record is the act worth having on
    file, and it is what the snooping rule counts.
    """
    return (
        method == "GET"
        and not principal.is_customer
        and bool(principal.roles)
        and any(f"{{{param}}}" in route for param in SUBJECT_PARAMS)
    )


__all__ = [
    "NOT_RECORDED_AS_REQUESTS",
    "STATE_CHANGING",
    "SUBJECT_PARAMS",
    "actor_kind_of",
    "bearer_token",
    "record",
    "records_data_read",
    "records_request",
    "route_of",
    "session_ref_for",
]
