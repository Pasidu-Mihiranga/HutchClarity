"""Principal, roles and permissions (deny by default)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Role(StrEnum):
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
    CASE_READ = "case:read"
    CASE_READ_ANY = "case:read:any"
    CASE_EVALUATE = "case:evaluate"
    ACTION_PROPOSE = "action:propose"
    ACTION_CONFIRM_OWN = "action:confirm:own"
    ACTION_APPROVE = "action:approve"
    ACTION_APPROVE_HIGH_VALUE = "action:approve:high_value"
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
    NOTIFY_SEND = "notify:send"
    KNOWLEDGE_SEARCH = "knowledge:search"
    POLICY_REPLAY = "policy:replay"
    AUTOPSY_READ = "autopsy:read"
    FORESIGHT_RUN = "foresight:run"


MONEY_PERMISSIONS: frozenset[Permission] = frozenset(
    {
        Permission.ACTION_APPROVE,
        Permission.ACTION_APPROVE_HIGH_VALUE,
        Permission.ACTION_CONFIRM_OWN,
        Permission.ACTION_PROPOSE,
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
            Permission.KNOWLEDGE_SEARCH,
        }
    ),
    Role.AGENT: frozenset(
        {
            Permission.CASE_READ_ANY,
            Permission.CASE_EVALUATE,
            Permission.ACTION_PROPOSE,
            Permission.ACTION_APPROVE,
            Permission.RECEIPT_READ_ANY,
            Permission.DESK_QUEUE_READ,
            Permission.KNOWLEDGE_SEARCH,
            Permission.NOTIFY_SEND,
        }
    ),
    Role.SUPERVISOR: frozenset(
        {
            Permission.CASE_READ_ANY,
            Permission.CASE_EVALUATE,
            Permission.ACTION_PROPOSE,
            Permission.ACTION_APPROVE,
            Permission.ACTION_APPROVE_HIGH_VALUE,
            Permission.RECEIPT_READ_ANY,
            Permission.DESK_QUEUE_READ,
            Permission.RULE_DRAFT,
            Permission.MERCHANT_SUSPEND,
            Permission.KNOWLEDGE_SEARCH,
            Permission.NOTIFY_SEND,
            Permission.POLICY_REPLAY,
            Permission.AUTOPSY_READ,
        }
    ),
    Role.FINANCE: frozenset(
        {
            Permission.CASE_READ_ANY,
            Permission.ACTION_APPROVE_HIGH_VALUE,
            Permission.RECEIPT_READ_ANY,
            Permission.DESK_QUEUE_READ,
            Permission.AUDIT_READ,
            Permission.REGULATOR_PACK_EXPORT,
            Permission.POLICY_REPLAY,
        }
    ),
    Role.VAS_OPS: frozenset(
        {
            Permission.CASE_READ_ANY,
            Permission.CASE_EVALUATE,
            Permission.ACTION_PROPOSE,
            Permission.MERCHANT_SUSPEND,
            Permission.DESK_QUEUE_READ,
        }
    ),
    Role.CX_ENGINEER: frozenset(
        {
            Permission.CASE_READ_ANY,
            Permission.RULE_DRAFT,
            Permission.RULE_PUBLISH,
            Permission.CONFIG_DRAFT,
            Permission.POLICY_REPLAY,
            Permission.AUTOPSY_READ,
            Permission.FORESIGHT_RUN,
            Permission.KNOWLEDGE_SEARCH,
        }
    ),
    Role.COMPLIANCE: frozenset(
        {
            Permission.CASE_READ_ANY,
            Permission.RECEIPT_READ_ANY,
            Permission.AUDIT_READ,
            Permission.REGULATOR_PACK_EXPORT,
            Permission.CONFIG_APPROVE,
            Permission.RULE_PUBLISH,
        }
    ),
    Role.AUDITOR: frozenset(
        {
            Permission.CASE_READ_ANY,
            Permission.RECEIPT_READ_ANY,
            Permission.AUDIT_READ,
            Permission.REGULATOR_PACK_EXPORT,
            Permission.POLICY_REPLAY,
        }
    ),
    Role.PLATFORM_ADMIN: frozenset(
        {
            Permission.ADMIN_MANAGE,
            Permission.KILL_SWITCH,
            Permission.CONFIG_DRAFT,
            Permission.AUDIT_READ,
        }
    ),
    Role.SECURITY_ADMIN: frozenset(
        {
            Permission.ADMIN_MANAGE,
            Permission.KILL_SWITCH,
            Permission.AUDIT_READ,
        }
    ),
}


class Assurance(StrEnum):
    ANONYMOUS = "anonymous"
    OTP = "otp"
    SSO = "sso"
    MFA = "mfa"
    SYSTEM = "system"


@dataclass(slots=True)
class Principal:
    subject: str
    roles: set[Role] = field(default_factory=set)
    permissions: set[Permission] = field(default_factory=set)
    subscriber_ref: str | None = None
    delegations: set[str] = field(default_factory=set)
    assurance: Assurance = Assurance.ANONYMOUS
    actor_ref: str | None = None

    def has(self, permission: Permission) -> bool:
        if permission in MONEY_PERMISSIONS and any(role.is_admin for role in self.roles):
            return False
        return permission in self.permissions

    @classmethod
    def from_roles(
        cls,
        *,
        subject: str,
        roles: set[Role],
        subscriber_ref: str | None = None,
        assurance: Assurance = Assurance.ANONYMOUS,
        actor_ref: str | None = None,
        delegations: set[str] | None = None,
    ) -> Principal:
        perms: set[Permission] = set()
        for role in roles:
            perms |= set(ROLE_PERMISSIONS.get(role, frozenset()))
        if any(role.is_admin for role in roles):
            perms -= MONEY_PERMISSIONS
        return cls(
            subject=subject,
            roles=roles,
            permissions=perms,
            subscriber_ref=subscriber_ref,
            assurance=assurance,
            actor_ref=actor_ref or subject,
            delegations=delegations or set(),
        )
