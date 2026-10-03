"""Conversation intake, language ID, handoff, and template composition."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from clarity.modules.conversation.intake import IntakeAssist, classify, reply_language
from clarity.modules.conversation.intake import detect_language as _detect_language
from clarity.modules.conversation.intent_routes import routing_payload
from clarity.modules.conversation.intents import Intent
from clarity.modules.conversation.suggestions import (
    build_suggestions,
    signals_from_snapshot,
)

_SINHALA = re.compile(r"[඀-෿]")
_TAMIL = re.compile(r"[஀-௿]")

# (pattern, intent, score) - en/si/ta. Highest score wins.
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
    assisted: bool = False
    """Whether the `extract` role was consulted (C04). Recorded, not cosmetic:
    a reader of the audit needs to know an intent came from a model and not
    from a matched phrase."""

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "confidence": self.confidence,
            "slots": self.slots,
            "language": self.language,
            "needs_handoff": self.needs_handoff,
            "raw_text": self.raw_text,
            "assisted": self.assisted,
            "route": self.route,
            "client_intent": self.client_intent,
        }


def detect_language(text: str) -> str:
    """Kept as the module's name for it; the rules live in `intake.py` (C04)."""
    return _detect_language(text)


def extract_intake(text: str, *, assist: IntakeAssist | None = None) -> IntakeResult:
    """Classify one message. Keyword rules first, a model only when unsure (C04).

    ``assist`` is the `extract` role and is optional: with none configured the
    rules answer alone, which is the supported default (ADR-0009).
    """
    language = detect_language(text)
    best_intent, best_score, assisted = classify(text, assist=assist)
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
        assisted=assisted,
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
    # Singlish has no template set of its own and should not: the approved
    # wording exists in si, ta and en (I15), and a Singlish speaker reads
    # Sinhala. Without this the lookup fell through to English.
    lang = reply_language(intake.language)
    key = intake.intent if intake.intent in _REPLY_TEMPLATES else Intent.FALLBACK.value
    if intake.needs_handoff:
        key = Intent.HANDOFF.value
    bundle = _REPLY_TEMPLATES.get(key) or _REPLY_TEMPLATES[Intent.FALLBACK.value]
    template = bundle.get(lang) or bundle["en"]
    # Only a figure from FACTS, never the one the customer typed. The slot is
    # still filled, because it narrows which charges are worth looking at (I2),
    # but quoting it back reads as agreement to an amount nothing decided. The
    # turn verifier refuses a reply carrying a figure outside FACTS, so the
    # fallback that used to be here made correct-looking replies unsendable.
    amount = facts.get("amount_lkr")
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
