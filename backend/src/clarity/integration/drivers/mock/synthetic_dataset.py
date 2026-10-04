"""Deterministic, fully synthetic telecom corpus for DATA01."""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum


class CauseFamily(StrEnum):
    DUPLICATE_RELOAD = "DUPLICATE_RELOAD"
    RELOAD_NOT_CREDITED = "RELOAD_NOT_CREDITED"
    DUPLICATE_VAS_CHARGE = "DUPLICATE_VAS_CHARGE"
    VAS_NO_CONSENT = "VAS_NO_CONSENT"
    VAS_RENEWAL_UNNOTIFIED = "VAS_RENEWAL_UNNOTIFIED"
    FUP_CAP_REACHED = "FUP_CAP_REACHED"
    PACK_EXPIRY_BURN = "PACK_EXPIRY_BURN"
    PACK_MISMATCH = "PACK_MISMATCH"
    OUTAGE_DURING_PACK = "OUTAGE_DURING_PACK"
    LOAN_RECOVERY = "LOAN_RECOVERY"
    PAYMENT_PENDING_SETTLEMENT = "PAYMENT_PENDING_SETTLEMENT"
    PACK_ACTIVATION_FAILED = "PACK_ACTIVATION_FAILED"
    FUP_NOT_DISCLOSED = "FUP_NOT_DISCLOSED"
    SOCIAL_PACK_SCOPE_MISMATCH = "SOCIAL_PACK_SCOPE_MISMATCH"
    BALANCE_BURN_PAYG = "BALANCE_BURN_PAYG"
    NETWORK_SERVICE_DEGRADATION = "NETWORK_SERVICE_DEGRADATION"
    SIM_ESIM_PROVISIONING_FAILURE = "SIM_ESIM_PROVISIONING_FAILURE"
    UNEXPECTED_SERVICE_DISCONNECTION = "UNEXPECTED_SERVICE_DISCONNECTION"
    UNKNOWN_OTHER = "UNKNOWN_OTHER"


@dataclass(frozen=True, slots=True)
class SyntheticEvent:
    event_ref: str
    synthetic_customer_id: str
    source: str
    occurred_at: datetime
    fact: str
    compliant: bool
    synthetic: bool = True


@dataclass(frozen=True, slots=True)
class SyntheticComplaint:
    complaint_id: str
    synthetic_customer_id: str
    case_id: str
    channel: str
    language: str
    text: str
    created_at: datetime
    ground_truth_issue_family: str
    ground_truth_cause_rule: str | None
    ground_truth_department: str
    severity: str
    repeat_contact_count: int
    underlying_event_refs: tuple[str, ...]
    regulatory_rule_refs: tuple[str, ...]
    synthetic: bool = True


@dataclass(frozen=True, slots=True)
class ForesightAggregate:
    segment: str
    synthetic_population_share: str
    historical_synthetic_complaint_band: str
    pack_usage_intensity: str
    price_sensitivity: str
    data_intensity: str
    relevant_theme_rates: tuple[tuple[str, str], ...]
    synthetic: bool = True


@dataclass(frozen=True, slots=True)
class SyntheticDataset:
    seed: int
    generated_from: datetime
    generated_to: datetime
    complaints: tuple[SyntheticComplaint, ...]
    events: tuple[SyntheticEvent, ...]
    foresight_aggregates: tuple[ForesightAggregate, ...]
    provenance: str = "SYNTHETIC"

    def canonical_json(self) -> str:
        return json.dumps(asdict(self), default=_json_default, ensure_ascii=False, sort_keys=True)

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()


