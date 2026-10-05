"""Who is calling, and what they are allowed to do.

Roles are coarse and few; permissions are fine-grained. The matrix below is
the one from the alternative design's 17 §5.4, and two rules in it matter more
than the rest:

- **Admins cannot approve money.** Running the platform and deciding refunds
  are different jobs, and the person who can grant themselves a role must not
  also be able to move money.
- **A maker is never the checker.** Enforced per item in the tool layer and
  the policy governance, not just by role.

Nothing is allowed unless it is listed here (plan §19 I9, deny by default).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum


class Role(StrEnum):
    """Coarse job titles. A person may hold several."""

    CUSTOMER = "customer"
    AGENT = "agent"
    SUPERVISOR = "supervisor"
    FINANCE = "finance"
    VAS_OPS = "vas_ops"
    CX_ENGINEER = "cx_engineer"
    COMPLIANCE = "compliance"
    AUDITOR = "auditor"
    PLATFORM_ADMIN = "platform_admin"
    SECURITY_ADMIN = "security_admin"
    PRODUCT = "product"
    """Owns what the product does: rehearses a change before it ships (C4).

    Added with the foresight API, but the name was already in use:
    ``config/policy/proactive.yaml`` and ``config/policy/foresight.yaml`` both
    write ``owner_role: product``, and until now no ``Role`` member matched it.
    A policy key owned by a role that does not exist is a key nobody can be held
    to.
    """

    @property
    def is_staff(self) -> bool:
        return self is not Role.CUSTOMER

    @property
    def is_admin(self) -> bool:
        return self in {Role.PLATFORM_ADMIN, Role.SECURITY_ADMIN}


class Permission(StrEnum):
    """What a caller may do. Every route and MCP tool declares one."""

    CASE_READ = "case:read"
    """May read cases. *Which* cases is decided by subject binding, not here."""
    CASE_READ_ANY = "case:read:any"
    """Widens subject binding to every subscriber. Staff only."""
    CASE_EVALUATE = "case:evaluate"
    ACTION_PROPOSE = "action:propose"
    ACTION_CONFIRM_OWN = "action:confirm:own"
    """A customer confirming their own one-tap fix."""
    ACTION_APPROVE = "action:approve"
    """Staff approving within the one-tap cap."""
    ACTION_APPROVE_HIGH_VALUE = "action:approve:high_value"
    """Above the cap. Requires recent MFA."""
    RECEIPT_READ = "receipt:read"
    RECEIPT_READ_ANY = "receipt:read:any"
    DESK_QUEUE_READ = "desk:queue:read"
    RECONCILIATION_READ = "reconciliation:read"
    AUTOPSY_REVIEW = "autopsy:review"
    """Confirm or reject a complaint cluster.

    Its own permission rather than `rule:draft`, because the two are different
    judgements. Reviewing says "these complaints are the same problem", which
    is a CX call on evidence. Drafting a rule says "this is what the system
    should do about it", which is a change to how money moves and is governed
    as one. A reviewer who could do both by holding one permission is a
    reviewer whose confirmation is already halfway to a published rule.
    """
    RULE_DRAFT = "rule:draft"
    RULE_PUBLISH = "rule:publish"
    CONFIG_DRAFT = "config:draft"
    CONFIG_APPROVE = "config:approve"
    MERCHANT_SUSPEND = "merchant:suspend"

    OFFER_VERIFY = "offer:verify"
    """A customer checking a message against their own offers (OFFER01).

    Separate from `self:read` because it is a different question with a
    different blast radius: `self:read` shows the account, this compares text
    against the campaign record. A rate limit or a kill switch wants to reach
    one without the other.
    """
    OFFER_MANAGE = "offer:manage"
    """Record what HUTCH sent to a number.

    Security admin's, and nobody else's. Whoever holds this decides what the
    fraud check will vouch for: adding an offer makes a message read as
    genuine, so it is the same shape of authority as flipping a kill switch and
    is deliberately not given to an agent, a supervisor or CX.
    """
    REGULATOR_PACK_EXPORT = "regulator_pack:export"
    AUDIT_READ = "audit:read"
    AUDIT_EXPORT = "audit:export"
    """Export a verifiable bundle of the trail (audit assurance plan, Phase 7)."""
    AUDIT_ASSIGN = "audit:assign"
    """Grant, approve, revoke and recertify audit duties for other people."""
    ALERT_DISPOSE = "alert:dispose"
    """Close an assurance alert with a disposition (Phase 4)."""
    AUDIT_RESTORE = "audit:restore"
    """Open a backup of the trail and restore it (Phase 6).

    Its own authority, separate from reading or exporting, because it is the only
    one in the system that can put a different past in place of the real one. Not
    grantable: it comes from a role, so taking it is a change somebody approved
    rather than a duty that can be handed out for an afternoon."""
    KILL_SWITCH = "flags:kill_switch"
    ADMIN_MANAGE = "admin:manage"
    IAM_ROLE_MANAGE = "iam:role:manage"
    """Attach or detach closed permissions on closed roles (ADR-0045).

    Platform admin only in the baseline. Step-up required. Does not invent new
    permission names and cannot put money authority on an admin role.
    """
    SELF_READ = "self:read"
    """Read your own account view, cases and receipts (customer self-service)."""
    SELF_SETTINGS = "self:settings"
    """Change your own preferences, safeguards and family links."""
    SELF_TRANSACT = "self:transact"
    """Simulated HUTCH self-care that moves money or changes a service on your own
    account: reload, buy a pack, cancel a subscription. Not a Clarity remedy."""
    FORESIGHT_READ = "foresight:read"
    """Read scenarios, runs, reports, backtests and spikes."""
    FORESIGHT_SCENARIO_DRAFT = "foresight:scenario:draft"
    """Draft and revise a scenario. Drafting predicts nothing on its own."""
    FORESIGHT_RUN = "foresight:run"
    """Ask for a rehearsal, and ask for a backtest to be recomputed."""
    FORESIGHT_OUTCOME_RECORD = "foresight:outcome:record"
    """Record what a launch actually produced.

    Deliberately **not** held by :attr:`Role.PRODUCT`. The person who wants the
    calibration gate open must not be the person who records the evidence that
    opens it: recorded outcomes are the only thing that can move a backtest to
    ``CALIBRATED``, and they are append-only precisely because somebody would
    otherwise be tempted. This is the same separation as a maker and a checker
    on the money path, applied to evidence instead of to a refund.
    """


#: Permissions that move money or change a paid service. Admins never hold
#: these, however many roles they are given.
MONEY_PERMISSIONS: frozenset[Permission] = frozenset(
    {
        Permission.ACTION_APPROVE,
        Permission.ACTION_APPROVE_HIGH_VALUE,
        Permission.ACTION_CONFIRM_OWN,
    }
)

#: Recording what a launch did is evidence about the system's own accuracy, so
#: it sits beside the audit duties in spirit: the person who benefits from a
#: favourable record must not be the person writing it (C4, plan 02 section 3.4).
FORESIGHT_EVIDENCE: frozenset[Permission] = frozenset({Permission.FORESIGHT_OUTCOME_RECORD})

#: Duties that watch the trail. Holding any of them removes money permissions,
#: however it was obtained: a monitor must not be able to approve the refunds
#: they are watching (audit assurance plan 5.6, rule 1).
AUDIT_DUTIES: frozenset[Permission] = frozenset(
    {
        Permission.AUDIT_READ,
        Permission.AUDIT_EXPORT,
        Permission.AUDIT_ASSIGN,
        Permission.ALERT_DISPOSE,
        Permission.AUDIT_RESTORE,
    }
)

#: What a grant may carry. Money is never grantable, and neither is the
#: authority to grant or to restore: ``AUDIT_ASSIGN`` and ``AUDIT_RESTORE`` come
#: from a role only.
GRANTABLE_PERMISSIONS: frozenset[Permission] = frozenset(
    {Permission.AUDIT_READ, Permission.AUDIT_EXPORT, Permission.ALERT_DISPOSE}
)

#: Permissions the IAM role-policy surface cannot attach or detach (ADR-0045).
#: They stay on the checked-in baseline only, same spirit as grant rules.
ROLE_POLICY_LOCKED: frozenset[Permission] = frozenset(
    {
        Permission.AUDIT_ASSIGN,
        Permission.AUDIT_RESTORE,
        Permission.IAM_ROLE_MANAGE,
    }
)

#: Permissions that need recent MFA, not just a valid session.
STEP_UP_PERMISSIONS: frozenset[Permission] = frozenset(
    {
        Permission.ACTION_APPROVE_HIGH_VALUE,
        Permission.RULE_PUBLISH,
        Permission.CONFIG_APPROVE,
        Permission.MERCHANT_SUSPEND,
        Permission.ADMIN_MANAGE,
        Permission.IAM_ROLE_MANAGE,
        Permission.AUDIT_ASSIGN,
        Permission.AUDIT_RESTORE,
    }
)

#: Optional provider of per-role (attached, detached) overrides. The composition
#: root wires :class:`RolePolicies`; tests may leave this unset so the baseline
#: alone answers.
RoleOverrideSnapshot = dict[Role, tuple[frozenset[Permission], frozenset[Permission]]]
_role_override_provider: Callable[[], RoleOverrideSnapshot] | None = None


def set_role_override_provider(
    provider: Callable[[], RoleOverrideSnapshot] | None,
) -> None:
    """Install or clear the IAM override reader used by :func:`permissions_for`."""
    global _role_override_provider
    _role_override_provider = provider


def role_override_maps() -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Attached/detached maps for the OPA input document (string keys/values)."""
    if _role_override_provider is None:
        return {}, {}
    attached: dict[str, list[str]] = {}
    detached: dict[str, list[str]] = {}
    for role, (add, remove) in _role_override_provider().items():
        if add:
            attached[role.value] = sorted(p.value for p in add)
        if remove:
            detached[role.value] = sorted(p.value for p in remove)
    return attached, detached


