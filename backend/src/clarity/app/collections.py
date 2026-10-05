"""Every collection the system stores, assembled by the composition root.

The platform layer provides the persistence seam but must not know which
modules exist (I4: L2 cannot import L4). So the list of collections is declared
here, where the whole system is already in view, and handed to the migration
and to the drivers.

A new collection is added by a module and listed here, which is the moment the
schema, the role grants and the row-level security policy follow it.
"""

from __future__ import annotations

from clarity.modules.actions.capability import ATTEMPTS as ACTION_ATTEMPTS
from clarity.modules.actions.capability import CONFIRMATIONS, PLANS
from clarity.modules.assurance.public import ALERTS, HEARTBEATS
from clarity.modules.autopsy.public import CLUSTERS, COMPLAINTS
from clarity.modules.case.public import CASE_SEQUENCE, CASES
from clarity.modules.conversation.public import CONVERSATION_STATES, CONVERSATION_TRANSCRIPTS
from clarity.modules.deskops.public import BATCHES
from clarity.modules.foresight.public import (
    FORESIGHT_CALIBRATIONS,
    FORESIGHT_CANDIDATES,
    FORESIGHT_LAUNCHES,
    FORESIGHT_OBSERVATIONS,
    FORESIGHT_OUTCOMES,
    FORESIGHT_REPORTS,
    FORESIGHT_RUNS,
    FORESIGHT_SCENARIOS,
    FORESIGHT_SPIKES,
)
from clarity.modules.governance.public import CHANGES
from clarity.modules.iam.public import (
    GRANTS,
    ROLE_POLICIES,
    ROLE_POLICY_IDEMPOTENCY,
    OTP_CHALLENGES,
    OTP_REQUESTS,
    PENDING_LOGINS,
    REFRESH_TOKENS,
    SESSIONS,
)
from clarity.modules.insights.public import PROJECTIONS
from clarity.modules.knowledge.public import CHUNKS, SOURCES
from clarity.modules.notifications.public import NOTIFICATIONS, PREFERENCES
from clarity.modules.offers.public import OFFERS
from clarity.modules.proactive.public import RISKS, SIGNALS
from clarity.modules.receipts.public import (
    BY_PLAN,
    RECEIPT_SEQUENCE,
    RECEIPTS,
    SUBSCRIBERS,
    SUPERSEDED,
)
from clarity.modules.reconciliation.public import EXPECTED_ACTIONS, MISMATCHES
from clarity.platform.audit.checkpoints import AUDIT_CHECKPOINTS
from clarity.platform.audit.ledger import AUDIT, AUDIT_FLOOR, AUDIT_HEAD
from clarity.platform.audit.lifecycle import HOLDS, PSEUDONYMS, SEGMENTS
from clarity.platform.messaging.consumers import ATTEMPTS as CONSUMER_ATTEMPTS
from clarity.platform.messaging.consumers import DEAD_LETTERS, PROCESSED
from clarity.platform.messaging.outbox import OUTBOX

#: Order matters only for legibility; each collection is an independent table.
ALL_COLLECTIONS: tuple[str, ...] = (
    # case
    CASES,
    CASE_SEQUENCE,
    # actions
    PLANS,
    ACTION_ATTEMPTS,
    CONFIRMATIONS,
    # receipts
    RECEIPTS,
    SUPERSEDED,
    SUBSCRIBERS,
    RECEIPT_SEQUENCE,
    BY_PLAN,
    # reconciliation
    EXPECTED_ACTIONS,
    MISMATCHES,
    # governance
    CHANGES,
    # iam
    PENDING_LOGINS,
    OTP_CHALLENGES,
    OTP_REQUESTS,
    SESSIONS,
    REFRESH_TOKENS,
    GRANTS,
    ROLE_POLICIES,
    ROLE_POLICY_IDEMPOTENCY,
    # notifications
    NOTIFICATIONS,
    PREFERENCES,
    # proactive
    SIGNALS,
    RISKS,
    # conversation
    CONVERSATION_STATES,
    CONVERSATION_TRANSCRIPTS,
    # knowledge
    SOURCES,
    CHUNKS,
    # autopsy
    COMPLAINTS,
    CLUSTERS,
    # foresight
    FORESIGHT_SCENARIOS,
    FORESIGHT_RUNS,
    FORESIGHT_REPORTS,
    FORESIGHT_LAUNCHES,
    FORESIGHT_OUTCOMES,
    FORESIGHT_CALIBRATIONS,
    FORESIGHT_SPIKES,
    FORESIGHT_CANDIDATES,
    FORESIGHT_OBSERVATIONS,
    # deskops
    BATCHES,
    # insights
    PROJECTIONS,
    # offers: what HUTCH sent to a number (OFFER01). Not customer scoped by
    # row-level security: a record is keyed by the subscriber pseudonym and
    # read only through `offer:manage` (staff) or the subject-bound check,
    # which is the same shape as the other staff-read collections.
    OFFERS,
    # assurance
    ALERTS,
    HEARTBEATS,
    # platform: the outbox and the consumer framework's bookkeeping
    OUTBOX,
    PROCESSED,
    CONSUMER_ATTEMPTS,
    DEAD_LETTERS,
    # platform: the audit trail and its head pointer (ADR-0034). Not customer
    # scoped: the trail is cross-cutting, and read through AUDIT_READ instead.
    AUDIT,
    AUDIT_HEAD,
    # The signed checkpoints that make the trail tamper-evident (ADR-0035). They
    # live beside the trail for the same reason: a checkpoint in a different
    # store from the records it vouches for can be lost separately from them.
    AUDIT_CHECKPOINTS,
    # The archival floor, the sealed segment index, the legal holds and the
    # pseudonym links erasure destroys (Phase 7, ADR-0039). All beside the trail:
    # a floor in a different store from the records it bounds can be lost
    # separately from them, which would read as a truncated trail.
    AUDIT_FLOOR,
    SEGMENTS,
    HOLDS,
    PSEUDONYMS,
)

__all__ = ["ALL_COLLECTIONS"]