_DETAILS: dict[CauseFamily, tuple[str, str, str, str]] = {
    CauseFamily.DUPLICATE_RELOAD: (
        "reload charged twice",
        "reload eka deparak",
        "රීලෝඩ් එක දෙවරක්",
        "ரீலோட் இருமுறை",
    ),
    CauseFamily.RELOAD_NOT_CREDITED: (
        "payment went but reload missing",
        "salli giya balance awe na",
        "මුදල් ගියා ශේෂය නැහැ",
        "பணம் போனது இருப்பு வரவில்லை",
    ),
    CauseFamily.DUPLICATE_VAS_CHARGE: (
        "same service charged twice",
        "service charge deparak",
        "සේවා ගාස්තුව දෙවරක්",
        "சேவை கட்டணம் இருமுறை",
    ),
    CauseFamily.VAS_NO_CONSENT: (
        "service charged without consent",
        "mama confirm kale na",
        "මම අනුමත කළේ නැහැ",
        "நான் ஒப்புதல் தரவில்லை",
    ),
    CauseFamily.VAS_RENEWAL_UNNOTIFIED: (
        "renewal happened without notice",
        "renew wenawa kiyala kiwwe na",
        "අලුත් කිරීම දැනුම් දුන්නේ නැහැ",
        "புதுப்பிப்பு அறிவிப்பு இல்லை",
    ),
    CauseFamily.FUP_CAP_REACHED: (
        "data slowed after fair use cap",
        "cap passe data slow",
        "සීමාවෙන් පසු දත්ත මන්දගාමීයි",
        "வரம்புக்கு பிறகு தரவு மெதுவாகிறது",
    ),
    CauseFamily.PACK_EXPIRY_BURN: (
        "balance used after pack expired",
        "pack iwara balance kapuna",
        "පැකේජය ඉවරවී ශේෂය කැපුණා",
        "பேக் முடிந்து இருப்பு கழிந்தது",
    ),
    CauseFamily.PACK_MISMATCH: (
        "activated pack differs from purchase",
        "gatte wena pack ekak",
        "ගත්තේ වෙනත් පැකේජයක්",
        "வாங்கியது வேறு பேக்",
    ),
    CauseFamily.OUTAGE_DURING_PACK: (
        "active pack unusable during outage",
        "pack thiyenawa signal na",
        "පැකේජය තිබුණත් ජාලය නැහැ",
        "பேக் இருந்தும் நெட்வொர்க் இல்லை",
    ),
    CauseFamily.LOAN_RECOVERY: (
        "unexpected loan recovery deduction",
        "loan eka kapala",
        "ණය අයකරගෙන",
        "கடன் மீட்பு கழிவு",
    ),
    CauseFamily.PAYMENT_PENDING_SETTLEMENT: (
        "payment remains pending",
        "payment pending thamai",
        "ගෙවීම තවමත් පොරොත්තුවේ",
        "பணம் இன்னும் நிலுவையில்",
    ),
    CauseFamily.PACK_ACTIVATION_FAILED: (
        "paid pack did not activate",
        "pack activate une na",
        "පැකේජය සක්‍රිය වුණේ නැහැ",
        "பேக் செயல்படவில்லை",
    ),
    CauseFamily.FUP_NOT_DISCLOSED: (
        "speed cap was not disclosed",
        "FUP kiyala pennuwe na",
        "FUP සීමාව පෙන්වූයේ නැහැ",
        "FUP வரம்பு தெரிவிக்கவில்லை",
    ),
    CauseFamily.SOCIAL_PACK_SCOPE_MISMATCH: (
        "social app used normal data",
        "social pack eken app eka cover na",
        "සමාජ පැකේජය යෙදුම ආවරණය කළේ නැහැ",
        "சமூக பேக் செயலியை உள்ளடக்கவில்லை",
    ),
    CauseFamily.BALANCE_BURN_PAYG: (
        "pay as you go drained balance",
        "data on wela balance iwara",
        "දත්ත නිසා ශේෂය ඉවරයි",
        "தரவு இருப்பை காலி செய்தது",
    ),
    CauseFamily.NETWORK_SERVICE_DEGRADATION: (
        "calls and data keep dropping",
        "signal eka kadin kada",
        "සංඥාව නැවත නැවත බිඳෙයි",
        "சிக்னல் அடிக்கடி துண்டிக்கிறது",
    ),
    CauseFamily.SIM_ESIM_PROVISIONING_FAILURE: (
        "eSIM QR provisioning failed",
        "eSIM activate wenne na",
        "eSIM සක්‍රිය වෙන්නේ නැහැ",
        "eSIM செயல்படவில்லை",
    ),
    CauseFamily.UNEXPECTED_SERVICE_DISCONNECTION: (
        "service disconnected unexpectedly",
        "service eka kapala",
        "සේවාව හදිසියේ විසන්ධි වුණා",
        "சேவை திடீரென துண்டிக்கப்பட்டது",
    ),
    CauseFamily.UNKNOWN_OTHER: (
        "I need help with something unusual",
        "mokak hari awulak",
        "අමුතු ගැටලුවක් තියෙනවා",
        "வேறு ஒரு சிக்கல் உள்ளது",
    ),
}
_SEGMENTS = (
    "students",
    "dual-sim",
    "family",
    "high-data-prepaid",
    "low-usage-prepaid",
    "small-business",
    "tourist",
    "basic-phone",
)
_CHANNELS = ("app", "whatsapp", "call-centre", "ussd", "web")
_LANGUAGES = ("en", "en", "si-en", "si", "ta", "ta-en")


