"""Classifying what a customer asked for (C04, #23; plan 22 section 4 step 3).

Keyword rules first, a model only when the rules are unsure, and the rules are
always the floor (ADR-0009). What comes out is a **hint**, never evidence: the
intent chooses a journey and the slots fill a form, and neither decides a cause,
an amount or an eligibility (I2).

**Rules are ordered, not scored against each other.** The previous version kept
a flat list of (pattern, intent, confidence) and took the highest confidence
that matched anywhere, which made specificity a function of whatever number
somebody typed: "why was LKR 49 deducted from my balance" matched both the
unexpected-charge rule at 0.88 and the balance rule at 0.85, so it classified as
an unexpected charge because of a 0.03 difference nobody intended. Here the
table is read top to bottom and the **first** match wins, so a rule is more
specific than another because it is above it, which is reviewable.

**Singlish is first class, not a special case.** Sinhala written in Latin script
is how a great many customers type, and the measurement said so loudly: before
C04, 13 of 20 Singlish examples classified as FALLBACK, because the rules held
no Singlish vocabulary at all. The vocabulary lives in `clarity.ai.language`,
shared with knowledge retrieval (K02), so improving it improves both.

**ASSUMPTION** on every romanisation below: Sinhala has no standard
romanisation, so "gaasthu", "gasthu" and "gastu" are all the same word and each
spelling has to be listed to be matched. **REQUIRES HUTCH CONFIRMATION** against
real message traffic.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Protocol

from clarity.ai.language import SINGLISH_TERMS
from clarity.modules.conversation.intents import Intent

#: Confidence for a rule that matched a phrase specific to one intent.
CERTAIN = 0.92

#: Confidence for a rule that matched a single discriminating word.
LIKELY = 0.80

#: Confidence for a rule that matched something suggestive but ambiguous.
UNSURE = 0.55

#: What a FALLBACK carries. Below `MIN_SWITCH_CONFIDENCE` in the router, which
#: is what stops a vague turn pulling a customer out of an active flow (C02).
VAGUE = 0.30

#: Below this the `extract` role is asked, when one is configured. Above it the
#: rules are confident enough that a model could only disagree, and a model
#: that can overrule a confident keyword match is a model that can reroute a
#: customer on a whim.
ASSIST_BELOW = 0.70


@dataclass(frozen=True)
class Rule:
    """One ordered rule: a pattern, the intent it means, and how sure that is."""

    pattern: str
    intent: Intent
    confidence: float = CERTAIN
    note: str = ""

    def matches(self, text: str) -> bool:
        return re.search(self.pattern, text, re.IGNORECASE | re.UNICODE) is not None


def _any(*words: str) -> str:
    """A pattern matching any of ``words`` as whole words."""
    return r"(?:\b(?:" + "|".join(words) + r")\b)"


#: The rule table, read top to bottom, first match wins.
#:
#: Grouped by what the rule is about rather than by language, because the same
#: question asked in four languages is one rule to review and four alternations
#: to keep in step. A rule with no Singlish alternation is a rule a Singlish
#: speaker cannot reach.
RULES: tuple[Rule, ...] = (
    # -- a person, always first ------------------------------------------ #
    Rule(
        _any(
            "agent",
            "human",
            "person",
            "someone",
            "staff",
            "officer",
            "operator",
            "speak to",
            "talk to",
            "complaint",
            "complain",
            "fraud",
            "police",
            "lawyer",
            # Singlish: "kenek/kenekwa ekka katha karanna" = talk with someone.
            "kenek",
            "kenekwa",
            "kattiya",
            "niladhariya",
        )
        + r"|නීති|පොලීස්|නිලධාරි|කතා කරන්න|මනුෂ|மனிதர்|முறையீடு|ஊழிய|பேச",
        Intent.HANDOFF,
        0.95,
        note="A customer asking for a person is never kept in automation.",
    ),
    # -- specific, phrase-level intents ---------------------------------- #
    Rule(
        _any("esim", "e-sim", "convert to esim", "physical sim"),
        Intent.ESIM_HELP,
    ),
    Rule(
        _any(
            "twice",
            "two times",
            "double charge",
            "duplicate",
            "charged again",
            "dewarak",
            "deperak",
            "dewathawak",
        )
        + r"|දෙවර|දෙවතාව|இரண்டு முறை|இருமுறை",
        Intent.DOUBLE_CHARGE,
    ),
    Rule(
        _any(
            "recommend",
            "best pack",
            "best package",
            "which pack",
            "which package",
            "suitable",
            "suggest",
            "hondama",
            "honda",
            "hoda",
        )
        + r"|හොඳම|නිර්දේශ|சிறந்த|பரிந்துரை",
        Intent.PACK_RECOMMEND,
    ),
    Rule(
        _any(
            "prevent",
            "safeguard",
            "spend cap",
            "spending limit",
            "block future",
            "stop unexpected",
            "walakwa",
            "welakwanna",
        )
        + r"|වැළැක්|සීමාව|தடுக்க|வரம்பு",
        Intent.PREVENT_CHARGES,
    ),
    # Expiry before activation: "when does my pack expire" also contains "pack".
    Rule(
        _any(
            "expire",
            "expires",
            "expiry",
            "expiring",
            "expired",
            "run out",
            "runs out",
            "ends",
            "valid till",
            "validity",
            "ivara",
            "iwara",
            "awasan",
        )
        + r"|කල් ඉකුත්|අවසන්|ඉවර|காலாவதி|முடிவ",
        Intent.PACK_EXPIRY,
    ),
    Rule(
        _any("activate", "activation", "turn on", "enable", "switch on", "start the", "aktivate")
        + r"|සක්රිය|ක්රියාත්මක|இயக்க|செயல்படுத்த",
        Intent.PACK_ACTIVATE,
        note="Not 'ganna', which is 'to take' or 'to buy': 'package ganna but "
        "wada karanne naththa' is a pack that does not work, not one to activate.",
    ),
    Rule(
        _any(
            "stop",
            "cancel",
            "disable",
            "unsubscribe",
            "opt out",
            "nawaththanna",
            "nawatanna",
            "navattanna",
            "epa",
        )
        + r"|\bturn\b.{0,12}\boff\b"
        + r"|නවත්ව|අවලංගු|නැවැත්|நிறுத்து|ரத்து",
        Intent.VAS_SUBSCRIPTIONS,
        note="Stopping something is about a subscription, not a safeguard.",
    ),
    Rule(
        _any(
            "subscription",
            "subscriptions",
            "vas",
            "vas list",
            "active vas",
            "content service",
            "gamezone",
            "gamehub",
            "ringtone",
        )
        + r"|දායක|சந்தா",
        Intent.VAS_SUBSCRIPTIONS,
        note="Not 'සේවාව' alone: it only means 'service' and appears in "
        "unexpected-charge complaints, which it used to capture.",
    ),
    Rule(
        _any(
            "my case",
            "case status",
            "ticket",
            "ticket status",
            "reference number",
            "complaint status",
        )
        + r"|කේස්|පැමිණිල්ල|වழக்கு|புகார்",
        Intent.CASE_STATUS,
    ),
    Rule(
        _any("refund", "money back", "got my money back", "reimburse", "apahu", "apasu")
        + r"|ආපසු|නැවත ලැබ|பணத்தைத் திருப்ப|திரும்ப",
        Intent.REFUND_STATUS,
    ),
    Rule(
        _any(
            "network", "no signal", "signal", "coverage", "outage", "tower", "no service", "no bars"
        )
        + r"|සිග්නල්|(?<!අන්තර්)ජාලය|කව්රේජ්|சிக்னல்|நெட்வொர்க்|சேவை இல்லை",
        Intent.NETWORK_STATUS,
        note="'ජාලය' is guarded against 'අන්තර්ජාලය' (internet), which it is a "
        "substring of: a slow-internet complaint was reading as an outage.",
    ),
    Rule(
        _any("fup", "fair use", "fair usage", "throttle", "throttled", "capped", "wegaya", "wega")
        + r"|සාධාරණ භාවිත|වේගය අඩු|வேகம் குறை|நியாயமான பயன்பாடு",
        Intent.FUP_QUERY,
    ),
    # Speed reduced is FUP, not a balance question. "been reduced" has to match
    # as well as "reduced": the previous pattern required the two words to be
    # adjacent and so missed "why has my speed been reduced".
    Rule(
        r"\b(?:speed|wegaya|wega)\b.{0,24}\b(?:reduc\w*|slow\w*|drop\w*|low|adu|aduwela)\b"
        r"|\b(?:reduc\w*|adu)\b.{0,24}\b(?:speed|wegaya|wega)\b"
        r"|වේගය.{0,16}අඩු|வேகம்.{0,16}குறை",
        Intent.FUP_QUERY,
    ),
    Rule(
        _any(
            "pack not working",
            "package not working",
            "not working",
            "doesnt work",
            "does not work",
            "wada karanne",
            "wada na",
            "weda karanne",
        )
        + r"|වැඩ කරන්නේ නැ|ක්රියා කරන්නේ නැ|வேலை செய்யவில்லை",
        Intent.PACK_NOT_WORKING,
    ),
    Rule(
        _any(
            "cant activate",
            "cannot activate",
            "activation failed",
            "activation fail",
            "barida",
            "bari",
            "bae",
        )
        + r"|සක්රිය කළ නොහැ|இயக்க முடியவில்லை",
        Intent.PACK_NOT_WORKING,
    ),
    Rule(
        _any(
            "disappeared",
            "disappear",
            "gone missing",
            "missing pack",
            "missing package",
            "missing data",
            "lost my pack",
            "nathi",
            "nathiwela",
            "nethi",
        )
        + r"|නැති වී|අතුරුදහන්|காணவில்லை|தொலைந்த",
        Intent.PACK_MISSING,
    ),
    # Reload before the generic money rules: a missing top-up is about the
    # top-up, not about the balance it should have changed.
    Rule(
        r"(?:\b(?:reload|reloaded|top.?up|topped.?up|recharge|recharged)\b.{0,40}"
        r"\b(?:not|didn.?t|hasn.?t|never|missing|pending|awe|enne|naththa|na)\b)"
        r"|(?:\b(?:not|didn.?t|hasn.?t|never|no)\b.{0,40}"
        r"\b(?:reload|top.?up|recharge|arrive\w*|receive\w*|show\w*|credit\w*)\b)"
        r"|රීලෝඩ්.{0,24}(?:නැ|ලැබී නැ)|ரீலோட்.{0,24}(?:இல்லை|வரவில்லை)",
        Intent.RELOAD_MISSING,
    ),
    Rule(
        _any(
            "reload", "reloaded", "top up", "topped up", "recharge", "recharged", "payment pending"
        )
        + r"|රීලෝඩ්|ප්රතිපූරණ|ரீலோட்",
        Intent.RELOAD_MISSING,
        LIKELY,
    ),
    # -- the money questions, specific before generic -------------------- #
    Rule(
        r"\b(?:balance|credit|salli|mudal)\b.{0,40}"
        r"\b(?:deduct\w*|reduc\w*|cut|gone|went|disappear\w*|low|adu|aduwela|kapala)\b"
        r"|\b(?:deduct\w*|cut|kapa\w*)\b.{0,40}\b(?:balance|credit|salli|mudal)\b"
        r"|(?:බැලන්ස්|මුදල්|ගිණුම).{0,24}(?:අඩු|කපා|කැප|ගියේ)"
        r"|(?:ගිණුම|රුපියල්).{0,30}(?:කැප|කපා|අඩු)"
        r"|(?:இருப்பு|பணம்|கணக்க|ரூபாய்).{0,30}(?:குறை|எடுக்க|கழி)",
        Intent.BALANCE_DEDUCTION_QUERY,
        note="A deduction from a balance is a balance question, whatever the amount.",
    ),
    Rule(
        _any(
            "dont know",
            "do not know",
            "didnt subscribe",
            "did not subscribe",
            "never subscribed",
            "unknown service",
            "did not authorise",
            "unauthorised",
            "nodanne",
            "danne na",
            "danne ne",
        )
        + r"|නොදන්නා|දන්නේ නැ|අනුමත කළේ නැ|தெரியாத|சந்தா செய்யவில்லை",
        Intent.UNEXPECTED_CHARGE,
        note="Not recognising the service is what makes a charge unexpected.",
    ),
    Rule(
        _any(
            "unexpected charge",
            "unexpected",
            "cannot explain",
            "cant explain",
            "unexplained",
            "strange charge",
            "wrong charge",
        )
        + r"|අනපේක්ෂිත|විස්තර කළ නොහැ|எதிர்பாராத",
        Intent.UNEXPECTED_CHARGE,
    ),
    Rule(
        _any(
            "charged",
            "charge",
            "charges",
            "deducted",
            "deduction",
            "debited",
            "billed",
            "gaasthu",
            "gasthu",
            "gastu",
            "gaasthuwak",
            "gewila",
            "gewuna",
        )
        + r"|අය කර|කපා ගෙන|ගාස්තු|கட்டண|வாங்கி",
        Intent.UNEXPECTED_CHARGE,
        LIKELY,
    ),
    Rule(
        _any("balance", "credit", "money", "salli", "mudal") + r"|බැලන්ස්|මුදල්|இருப்பு|பணம்",
        Intent.BALANCE_DEDUCTION_QUERY,
        LIKELY,
    ),
    # -- the slow-data family, last because "slow" is common ------------- #
    Rule(
        _any(
            "slow",
            "slowly",
            "laggy",
            "lagging",
            "buffering",
            "crawling",
            "hemin",
            "hemihita",
            "madagathi",
        )
        + r"|මන්දගාමී|මන්දගත|සෙමින්|மெதுவாக|மெது",
        Intent.DATA_SLOW,
    ),
    Rule(
        _any("data", "internet", "pack", "package", "bundle")
        + r"|දත්ත|අන්තර්ජාල|පැකේජ|தரவு|இணைய|தொகுப்பு",
        Intent.PACK_NOT_WORKING,
        UNSURE,
        note="A bare mention of data or a pack, with nothing saying what about it.",
    ),
    Rule(
        _any("how do i", "how to", "how can i", "what is", "kohomada", "kohomda")
        + r"|කොහොමද|කෙසේද|எப்படி",
        Intent.FALLBACK,
        UNSURE,
        note=(
            "A how-to with no topic. This used to answer ESIM_HELP, on the "
            "reasoning that knowledge would retrieve or refuse. Measured (S01): "
            'on the caseless path it did neither. "What is the capital of '
            'France?" and "How do I make a bomb" were both answered with "Here '
            'is how to convert to eSIM", because the stateless path composes '
            "from the intent template and has no grounding step to refuse. A "
            "topicless question is not an eSIM question, so it is not labelled "
            "one; FALLBACK invites the customer to say what it is about and "
            "stays inside the domain. The stateful path still grounds or says "
            "it has no published source."
        ),
    ),
)


class IntakeAssist(Protocol):
    """The `extract` role, asked only when the rules are unsure (C04).

    Returns an intent name or ``None``. Whatever it returns is checked against
    the catalogue before it is used, so a model cannot invent an intent and no
    flow can be reached that no rule could reach.
    """

    def classify(self, text: str) -> str | None: ...


#: Zero-width characters that change nothing a reader sees and everything a
#: regex matches. Sinhala writes conjunct consonants with a zero-width joiner,
#: so "සක්‍රිය" (activate) and "සක්රිය" are the same word to a customer and two
#: different strings to `re`. Measured: the activation rule missed a Sinhala
#: activation request for exactly this reason.
_INVISIBLE = re.compile(r"[\u200b-\u200f\u202a-\u202e\ufeff]")


def normalise(text: str) -> str:
    """NFC and no zero-width characters, so a pattern can be written plainly."""
    return _INVISIBLE.sub("", unicodedata.normalize("NFC", text))


def classify(
    text: str,
    *,
    assist: IntakeAssist | None = None,
    assist_below: float = ASSIST_BELOW,
) -> tuple[str, float, bool]:
    """The intent, how sure, and whether a model was consulted.

    The rules run first and always. A model is asked only when they came back
    under ``assist_below``, and only to replace a weak answer with a real
    intent: it cannot overrule a confident match, and it cannot return
    something outside the catalogue.
    """
    intent, confidence = _by_rules(normalise(text))
    if assist is None or confidence >= assist_below:
        return intent, confidence, False

    try:
        suggested = assist.classify(text)
    except Exception:
        # The extract role is a provider call. Its failure costs the assist,
        # never the turn: the rules already answered.
        return intent, confidence, False

    if not suggested:
        return intent, confidence, True
    try:
        named = Intent(suggested.strip().upper())
    except ValueError:
        # A model naming an intent that does not exist is a rejected answer,
        # not a new intent. Silently accepting one would let a model reach a
        # flow no rule can reach, which is agency this layer does not have.
        return intent, confidence, True
    if named is Intent.FALLBACK:
        return intent, confidence, True
    # Capped, deliberately. A model-sourced intent must not look as certain as
    # a matched phrase, because the router uses the number to decide whether to
    # move a customer out of a flow they are already in (C02).
    return named.value, min(LIKELY, max(confidence, UNSURE)), True


def _by_rules(text: str) -> tuple[str, float]:
    """The first rule that matches, top to bottom."""
    for rule in RULES:
        if rule.matches(text):
            return rule.intent.value, rule.confidence
    return Intent.FALLBACK.value, VAGUE


#: Words that mark Latin-script text as Singlish rather than English. Drawn
#: from the lexicon shared with retrieval, plus the grammatical particles that
#: carry no meaning on their own and so are not in it.
_SINGLISH_MARKERS: frozenset[str] = frozenset(SINGLISH_TERMS) | {
    # Pronouns and demonstratives.
    "mama",
    "mage",
    "mata",
    "api",
    "ape",
    "oya",
    "oyage",
    "eya",
    "meka",
    "mekata",
    "mewa",
    "ara",
    "arage",
    # The definite particle and its inflections, which are in almost every
    # Singlish sentence. "eka" alone is weak, which is why two markers are
    # required rather than one.
    "eka",
    "eke",
    "ekak",
    "eken",
    "ekata",
    "ekakata",
    "ekath",
    # Question words. A Singlish question almost always carries one, and none
    # of them is an English word, so they are strong markers.
    "mokakda",
    "mokawada",
    "mokada",
    "mokak",
    "kohomada",
    "kohomda",
    "kawada",
    "kiyada",
    "koheda",
    "aida",
    # Verb endings and particles: what makes a sentence Singlish rather than
    # English with a loan word in it.
    "karanna",
    "karala",
    "kala",
    "karanne",
    "wenne",
    "wenawada",
    "wela",
    "danna",
    "danne",
    "dapu",
    "ganna",
    "gaththa",
    "enawada",
    "enne",
    "awe",
    "naththa",
    "naththam",
    "nathi",
    "nethi",
    "puluwanda",
    "puluwan",
    "ona",
    "oni",
    "epa",
    "tawama",
    "thawama",
    "ane",
    "nam",
    "hari",
    "nawaththanna",
    "nawatanna",
    "navattanna",
    "aktivate",
    "ivara",
    "iwara",
    # Quantifiers, intensifiers and courtesy.
    "godak",
    "tikak",
    "hondama",
    "honda",
    "hoda",
    "bohoma",
    "sthuthi",
    "karunakara",
    # Time words that appear in complaints.
    "ada",
    "ude",
    "udhe",
    "iye",
    "heta",
    "dawasa",
    "sita",
    "idan",
}

#: How many markers make a sentence Singlish rather than English with a stray
#: loan word. Two, because one is often a name or a coincidence.
_SINGLISH_MARKERS_NEEDED = 2

_SINHALA = re.compile(r"[඀-෿]")
_TAMIL = re.compile(r"[஀-௿]")
_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)


def detect_language(text: str) -> str:
    """The language a message is written in, including Singlish (C04).

    Script first, because Sinhala and Tamil script are unambiguous. Then
    Singlish, which has no script of its own: it is Latin text carrying Sinhala
    words, so it is recognised by vocabulary and nothing else can recognise it.

    Returns ``si-en`` for Singlish, which is what the evaluation datasets call
    it. A05 recorded that intake reported it as ``en``; this is that gap closed.
    """
    if _SINHALA.search(text):
        return "si"
    if _TAMIL.search(text):
        return "ta"
    words = {match.group(0).casefold() for match in _WORD.finditer(text)}
    if len(words & _SINGLISH_MARKERS) >= _SINGLISH_MARKERS_NEEDED:
        return "si-en"
    return "en"


def reply_language(detected: str) -> str:
    """Which language to answer in. Singlish is answered in Sinhala.

    A Singlish speaker writes Latin script and reads Sinhala, and the approved
    templates exist in si, ta and en (I15). Answering Singlish in English would
    be a guess about literacy; Sinhala is the language the words are.
    """
    return "si" if detected == "si-en" else detected


__all__ = [
    "ASSIST_BELOW",
    "CERTAIN",
    "LIKELY",
    "RULES",
    "UNSURE",
    "VAGUE",
    "IntakeAssist",
    "Rule",
    "classify",
    "detect_language",
    "reply_language",
]
