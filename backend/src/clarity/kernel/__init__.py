"""Clarity kernel (L0): shared vocabulary every layer imports.

Money is Decimal. IDs are typed ULIDs. Clocks are injectable. Errors are typed.
Nothing here does I/O.
"""

from clarity.kernel.clock import Clock, SystemClock, frozen_clock
from clarity.kernel.common import (
    ActionSafetyLevel,
    Channel,
    ClarityModel,
    Completeness,
    EventSource,
    Language,
    Money,
    ZERO,
    ensure_utc,
    mask_msisdn,
    money,
    normalise_msisdn,
    subscriber_ref,
    utc_now,
)
from clarity.kernel.context import CorrelationContext
from clarity.kernel.errors import (
    ClarityError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from clarity.kernel.events import CRITICAL_EVENTS, Event, EventType
from clarity.kernel.ids import (
    ActionId,
    CaseId,
    DecisionId,
    ReceiptId,
    case_no,
    new_id,
    receipt_id,
)
from clarity.kernel.principal import (
    MONEY_PERMISSIONS,
    ROLE_PERMISSIONS,
    Assurance,
    Permission,
    Principal,
    Role,
)
from clarity.kernel.result import Err, Ok, Result

__all__ = [
    "CRITICAL_EVENTS",
    "MONEY_PERMISSIONS",
    "ROLE_PERMISSIONS",
    "ActionId",
    "ActionSafetyLevel",
    "Assurance",
    "CaseId",
    "Channel",
    "ClarityError",
    "ClarityModel",
    "Clock",
    "Completeness",
    "ConflictError",
    "CorrelationContext",
    "DecisionId",
    "Err",
    "Event",
    "EventSource",
    "EventType",
    "ForbiddenError",
    "Language",
    "Money",
    "NotFoundError",
    "Ok",
    "Permission",
    "Principal",
    "ReceiptId",
    "Result",
    "Role",
    "SystemClock",
    "ValidationError",
    "ZERO",
    "case_no",
    "ensure_utc",
    "frozen_clock",
    "mask_msisdn",
    "money",
    "new_id",
    "normalise_msisdn",
    "receipt_id",
    "subscriber_ref",
    "utc_now",
]
