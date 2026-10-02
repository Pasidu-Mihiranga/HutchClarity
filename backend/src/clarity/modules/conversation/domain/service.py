"""Conversation intake, language ID, handoff, and template composition."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


_SINHALA = re.compile(r"[඀-෿]")
_TAMIL = re.compile(r"[஀-௿]")

# Keyword → structured intake slots (LLM via ai-gateway later).
_INTAKE_KEYWORDS: list[tuple[str, str, float]] = [
    (r"\b(vas|subscription|gamehub|renewal|subscribe)\b", "vas_charge", 0.85),
    (r"\b(pack|data|fup|throttle|slow)\b", "pack_fup", 0.8),
    (r"\b(reload|top.?up|payment|double)\b", "payment", 0.8),
    (r"\b(outage|no signal|network)\b", "outage", 0.75),
    (r"\b(loan|credit)\b", "loan", 0.7),
    (r"\b(why|charge|charged|debit|money|lkr|රු|කැප්පුම)\b", "why_charge", 0.7),
    (r"අය|කපා|ගාස්තු", "why_charge", 0.75),
    (r"கட்டண|வாங்கி", "why_charge", 0.75),
]

_HANDOFF_TRIGGERS = re.compile(
    r"\b(agent|human|speak to|talk to|complaint|fraud|police|lawyer)\b|"
    r"නීති|පොලීස්|மனிதர்|முறையீடு",
    re.IGNORECASE,
)

_REPLY_TEMPLATES: dict[str, dict[str, str]] = {
    "why_charge": {
        "en": "I can explain the charge. Share the amount or open Why? in the app.",
        "si": "අයකිරීම පැහැදිලි කළ හැක. මුදල දක්වන්න හෝ Why? භාවිතා කරන්න.",
        "ta": "கட்டணத்தை விளக்க முடியும். தொகையைச் சொல்லுங்கள் அல்லது Why? பயன்படுத்தவும்.",
    },
    "vas_charge": {
        "en": "This looks like a VAS subscription charge. I will check consent evidence.",
        "si": "මෙය VAS ගාස්තුවක් ලෙස පෙනේ. අනුමතිය පරීක්ෂා කරමි.",
        "ta": "இது VAS கட்டணம் போல் தெரிகிறது. ஒப்புதலைச் சரிபார்க்கிறேன்.",
    },
    "pack_fup": {
        "en": "I will check your pack usage and FUP status.",
        "si": "ඔබේ pack භාවිතය සහ FUP තත්ත්වය පරීක්ෂා කරමි.",
        "ta": "பேக் பயன்பாடு மற்றும் FUP நிலையைச் சரிபார்க்கிறேன்.",
    },
    "payment": {
        "en": "I will review recent reloads and settlement status.",
        "si": "මෑත reload සහ settlement තත්ත්වය බලමි.",
        "ta": "சமீபத்திய ரீலோடுகளைச் சரிபார்க்கிறேன்.",
    },
    "outage": {
        "en": "I will check network status for your area.",
        "si": "ඔබේ ප්‍රදේශයේ ජාල තත්ත්වය පරීක්ෂා කරමි.",
        "ta": "உங்கள் பகுதியின் நெட்வொர்க் நிலையைச் சரிபார்க்கிறேன்.",
    },
    "loan": {
        "en": "I will check airtime loan and recovery charges.",
        "si": "loan සහ recovery අයකිරීම් පරීක්ෂා කරමි.",
        "ta": "கடன் மற்றும் வசூல் கட்டணங்களைச் சரிபார்க்கிறேன்.",
    },
    "handoff": {
        "en": "Connecting you to a human agent. Your case stays open.",
        "si": "නියෝජිතයෙකු වෙත සම්බන්ධ කරමි. Case එක විවෘතව තබනවා.",
        "ta": "முகவருடன் இணைக்கிறேன். வழக்கு திறந்தே இருக்கும்.",
    },
    "fallback": {
        "en": "Tell me more about the charge or issue, or type WHY.",
        "si": "අයකිරීම ගැන තව කියන්න, නැත්නම් WHY ලියන්න.",
        "ta": "கட்டணம் பற்றி மேலும் சொல்லுங்கள் அல்லது WHY எழுதுங்கள்.",
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "confidence": self.confidence,
            "slots": self.slots,
            "language": self.language,
            "needs_handoff": self.needs_handoff,
            "raw_text": self.raw_text,
        }


def detect_language(text: str) -> str:
    """Heuristic language ID: si / ta / en."""
    if _SINHALA.search(text):
        return "si"
    if _TAMIL.search(text):
        return "ta"
    return "en"


def extract_intake(text: str) -> IntakeResult:
    """Keyword + structure extract (LLM via ai-gateway later)."""
    language = detect_language(text)
    lowered = text.lower()
    best_intent = "fallback"
    best_score = 0.0
    for pattern, intent, score in _INTAKE_KEYWORDS:
        if re.search(pattern, lowered if language == "en" else text, re.IGNORECASE):
            if score > best_score:
                best_intent = intent
                best_score = score
    amounts = re.findall(r"(?:LKR|Rs\.?|රු)?\s*(\d+(?:\.\d{2})?)", text, re.IGNORECASE)
    slots: dict[str, Any] = {}
    if amounts:
        slots["amount_hint"] = amounts[0]
    needs_handoff = bool(_HANDOFF_TRIGGERS.search(text))
    if needs_handoff:
        best_intent = "handoff"
        best_score = max(best_score, 0.9)
    return IntakeResult(
        intent=best_intent,
        confidence=best_score if best_score else 0.3,
        slots=slots,
        language=language,
        needs_handoff=needs_handoff,
        raw_text=text,
    )


def check_handoff(intake: IntakeResult) -> dict[str, Any]:
    if intake.needs_handoff or intake.intent == "handoff":
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
    """Compose a reply from approved templates (not free-form LLM text)."""
    facts = facts or {}
    lang = intake.language
    key = intake.intent if intake.intent in _REPLY_TEMPLATES else "fallback"
    if intake.needs_handoff:
        key = "handoff"
    template = _REPLY_TEMPLATES[key].get(lang) or _REPLY_TEMPLATES[key]["en"]
    amount = facts.get("amount_lkr") or intake.slots.get("amount_hint")
    if amount and "{amount}" not in template and key == "why_charge":
        return f"{template} (LKR {amount})"
    return template


@dataclass
class TurnResult:
    intake: IntakeResult
    handoff: dict[str, Any]
    reply: str
    case_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "intake": self.intake.to_dict(),
            "handoff": self.handoff,
            "reply": self.reply,
            "case_id": self.case_id,
        }


def handle_turn(
    text: str,
    *,
    case_id: str | None = None,
    facts: dict[str, Any] | None = None,
    language_hint: str | None = None,
) -> TurnResult:
    intake = extract_intake(text)
    if language_hint in {"si", "ta", "en"}:
        intake.language = language_hint
    handoff = check_handoff(intake)
    reply = compose_reply(intake, facts=facts)
    return TurnResult(intake=intake, handoff=handoff, reply=reply, case_id=case_id)