def effective_role_permissions(role: Role) -> frozenset[Permission]:
    """Baseline for ``role``, with persisted attach/detach overrides applied."""
    baseline = ROLE_PERMISSIONS.get(role, frozenset())
    if _role_override_provider is None:
        return baseline
    attached, detached = _role_override_provider().get(role, (frozenset(), frozenset()))
    return frozenset((baseline | attached) - detached)


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.CUSTOMER: frozenset(
        {
            Permission.CASE_READ,
            Permission.CASE_EVALUATE,
            Permission.ACTION_PROPOSE,
            Permission.ACTION_CONFIRM_OWN,
            Permission.RECEIPT_READ,
            Permission.SELF_READ,
            Permission.SELF_SETTINGS,
            Permission.SELF_TRANSACT,
            Permission.OFFER_VERIFY,
        }
    ),
    Role.AGENT: frozenset(
        {
            Permission.CASE_READ,
            Permission.CASE_READ_ANY,
            Permission.CASE_EVALUATE,
            Permission.ACTION_PROPOSE,
            Permission.ACTION_APPROVE,
            Permission.RECEIPT_READ,
            Permission.RECEIPT_READ_ANY,
            Permission.DESK_QUEUE_READ,
        }
    ),
    Role.SUPERVISOR: frozenset(
        {
            Permission.AUTOPSY_REVIEW,
            Permission.CASE_READ,
            Permission.CASE_READ_ANY,
            Permission.CASE_EVALUATE,
            Permission.ACTION_PROPOSE,
            Permission.ACTION_APPROVE,
            Permission.ACTION_APPROVE_HIGH_VALUE,
            Permission.RECEIPT_READ,
            Permission.RECEIPT_READ_ANY,
            Permission.DESK_QUEUE_READ,
            Permission.KILL_SWITCH,
        }
    ),
    Role.FINANCE: frozenset(
        {
            Permission.CASE_READ,
            Permission.CASE_READ_ANY,
            Permission.ACTION_APPROVE,
            Permission.ACTION_APPROVE_HIGH_VALUE,
            Permission.RECEIPT_READ,
            Permission.RECEIPT_READ_ANY,
            Permission.DESK_QUEUE_READ,
            Permission.CONFIG_APPROVE,
            Permission.RECONCILIATION_READ,
        }
    ),
    Role.VAS_OPS: frozenset(
        {
            Permission.CASE_READ,
            Permission.CASE_READ_ANY,
            Permission.ACTION_PROPOSE,
            Permission.RECEIPT_READ,
            Permission.RECEIPT_READ_ANY,
            Permission.DESK_QUEUE_READ,
            Permission.MERCHANT_SUSPEND,
        }
    ),
    Role.CX_ENGINEER: frozenset(
        {
            Permission.CASE_READ,
            Permission.CASE_READ_ANY,
            Permission.CASE_EVALUATE,
            Permission.RECEIPT_READ,
            Permission.RECEIPT_READ_ANY,
            Permission.DESK_QUEUE_READ,
            Permission.AUTOPSY_REVIEW,
            Permission.RULE_DRAFT,
            Permission.CONFIG_DRAFT,
            # CX writes the migration cards and scripts a rehearsal asks for, and
            # is the one who observes what a launch actually produced.
            Permission.FORESIGHT_READ,
            Permission.FORESIGHT_OUTCOME_RECORD,
        }
    ),
    Role.PRODUCT: frozenset(
        {
            Permission.FORESIGHT_READ,
            Permission.FORESIGHT_SCENARIO_DRAFT,
            Permission.FORESIGHT_RUN,
            Permission.CONFIG_DRAFT,
            Permission.DESK_QUEUE_READ,
        }
    ),
    Role.COMPLIANCE: frozenset(
        {
            Permission.CASE_READ,
            Permission.CASE_READ_ANY,
            Permission.RECEIPT_READ,
            Permission.RECEIPT_READ_ANY,
            Permission.DESK_QUEUE_READ,
            Permission.RULE_PUBLISH,
            Permission.MERCHANT_SUSPEND,
            Permission.REGULATOR_PACK_EXPORT,
            Permission.AUDIT_READ,
            Permission.AUDIT_EXPORT,
            Permission.ALERT_DISPOSE,
        }
    ),
    Role.AUDITOR: frozenset(
        {
            Permission.CASE_READ,
            Permission.CASE_READ_ANY,
            Permission.RECEIPT_READ,
            Permission.RECEIPT_READ_ANY,
            Permission.AUDIT_READ,
        }
    ),
    Role.PLATFORM_ADMIN: frozenset(
        {
            Permission.ADMIN_MANAGE,
            Permission.IAM_ROLE_MANAGE,
            Permission.KILL_SWITCH,
            Permission.AUDIT_READ,
            # Restoring the trail is an operations job, and the only role that
            # holds it: it needs step-up, and holding it costs every money
            # permission (rule 1), so it is not a convenience anybody carries.
            Permission.AUDIT_RESTORE,
            Permission.AUDIT_EXPORT,
            # Read the foresight workspace (rehearsal results as labelled
            # scenarios). Draft/run stay with product; outcome record stays
            # with CX so an admin cannot write the evidence they operate on.
            Permission.FORESIGHT_READ,
        }
    ),
    Role.SECURITY_ADMIN: frozenset(
        {
            Permission.ADMIN_MANAGE,
            Permission.AUDIT_READ,
            Permission.AUDIT_ASSIGN,
            # Recording what HUTCH sent to a number (OFFER01). Security's
            # because it is the authority the fraud check rests on, and
            # because they already hold no money permission, so the person who
            # decides what reads as genuine cannot also move a balance.
            Permission.OFFER_MANAGE,
        }
    ),
}


