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
    "foresight": "foresight",
    "deskops": "deskops",
    "insights": "insights",
    "platform": "platform",
}

#: Collections that may only ever be inserted into: no UPDATE, no DELETE.
#:
#: The audit trail is the reason this exists. A hash chain detects an edit after
#: the fact; this stops the edit being possible at all through the ordinary write
#: path, and the migration backs it with grants so the database refuses rather
#: than relying on the code remembering (ADR-0034, audit assurance plan W1).
#:
#: ``platform.audit_head`` and ``platform.audit_floor`` are deliberately **not**
#: here: they are pointers, they move by design, and an append-only pointer is a
#: contradiction. They hold no history, only the current position, and the chain
#: they point into is what makes a wrong pointer detectable.
APPEND_ONLY: frozenset[str] = frozenset(
    {
        "platform.audit",
        "platform.audit_checkpoints",
        "platform.audit_segments",
        # What a customer was told, and what they said (A4, ADR-0040). A
        # transcript somebody can edit after the fact is not a record of a
        # conversation, it is a draft of one, and the handoff and dispute it
        # exists for both depend on it being the former. Retention is enforced
        # by expiry on read; an expired line is deleted, which is a removal of
        # the whole row and not a rewrite of one.
        "conversation.transcripts",
        # What a rehearsal said, and what the change actually did (C2, F05).
        # A scenario version, an engine output and a recorded launch outcome are
        # all claims about the past that a later reader relies on. The launches
        # and outcomes matter most: they are the evidence the plan 02 section
        # 3.4 calibration gate opens on, so they are exactly the rows somebody
        # would have to rewrite to make an uncalibrated engine look calibrated.
        #
        # `foresight.runs` and `foresight.candidates` are deliberately absent.
        # A run has a lifecycle a caller polls (queued, running, succeeded or
        # failed) and a candidate has one transition (unconfirmed to confirmed),
        # so both rows move by design. An append-only job record is the same
        # contradiction as an append-only pointer. What a confirmation produces
        # is a `foresight.outcomes` row, and that one cannot be rewritten.
        "foresight.scenarios",
        "foresight.reports",
        "foresight.launches",
        "foresight.outcomes",
        "foresight.calibrations",
        "foresight.spikes",
        # One complaint, counted, keyed by its event id (C5). Append-only
        # because the only way to make a spike disappear would be to delete
        # some of the observations that raised it.
        "foresight.observations",
    }
)


def is_append_only(collection: str) -> bool:
    return collection in APPEND_ONLY


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
        "iam.pending_logins",
        "reconciliation.expected_actions",
        "reconciliation.mismatches",
    }
)

#: Five modules own data that is deliberately **not** customer-scoped, and the
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
#: - ``foresight.*`` holds rehearsals of changes and the aggregate evidence
#:   about them. Foresight reads segment statistics and never an individual
#:   record (deck S8), so there is no subscriber to bind a row to, and inventing
#:   one to satisfy the pattern would be the opposite of the invariant.


#: The role the application runs its requests as.
#:
#: It is deliberately **not** the database owner. A superuser bypasses row-level
#: security unconditionally, so an application that connects as one has no RLS
#: at all however carefully the policies are written. This role is a member of
#: every module role, so its reach is exactly the union of the per-module grants
#: and nothing more, and it is subject to the policies.
APP_ROLE = "clarity_app"

#: Holds DELETE on the append-only tables, for the two operations that
#: legitimately remove audit rows: restoring a backup (ADR-0038) and sealing a
#: segment (ADR-0039). The application role is deliberately **not** a member, so
#: ordinary request handling cannot reach it however the code is called.
CUSTODIAN_ROLE = "clarity_audit_custodian"


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
    "APPEND_ONLY",
    "APP_ROLE",
    "CUSTODIAN_ROLE",
    "CUSTOMER_SCOPED",
    "OWNERS",
    "UnknownCollection",
    "is_append_only",
    "is_customer_scoped",
    "owner_of",
    "role_of",
    "schema_of",
    "table_of",
]
