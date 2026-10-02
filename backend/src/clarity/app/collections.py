"""Every collection the system stores, assembled by the composition root.

The platform layer provides the persistence seam but must not know which
modules exist (I4: L2 cannot import L4). So the list of collections is declared
here, where the whole system is already in view, and handed to the migration
and to the drivers.

A new collection is added by a module and listed here, which is the moment the
schema, the role grants and the row-level security policy follow it.
"""

from __future__ import annotations

from clarity.modules.actions.capability import PLANS
from clarity.modules.case.public import CASE_SEQUENCE, CASES
from clarity.modules.governance.public import CHANGES
from clarity.modules.receipts.public import (
    BY_PLAN,
    RECEIPT_SEQUENCE,
    RECEIPTS,
    SUBSCRIBERS,
    SUPERSEDED,
)
from clarity.platform.messaging.consumers import ATTEMPTS, DEAD_LETTERS, PROCESSED
from clarity.platform.messaging.outbox import OUTBOX

#: Order matters only for legibility; each collection is an independent table.
ALL_COLLECTIONS: tuple[str, ...] = (
    # case
    CASES,
    CASE_SEQUENCE,
    # actions
    PLANS,
    # receipts
    RECEIPTS,
    SUPERSEDED,
    SUBSCRIBERS,
    RECEIPT_SEQUENCE,
    BY_PLAN,
    # governance
    CHANGES,
    # platform: the outbox and the consumer framework's bookkeeping
    OUTBOX,
    PROCESSED,
    ATTEMPTS,
    DEAD_LETTERS,
)

__all__ = ["ALL_COLLECTIONS"]
