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
    RULE_DRAFT = "rule:draft"
    RULE_PUBLISH = "rule:publish"
    CONFIG_DRAFT = "config:draft"
    CONFIG_APPROVE = "config:approve"
    MERCHANT_SUSPEND = "merchant:suspend"
    REGULATOR_PACK_EXPORT = "regulator_pack:export"
    AUDIT_READ = "audit:read"
    KILL_SWITCH = "flags:kill_switch"
    ADMIN_MANAGE = "admin:manage"


#: Permissions that move money or change a paid service. Admins never hold
#: these, however many roles they are given.
MONEY_PERMISSIONS: frozenset[Permission] = frozenset(
    {
        Permission.ACTION_APPROVE,
        Permission.ACTION_APPROVE_HIGH_VALUE,
        Permission.ACTION_CONFIRM_OWN,
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
    }
)


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.CUSTOMER: frozenset(
        {
            Permission.CASE_READ,
            Permission.CASE_EVALUATE,
            Permission.ACTION_PROPOSE,
            Permission.ACTION_CONFIRM_OWN,
            Permission.RECEIPT_READ,
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
            Permission.RULE_DRAFT,
            Permission.CONFIG_DRAFT,
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
            Permission.KILL_SWITCH,
            Permission.AUDIT_READ,
        }
    ),
    Role.SECURITY_ADMIN: frozenset(
        {
            Permission.ADMIN_MANAGE,
            Permission.AUDIT_READ,
        }
    ),
}


def permissions_for(roles: set[Role]) -> frozenset[Permission]:
    """What a set of roles grants, with separation of duties applied.

    An admin who is also given an operational role still cannot approve money:
    the exclusion is applied after the union, so it cannot be escaped by
    stacking roles.
    """
    granted: set[Permission] = set()
    for role in roles:
        granted |= ROLE_PERMISSIONS.get(role, frozenset())

    if any(role.is_admin for role in roles):
        granted -= MONEY_PERMISSIONS
    return frozenset(granted)


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

    @property
    def permissions(self) -> frozenset[Permission]:
        return permissions_for(set(self.roles))

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