def generate_synthetic_dataset(
    *, count: int = 1500, seed: int = 42, start: datetime | None = None, end: datetime | None = None
) -> SyntheticDataset:
    """Create the same semantic corpus for the same configuration."""
    if count < len(CauseFamily):
        raise ValueError(f"count must be at least {len(CauseFamily)}")
    end_at = end or datetime(2027, 9, 14, tzinfo=UTC)
    start_at = start or end_at - timedelta(days=90)
    if start_at >= end_at:
        raise ValueError("start must be before end")
    rng = random.Random(seed)
    complaints: list[SyntheticComplaint] = []
    events: list[SyntheticEvent] = []
    families = tuple(CauseFamily)
    span_seconds = int((end_at - start_at).total_seconds())
    for offset in range(count):
        family = families[offset % len(families)]
        language = _LANGUAGES[offset % len(_LANGUAGES)]
        customer_id = f"SYN-CUST-{(offset % max(25, count // 4)) + 1:05d}"
        created_at = start_at + timedelta(seconds=rng.randrange(span_seconds + 1))
        missing = offset % 17 == 0 or family is CauseFamily.UNKNOWN_OTHER
        refs: tuple[str, ...] = ()
        if not missing:
            event_ref = f"SYN-EVT-{offset + 1:06d}"
            refs = (event_ref,)
            events.append(
                SyntheticEvent(
                    event_ref,
                    customer_id,
                    _source_for(family),
                    created_at - timedelta(minutes=5),
                    family.value,
                    offset % 11 == 0,
                )
            )
        text = _DETAILS[family][_language_index(language)]
        if offset % 23 == 0 and complaints:
            text = complaints[-1].text
        complaints.append(
            SyntheticComplaint(
                f"SYN-CMP-{offset + 1:06d}",
                customer_id,
                f"SYN-CASE-{offset + 1:06d}",
                rng.choice(_CHANNELS),
                language,
                text,
                created_at,
                family.value,
                None if missing else family.value,
                _department_for(family),
                rng.choice(("low", "medium", "high")),
                offset % 4,
                refs,
                ("SYNTHETIC-REG-EVAL",) if offset % 13 == 0 else (),
            )
        )
    aggregates = tuple(
        ForesightAggregate(
            segment,
            str(100 // len(_SEGMENTS)),
            "MEDIUM",
            "HIGH" if "data" in segment else "MEDIUM",
            "HIGH" if segment in {"students", "tourist"} else "MEDIUM",
            "HIGH" if segment in {"students", "high-data-prepaid"} else "LOW",
            (("pack-change", "MEDIUM"), ("service-quality", "LOW")),
        )
        for segment in _SEGMENTS
    )
    return SyntheticDataset(seed, start_at, end_at, tuple(complaints), tuple(events), aggregates)


def _language_index(language: str) -> int:
    return {"en": 0, "si-en": 1, "si": 2, "ta": 3, "ta-en": 3}[language]


def _source_for(family: CauseFamily) -> str:
    if "VAS" in family.value:
        return "vas-consent"
    if "RELOAD" in family.value or "PAYMENT" in family.value:
        return "payments"
    if any(word in family.value for word in ("NETWORK", "OUTAGE", "DISCONNECTION")):
        return "network-service"
    if "SIM" in family.value:
        return "sim-provisioning"
    if "FUP" in family.value:
        return "usage-fup"
    return "charging-catalogue"


def _department_for(family: CauseFamily) -> str:
    if "NETWORK" in family.value or "OUTAGE" in family.value:
        return "network-operations"
    if "VAS" in family.value:
        return "digital-services"
    if "PAYMENT" in family.value or "RELOAD" in family.value:
        return "payments"
    return "customer-operations"


def _json_default(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"cannot encode {type(value).__name__}")