def permissions_for(
    roles: set[Role], granted: frozenset[Permission] = frozenset()
) -> frozenset[Permission]:
    """What a set of roles and active grants allow, with separation of duties applied.

    An admin who is also given an operational role still cannot approve money:
    the exclusions are applied after the union, so they cannot be escaped by
    stacking roles, or by adding a grant. A grant can only carry a permission
    in ``GRANTABLE_PERMISSIONS``; anything else in ``granted`` is ignored.
    Role overrides (ADR-0045) are applied per role before the union.
    """
    allowed: set[Permission] = set()
    for role in roles:
        allowed |= effective_role_permissions(role)
    allowed |= granted & GRANTABLE_PERMISSIONS

    if any(role.is_admin for role in roles):
        allowed -= MONEY_PERMISSIONS
    if allowed & AUDIT_DUTIES:
        # Rule 1: whoever watches the trail cannot move the money in it.
        allowed -= MONEY_PERMISSIONS
    return frozenset(allowed)


class Assurance(StrEnum):
    """How strongly the caller proved who they are (``acr``)."""

    NONE = "none"
    CLAIMED = "claimed"
    """A number asserted by a channel, e.g. WhatsApp. Not yet proven."""
    NETWORK = "network"
    """MSISDN asserted by the HUTCH gateway, e.g. USSD."""
    OTP = "otp"
    APP = "app"
    MFA = "mfa"
    MFA_RECENT = "mfa-recent"
    """Re-authenticated within the step-up window."""

    @property
    def can_act(self) -> bool:
        """Enough to change something on an account."""
        return self in {Assurance.OTP, Assurance.APP, Assurance.MFA, Assurance.MFA_RECENT}

    @property
    def is_step_up(self) -> bool:
        return self is Assurance.MFA_RECENT


@dataclass(frozen=True)
class Principal:
    """The authenticated caller. Built from a token, never from a request body."""

    ref: str
    roles: frozenset[Role]
    assurance: Assurance = Assurance.NONE
    subscriber_ref: str | None = None
    """Set for customers. The only subject whose cases they may read."""
    channel: str | None = None
    delegations: frozenset[str] = field(default_factory=frozenset)
    """Other subscriber_refs this principal may act for (guardian)."""
    granted: frozenset[Permission] = field(default_factory=frozenset)
    """Audit duties held by an active grant rather than a role (Phase 3)."""

    @property
    def permissions(self) -> frozenset[Permission]:
        return permissions_for(set(self.roles), self.granted)

    @property
    def is_customer(self) -> bool:
        return Role.CUSTOMER in self.roles

    def has(self, permission: Permission) -> bool:
        return permission in self.permissions

    def may_read(self, subscriber_ref: str) -> bool:
        """Subject binding: a customer sees their own cases and no others."""
        if self.has(Permission.CASE_READ_ANY):
            return True
        return subscriber_ref == self.subscriber_ref or subscriber_ref in self.delegations


ANONYMOUS = Principal(ref="anonymous", roles=frozenset())
