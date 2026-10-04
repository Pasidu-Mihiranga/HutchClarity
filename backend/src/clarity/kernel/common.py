"""Shared primitives for every Clarity domain model.

Design rules (plan §16.1, §17.1):
- Money is always ``Decimal`` quantized to 2 places and serialized as a string.
  Floats are never used for money.
- Models forbid unknown fields, so a malformed payload fails loudly instead of
  silently losing evidence.
- Customers are identified by ``subscriber_ref`` (a keyed HMAC of the MSISDN).
  The raw MSISDN never enters a domain model; it lives only in the token vault.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, PlainSerializer

# --------------------------------------------------------------------------- #
# Base model
# --------------------------------------------------------------------------- #


class ClarityModel(BaseModel):
    """Base for all domain models: strict, immutable-friendly, no extra fields."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        ser_json_timedelta="iso8601",
    )


# --------------------------------------------------------------------------- #
# Money
# --------------------------------------------------------------------------- #

_TWO_PLACES = Decimal("0.01")


def _to_money(value: Any) -> Decimal:
    """Accept int/str/Decimal; reject float so binary rounding can never creep in."""
    if isinstance(value, float):
        raise ValueError("money must not be a float; use Decimal or a decimal string")
    if isinstance(value, Decimal):
        dec = value
    elif isinstance(value, int | str):
        dec = Decimal(str(value))
    else:
        raise TypeError(f"cannot interpret {type(value).__name__} as money")
    if not dec.is_finite():
        raise ValueError("money must be a finite amount")
    return dec.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)


Money = Annotated[
    Decimal,
    BeforeValidator(_to_money),
    PlainSerializer(lambda d: f"{d:.2f}", return_type=str, when_used="always"),
]
"""LKR amount. Validated from int/str/Decimal, serialized as e.g. ``"49.00"``."""

ZERO = Decimal("0.00")


def money(value: Any) -> Decimal:
    """Build a money ``Decimal`` outside of a model (same rules as :data:`Money`)."""
    return _to_money(value)


# --------------------------------------------------------------------------- #
# Time
# --------------------------------------------------------------------------- #


def utc_now() -> datetime:
    """Timezone-aware current time. All domain timestamps are UTC."""
    return datetime.now(UTC)


def ensure_utc(value: datetime) -> datetime:
    """Reject naive datetimes; normalise everything else to UTC."""
    if value.tzinfo is None:
        raise ValueError("naive datetime is not allowed; timestamps must carry a timezone")
    return value.astimezone(UTC)


# --------------------------------------------------------------------------- #
# Identifiers
# --------------------------------------------------------------------------- #

_MSISDN_RE = re.compile(r"^(?:\+?94|0)?(7\d{8})$")


def normalise_msisdn(raw: str) -> str:
    """Normalise a Sri Lankan mobile number to E.164 (``+947XXXXXXXX``).

    Accepts ``0781234567``, ``781234567``, ``+94781234567`` and spaced or
    hyphenated variants. Raises ``ValueError`` for anything else, so a bad
    identifier is caught at the edge rather than producing a wrong timeline.
    """
    compact = re.sub(r"[\s\-()]", "", raw)
    match = _MSISDN_RE.match(compact)
    if match is None:
        raise ValueError(f"not a valid Sri Lankan mobile number: {raw!r}")
    return f"+94{match.group(1)}"


def subscriber_ref(msisdn: str, *, key: bytes) -> str:
    """Keyed HMAC pseudonym for a subscriber (plan §16.1).

    The same number always maps to the same ref under one key, and the ref
    cannot be reversed without the key. Partitioning and Kafka keys use this.
    """
    digest = hmac.new(key, normalise_msisdn(msisdn).encode("utf-8"), hashlib.sha256)
    return f"sub_{digest.hexdigest()[:32]}"


def mask_msisdn(msisdn: str) -> str:
    """Mask for display and receipts: ``+94781234567`` -> ``07X XXX 4567``."""
    national = "0" + normalise_msisdn(msisdn)[3:]
    return f"{national[:2]}X XXX {national[-4:]}"


# --------------------------------------------------------------------------- #
# Enumerations shared across modules
# --------------------------------------------------------------------------- #


class Language(StrEnum):
    """Languages Clarity answers in (plan §4.2 NFR-L10N-01)."""

    SI = "si"
    TA = "ta"
    EN = "en"


class Channel(StrEnum):
    """Customer and staff touchpoints (deck S12)."""

    WEB = "web"
    APP = "app"
    WHATSAPP = "whatsapp"
    SMS = "sms"
    USSD = "ussd"
    DESK = "desk"
    SHOP = "shop"
    SYSTEM = "system"
    """Used when no human started the interaction, e.g. zero-contact detection."""


class EventSource(StrEnum):
    """The eight log sources joined into one case file (deck S7, plan §9.2)."""

    PAYMENTS = "payments"
    CHARGING = "charging"
    CATALOGUE = "catalogue"
    VAS_CONSENT = "vas_consent"
    USAGE_FUP = "usage_fup"
    LOANS = "loans"
    CRM = "crm"
    IDENTITY = "identity"


class Completeness(StrEnum):
    """Per-source evidence quality.

    ``MISSING`` or ``PARTIAL`` on a source a rule requires means the case is
    held or handed off: "missing log -> a human, never a guess" (deck S7).
    """

    COMPLETE = "complete"
    PARTIAL = "partial"
    MISSING = "missing"


class ActionSafetyLevel(StrEnum):
    """MCP/tool-layer safety levels (plan §10.4).

    The LLM may read at L1, propose at L2/L3, and is never permitted to execute
    L3 or L4. Execution always requires a confirmation token or staff approval.
    """

    L1_READ = "L1"
    L2_LOW_RISK = "L2"
    L3_FINANCIAL = "L3"
    L4_BULK_ADMIN = "L4"
