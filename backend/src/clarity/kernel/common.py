"""Shared primitives: Money, enums, MSISDN helpers."""

from __future__ import annotations

import hashlib
import hmac
import re
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, PlainSerializer

_TWO_PLACES = Decimal("0.01")


class ClarityModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        ser_json_timedelta="iso8601",
    )


def _to_money(value: Any) -> Decimal:
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
ZERO = Decimal("0.00")


def money(value: Any) -> Decimal:
    return _to_money(value)


def utc_now() -> datetime:
    return datetime.now(UTC)


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("naive datetime is not allowed; timestamps must carry a timezone")
    return value.astimezone(UTC)


_MSISDN_RE = re.compile(r"^(?:\+?94|0)?(7\d{8})$")


def normalise_msisdn(raw: str) -> str:
    compact = re.sub(r"[\s\-()]", "", raw)
    match = _MSISDN_RE.match(compact)
    if match is None:
        raise ValueError(f"not a valid Sri Lankan mobile number: {raw!r}")
    return f"+94{match.group(1)}"


def subscriber_ref(msisdn: str, *, key: bytes) -> str:
    digest = hmac.new(key, normalise_msisdn(msisdn).encode("utf-8"), hashlib.sha256)
    return f"sub_{digest.hexdigest()[:32]}"


def mask_msisdn(msisdn: str) -> str:
    national = "0" + normalise_msisdn(msisdn)[3:]
    return f"{national[:2]}X XXX {national[-4:]}"


class Language(StrEnum):
    SI = "si"
    TA = "ta"
    EN = "en"


class Channel(StrEnum):
    WEB = "web"
    APP = "app"
    WHATSAPP = "whatsapp"
    SMS = "sms"
    USSD = "ussd"
    DESK = "desk"
    SHOP = "shop"
    SYSTEM = "system"


class EventSource(StrEnum):
    PAYMENTS = "payments"
    CHARGING = "charging"
    CATALOGUE = "catalogue"
    VAS_CONSENT = "vas_consent"
    USAGE_FUP = "usage_fup"
    LOANS = "loans"
    CRM = "crm"
    IDENTITY = "identity"


class Completeness(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    MISSING = "missing"


class ActionSafetyLevel(StrEnum):
    L1_READ = "L1"
    L2_LOW_RISK = "L2"
    L3_FINANCIAL = "L3"
    L4_BULK_ADMIN = "L4"
