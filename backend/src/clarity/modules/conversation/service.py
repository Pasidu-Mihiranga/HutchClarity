"""Conversation intake, language ID, handoff, and template composition."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from clarity.modules.conversation.intent_routes import routing_payload
from clarity.modules.conversation.intents import Intent
from clarity.modules.conversation.suggestions import (
    build_suggestions,
    signals_from_snapshot,
)

_SINHALA = re.compile(r"[඀-෿]")
_TAMIL = re.compile(r"[஀-௿]")

# (pattern, intent, score) - en/si/ta. Highest score wins.
_INTAKE_KEYWORDS: list[tuple[str, str, float]] = [
    (
        r"\b(agent|human|speak to|talk to|complaint|fraud|police|lawyer)\b|නීති|පොලීස්|மனிதர்|முறையீடு",
        Intent.HANDOFF.value,
        0.95,
    ),
    (r"\b(esim|e-sim|convert to esim)\b", Intent.ESIM_HELP.value, 0.92),
    (r"\b(recommend|best pack|which pack|suitable)\b|හොඳම|சிறந்த", Intent.PACK_RECOMMEND.value, 0.9),
    (
        r"\b(prevent|safeguard|stop unexpected|spend cap)\b|වැළැක්|தடுக்க",
        Intent.PREVENT_CHARGES.value,
        0.88,
    ),
    (
        r"\b(stop (it|this)|disable (it|this|the service)|cancel (it|this)|turn (it|this) off)\b"
        r"|නවත්ව|நிறுத்து",
        Intent.VAS_SUBSCRIPTIONS.value,
        0.9,
    ),
    (r"\b(my case|ticket status|case status)\b|කේස්|வழக்கு", Intent.CASE_STATUS.value, 0.88),
    (r"\b(refund|got my money back)\b|ආපසු|பணத்தைத் திருப்பு", Intent.REFUND_STATUS.value, 0.88),
    (r"\b(network|no signal|coverage|outage)\b|සිග්නල්|சிக்னல்", Intent.NETWORK_STATUS.value, 0.86),
    (
        r"\b(subscription|subscriptions|vas list|active vas|gamezone|gamehub)\b|දායක|சந்தா",
        Intent.VAS_SUBSCRIPTIONS.value,
        0.9,
    ),
    (r"\b(twice|duplicate|double.?charge|දෙවර|இரண்டு)\b", Intent.DOUBLE_CHARGE.value, 0.92),
    (r"\b(fup|fair.?use|speed reduced|throttle)\b|වේගය|வேக", Intent.FUP_QUERY.value, 0.9),
    (r"\b(slow|data slow|මන්දගත|மெதுவாக)\b", Intent.DATA_SLOW.value, 0.9),
    (
        r"\b(paid but|didn.?t receive|missing (data|pack)|නොආ|வரவில்லை)\b",
        Intent.PACK_MISSING.value,
        0.88,
    ),
    (r"\b(can.?t activate|cannot activate|activation fail)\b", Intent.PACK_ACTIVATE.value, 0.88),
    (
        r"\b(pack(age)? (not|isn.?t) work|not working)\b|වැඩ කරන්නේ නැ|வேலை செய்யவில்லை",
        Intent.PACK_NOT_WORKING.value,
        0.88,
    ),
    (r"\b(expir(e|es|ing)|pack end|when my pack)\b|කල් ඉකුත්|காலாவதி", Intent.PACK_EXPIRY.value, 0.86),
    (
        r"\b(reload|top.?up|where.*(money|reload)|payment pending)\b",
        Intent.RELOAD_MISSING.value,
        0.88,
    ),
    (
        r"(?:charged|deduct(?:ed|ion)?|unexpected\s+(?:charge|vas)|(?:rs\.?|lkr)\s*\d+(?:\.\d{2})?)|අය|කපා|ගාස්තු|கட்டண|வாங்கி",
        Intent.UNEXPECTED_CHARGE.value,
        0.88,
    ),
    (
        r"\b(balance|money (go|went|gone)|why.*(rupee|money)|mage balance|බැලන්ස්|இருப்பு)\b",
        Intent.BALANCE_DEDUCTION_QUERY.value,
        0.85,
    ),
    (r"\b(why|charge|charged|debit|money|lkr|රු)\b", Intent.BALANCE_DEDUCTION_QUERY.value, 0.7),
    (r"අය|කපා|ගාස්තු|ඇයි", Intent.BALANCE_DEDUCTION_QUERY.value, 0.75),
    (r"கட்டண|வாங்கி|ஏன்", Intent.BALANCE_DEDUCTION_QUERY.value, 0.75),
    (
        r"\b(how (do|to|can) i|activate a pack|what is fup)\b|කොහොමද|எப்படி",
        Intent.ESIM_HELP.value,
        0.65,
    ),
]

_REPLY_TEMPLATES: dict[str, dict[str, str]] = {
    Intent.BALANCE_DEDUCTION_QUERY.value: {
        "en": "I will check what changed your balance against charging and payment evidence.",
        "si": "බැලන්ස් වෙනස් වූයේ ඇයිදැයි ගාස්තු සහ ගෙවීම් සාක්ෂි සමඟ පරීක්ෂා කරමි.",
        "ta": "இருப்பு மாற்றத்தை கட்டண மற்றும் செலுத்தல் ஆதாரங்களுடன் சரிபார்க்கிறேன்.",
    },
    Intent.UNEXPECTED_CHARGE.value: {
        "en": "This looks like an unexpected charge. I will check consent and charging evidence.",
        "si": "අනපේක්ෂිත අයකිරීමක් ලෙස පෙනේ. අනුමතිය සහ ගාස්තු සාක්ෂි පරීක්ෂා කරමි.",
        "ta": "எதிர்பாராத கட்டணம் போல் தெரிகிறது. ஒப்புதல் மற்றும் கட்டண ஆதாரங்களைச் சரிபார்க்கிறேன்.",
    },
    Intent.DATA_SLOW.value: {
        "en": "I will check your pack usage, FUP status and network signals.",
        "si": "pack භාවිතය, FUP සහ ජාල සංඥා පරීක්ෂා කරමි.",
        "ta": "பேக் பயன்பாடு, FUP மற்றும் நெட்வொர்க் சமிக்ஞைகளைச் சரிபார்க்கிறேன்.",
    },
    Intent.FUP_QUERY.value: {
        "en": "I will check Fair Usage Policy thresholds on your pack.",
        "si": "ඔබේ pack හි Fair Usage Policy සීමා පරීක්ෂා කරමි.",
        "ta": "உங்கள் பேக்கில் Fair Usage Policy வரம்புகளைச் சரிபார்க்கிறேன்.",
    },
    Intent.VAS_SUBSCRIPTIONS.value: {
        "en": "I will list active subscriptions and consent evidence.",
        "si": "සක්‍රීය දායකත්ව සහ අනුමති සාක්ෂි ලැයිස්තුගත කරමි.",
        "ta": "செயலில் உள்ள சந்தாக்கள் மற்றும் ஒப்புதல் ஆதாரங்களைப் பட்டியலிடுகிறேன்.",
    },
    Intent.ESIM_HELP.value: {
        "en": "Here is how to convert to eSIM. For account-specific issues I can open a case.",
        "si": "eSIM වෙත මාරු වන ආකාරය මෙන්න. ගිණුම් ගැටලුවක් නම් case එකක් විවෘත කළ හැක.",
        "ta": "eSIM க்கு மாறும் முறை இதோ. கணக்குச் சிக்கலாக இருந்தால் வழக்கைத் திறக்கலாம்.",
    },
    Intent.PACK_RECOMMEND.value: {
        "en": "I can recommend a pack from your usage pattern. Checking catalogue options.",
        "si": "ඔබේ භාවිත රටාව අනුව pack නිර්දේශ කළ හැක.",
        "ta": "உங்கள் பயன்பாட்டு முறைப்படி பேக் பரிந்துரைக்க முடியும்.",
    },
    Intent.HANDOFF.value: {
        "en": "Connecting you to a human agent. Your case stays open.",
        "si": "නියෝජිතයෙකු වෙත සම්බන්ධ කරමි. Case එක විවෘතව තබනවා.",
        "ta": "முகவருடன் இணைக்கிறேன். வழக்கு திறந்தே இருக்கும்.",
    },
    Intent.FALLBACK.value: {
        "en": "Tell me more about the charge or issue, or pick a suggestion below.",
        "si": "අයකිරීම ගැන තව කියන්න, නැත්නම් පහත යෝජනාවක් තෝරන්න.",
        "ta": "கட்டணம் பற்றி மேலும் சொல்லுங்கள் அல்லது கீழே ஒரு பரிந்துரையைத் தேர்ந்தெடுக்கவும்.",
    },
    Intent.RELOAD_MISSING.value: {
        "en": "I will match recent reloads against settlement confirmations.",
        "si": "මෑත reload සහ settlement තහවුරු කිරීම් සසඳමි.",
        "ta": "சமீபத்திய ரீலோடுகளை settlement உடன் ஒப்பிடுகிறேன்.",
    },
    Intent.DOUBLE_CHARGE.value: {
        "en": "I will look for duplicate charges in the same window.",
        "si": "එකම කාලයේ අනුපිටපත් අයකිරීම් සොයමි.",
        "ta": "அதே சாளரத்தில் நகல் கட்டணங்களைத் தேடுகிறேன்.",
    },
    Intent.PREVENT_CHARGES.value: {
        "en": "You can set spend caps and VAS safeguards. I will open the protection options.",
        "si": "වියදම් සීමා සහ VAS ආරක්ෂා සැකසිය හැක.",
        "ta": "செலவு வரம்புகள் மற்றும் VAS பாதுகாப்புகளை அமைக்கலாம்.",
    },
}


@dataclass
class IntakeResult:
    intent: str
    confidence: float
    slots: dict[str, Any] = field(default_factory=dict)
    language: str = "en"
    needs_handoff: bool = False
    raw_text: str = ""
    route: str = "account"
    client_intent: str = "balance"

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "confidence": self.confidence,
            "slots": self.slots,
            "language": self.language,
            "needs_handoff": self.needs_handoff,
            "raw_text": self.raw_text,
            "route": self.route,
            "client_intent": self.client_intent,
        }


def detect_language(text: str) -> str:
    if _SINHALA.search(text):
        return "si"
    if _TAMIL.search(text):
        return "ta"
    return "en"


def extract_intake(text: str) -> IntakeResult:
    language = detect_language(text)
    search_text = text if language != "en" else text.lower()
    best_intent = Intent.FALLBACK.value
    best_score = 0.0
    for pattern, intent, score in _INTAKE_KEYWORDS:
        if score > best_score and re.search(pattern, search_text, re.IGNORECASE):
            best_intent = intent
            best_score = score
    amounts = re.findall(r"(?:LKR|Rs\.?|රු)?\s*(\d+(?:\.\d{2})?)", text, re.IGNORECASE)
    slots: dict[str, Any] = {}
    if amounts:
        slots["amount_lkr"] = amounts[0]
        slots["amount_hint"] = amounts[0]
    needs_handoff = best_intent == Intent.HANDOFF.value
    routing = routing_payload(best_intent)
    return IntakeResult(
        intent=best_intent,
        confidence=best_score if best_score else 0.3,
        slots=slots,
        language=language,
        needs_handoff=needs_handoff,
        raw_text=text,
        route=routing["route"],
        client_intent=routing["client_intent"],
    )


def check_handoff(intake: IntakeResult) -> dict[str, Any]:
    if intake.needs_handoff or intake.intent == Intent.HANDOFF.value:
        return {
            "handoff": True,
            "reason": "customer_requested_agent",
            "queue": "cx-general",
        }
    if intake.confidence < 0.4:
        return {
            "handoff": False,
            "reason": "low_confidence_clarify",
            "queue": None,
        }
    return {"handoff": False, "reason": None, "queue": None}


def compose_reply(intake: IntakeResult, *, facts: dict[str, Any] | None = None) -> str:
    facts = facts or {}
    lang = intake.language
    key = intake.intent if intake.intent in _REPLY_TEMPLATES else Intent.FALLBACK.value
    if intake.needs_handoff:
        key = Intent.HANDOFF.value
    bundle = _REPLY_TEMPLATES.get(key) or _REPLY_TEMPLATES[Intent.FALLBACK.value]
    template = bundle.get(lang) or bundle["en"]
    amount = facts.get("amount_lkr") or intake.slots.get("amount_lkr")
    if amount and key in {
        Intent.UNEXPECTED_CHARGE.value,
        Intent.BALANCE_DEDUCTION_QUERY.value,
    }:
        return f"{template} (LKR {amount})"
    return template


@dataclass
class TurnResult:
    intake: IntakeResult
    handoff: dict[str, Any]
    reply: str
    case_id: str | None = None
    follow_ups: list[dict[str, str]] = field(default_factory=list)
    card_hints: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "intake": self.intake.to_dict(),
            "handoff": self.handoff,
            "reply": self.reply,
            "case_id": self.case_id,
            "follow_ups": self.follow_ups,
            "card_hints": self.card_hints,
            "route": self.intake.route,
            "client_intent": self.intake.client_intent,
        }


def handle_turn(
    text: str,
    *,
    case_id: str | None = None,
    facts: dict[str, Any] | None = None,
    language_hint: str | None = None,
    intent_override: str | None = None,
) -> TurnResult:
    facts = facts or {}
    intake = extract_intake(text)
    # Prior turn context from the UI (product under discussion, amount, case).
    for key in ("product", "amount_lkr", "case_id", "chat_intent"):
        value = facts.get(key)
        if value is not None and key not in intake.slots:
            intake.slots[key] = value
    if intent_override:
        intake.intent = intent_override
        routing = routing_payload(intent_override)
        intake.route = routing["route"]
        intake.client_intent = routing["client_intent"]
        intake.needs_handoff = intent_override == Intent.HANDOFF.value
        intake.confidence = max(intake.confidence, 0.95)
    elif intake.confidence < 0.5 and facts.get("chat_intent") and facts.get("product"):
        # Weak follow-ups like "Can you stop it?" keep the discussed service.
        prior = str(facts["chat_intent"])
        intake.intent = prior
        routing = routing_payload(prior)
        intake.route = routing["route"]
        intake.client_intent = routing["client_intent"]
        intake.confidence = max(intake.confidence, 0.8)
    if language_hint in {"si", "ta", "en"}:
        intake.language = language_hint
    handoff = check_handoff(intake)
    if handoff["handoff"]:
        intake.route = "handoff"
        intake.client_intent = "human"
    reply = compose_reply(intake, facts=facts)
    routing = routing_payload(intake.intent)
    return TurnResult(
        intake=intake,
        handoff=handoff,
        reply=reply,
        case_id=case_id,
        follow_ups=routing["follow_ups"],
        card_hints={
            "title_key": "foundReason",
            "show_evidence": intake.route in {"account", "both"},
        },
    )


def suggest_for_snapshot(
    snapshot: dict[str, Any] | None = None,
    *,
    language: str = "en",
    limit: int = 6,
) -> dict[str, Any]:
    signals = signals_from_snapshot(snapshot)
    return build_suggestions(signals, language=language, limit=limit)
