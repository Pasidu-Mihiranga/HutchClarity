"""Which schema and role each collection belongs to (B05, ADR-0013).

Data ownership is a boundary the database enforces, not a convention the code
remembers (I6). Every collection name maps to the module that owns it, that
module gets one PostgreSQL schema and one role, and the role is granted nothing
outside its own schema. A module that reaches into another module's tables gets
a permission error rather than a code review comment.
"""

from __future__ import annotations

#: Collection name prefix -> owning module. The prefix is the part before the
#: first dot, which is how every collection in B02 and B04 is already named.
OWNERS: dict[str, str] = {
    "assurance": "assurance",
    "case": "case",
    "actions": "actions",
    "receipts": "receipts",
    "governance": "governance",
    "reconciliation": "reconciliation",
    "iam": "iam",
    "notifications": "notifications",
    "proactive": "proactive",
    "conversation": "conversation",
    "knowledge": "knowledge",
    "autopsy": "autopsy",
    "deskops": "deskops",
    "insights": "insights",
    "platform": "platform",
}

#: Collections holding rows about one customer. Row-level security binds these
#: to the subscriber the request is for, so a query that forgets its filter
#: returns nothing rather than someone else's case (plan 11 section 19).
CUSTOMER_SCOPED: frozenset[str] = frozenset(
    {
        "case.records",
        "actions.plans",
        "actions.attempts",
        "actions.confirmations",
        "receipts.chain",
        "receipts.subscriber",
        "platform.outbox",
        # A notification and a risk signal are both about one customer.
        "notifications.records",
        "notifications.preferences",
        "proactive.risks",
        "proactive.signals",
        # A conversation belongs to one case, so to one customer.
        "conversation.states",
        "iam.otp_challenges",
        "iam.otp_requests",
        "iam.sessions",
        "iam.refresh_tokens",
        "reconciliation.expected_actions",
        "reconciliation.mismatches",
    }
)

#: Four modules own data that is deliberately **not** customer-scoped, and the
#: reason differs for each. Binding any of them to a subscriber would not be a
#: stricter setting, it would hide the row from the only query that needs it.
#:
#: - ``knowledge.*`` holds published policy and help documents. There is no
#:   customer in them at all.
#: - ``insights.projections`` holds folds over the whole event log. A row is an
#:   aggregate across every subscriber, so it belongs to none of them.
#: - ``deskops.batches`` holds a staff batch spanning many subscribers, which a
#:   per-subscriber policy would make unreadable to the desk that owns it.
#: - ``autopsy.complaints`` holds masked complaint text and carries no
#:   ``subscriber_ref`` to bind to: the autopsy is aggregate-facing by
#:   construction (AU01), and the masking is what protects it.


#: The role the application runs its requests as.
#:
#: It is deliberately **not** the database owner. A superuser bypasses row-level
#: security unconditionally, so an application that connects as one has no RLS
#: at all however carefully the policies are written. This role is a member of
#: every module role, so its reach is exactly the union of the per-module grants
#: and nothing more, and it is subject to the policies.
APP_ROLE = "clarity_app"


class UnknownCollection(KeyError):
    """A collection no module claims.

    Refused rather than defaulted: a table with no owner is a table with no
    access rules, which is how customer data ends up readable by everything.
    """


def owner_of(collection: str) -> str:
    """The module that owns this collection."""
    prefix = collection.split(".", 1)[0]
    owner = OWNERS.get(prefix)
    if owner is None:
        raise UnknownCollection(
            f"no module owns {collection!r}; add its prefix to OWNERS in "
            "clarity/platform/persistence/schemas.py and give it a migration"
        )
    return owner


def schema_of(collection: str) -> str:
    """The PostgreSQL schema this collection's table lives in."""
    return f"clarity_{owner_of(collection)}"


def role_of(module: str) -> str:
    """The database role that owns one module's schema."""
    return f"clarity_{module}_rw"


def table_of(collection: str) -> str:
    """The table name inside the schema, with the owner prefix removed."""
    remainder = collection.split(".", 1)[1] if "." in collection else collection
    return remainder.replace(".", "_")


def is_customer_scoped(collection: str) -> bool:
    return collection in CUSTOMER_SCOPED


__all__ = [
    "APP_ROLE",
    "CUSTOMER_SCOPED",
    "OWNERS",
    "UnknownCollection",
    "is_customer_scoped",
    "owner_of",
    "role_of",
    "schema_of",
    "table_of",
]
