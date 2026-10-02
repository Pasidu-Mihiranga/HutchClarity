"""CX-approved explanation templates (deck S7: "Works without the LLM").

These live in the core, not under ``ai/``, because they are **content**: no
model is involved in producing them. That also keeps the layering honest - the
case service needs wording for a receipt, and should not have to import the AI
package to get it.

Templates are the floor the whole system stands on. If every model is down, or
the verifier rejects what one wrote, the customer still gets a correct answer
in their own language - assembled from the decision's facts, not generated.

They are also the fastest and cheapest path, which is why the router tries
them first (deck S14, tier 1: "Rules + templates - 0 tokens").

**Prototype note.** The Sinhala and Tamil strings here were written for the
demo and have **not been reviewed by native speakers**. Plan §30.2 and §49.2
put CX content design and native review on the critical path before any
customer sees these.
"""

from __future__ import annotations

from decimal import Decimal

from clarity.contracts.decision import Outcome
from clarity.kernel.common import Language

#: rule_id -> language -> template. ``{amount}`` is the only substitution, and
#: it comes from the decision record.
_CAUSE: dict[str, dict[Language, str]] = {
    "VAS_NO_CONSENT": {
        Language.EN: (
            "LKR {amount} was charged for a subscription, and we found no OTP "
            "or second confirmation from you before that charge."
        ),
        Language.SI: (
            "දායකත්වයක් සඳහා රු. {amount} අය කර ඇත. ඒ සඳහා ඔබගෙන් OTP එකක් හෝ දෙවන තහවුරු කිරීමක් අපට හමු නොවීය."
        ),
        Language.TA: (
            "ஒரு சந்தாவுக்கு ரூ. {amount} கட்டணம் விதிக்கப்பட்டது. அதற்கு உங்களிடமிருந்து "
            "OTP அல்லது இரண்டாவது உறுதிப்படுத்தல் எதுவும் எங்களுக்குக் கிடைக்கவில்லை."
        ),
    },
    "DUPLICATE_RELOAD": {
        Language.EN: (
            "Your reload of LKR {amount} was taken twice by the bank, but your "
            "balance was credited only once."
        ),
        Language.SI: "ඔබගේ රු. {amount} රීලෝඩ් එක බැංකුව දෙවරක් අය කර ඇත, නමුත් ශේෂයට එක් වරක් පමණි.",
        Language.TA: (
            "உங்கள் ரூ. {amount} ரீலோட் வங்கியால் இரண்டு முறை எடுக்கப்பட்டது, "
            "ஆனால் இருப்புக்கு ஒரு முறை மட்டுமே சேர்க்கப்பட்டது."
        ),
    },
    "RELOAD_NOT_CREDITED": {
        Language.EN: (
            "LKR {amount} was taken by your bank, but we cannot find a matching "
            "credit to your balance."
        ),
        Language.SI: "ඔබගේ බැංකුව රු. {amount} අය කර ඇත, නමුත් ඔබගේ ශේෂයට එය එකතු වී නැත.",
        Language.TA: ("உங்கள் வங்கி ரூ. {amount} எடுத்துள்ளது, ஆனால் அது உங்கள் இருப்பில் சேரவில்லை."),
    },
    "FUP_CAP_REACHED": {
        Language.EN: (
            "Your data slowed down because the pack reached its fair-use cap. "
            "That cap was shown when you bought the pack, so nothing was charged wrongly."
        ),
        Language.SI: (
            "ඔබගේ පැකේජයේ සාධාරණ භාවිත සීමාවට ළඟා වූ නිසා දත්ත වේගය අඩු විය. "
            "එම සීමාව මිලදී ගැනීමේදී පෙන්වා ඇත, එබැවින් වැරදි ලෙස අය කර නැත."
        ),
        Language.TA: (
            "உங்கள் தொகுப்பு நியாயமான பயன்பாட்டு வரம்பை அடைந்ததால் தரவு வேகம் குறைந்தது. "
            "அந்த வரம்பு வாங்கும்போது காட்டப்பட்டது, எனவே தவறாக எதுவும் வசூலிக்கப்படவில்லை."
        ),
    },
    "DUPLICATE_VAS_CHARGE": {
        Language.EN: "The same subscription was charged twice, so LKR {amount} was taken in error.",
        Language.SI: "එකම දායකත්වය දෙවරක් අය කර ඇති බැවින් රු. {amount} වැරදියට අය වී ඇත.",
        Language.TA: "ஒரே சந்தா இரண்டு முறை வசூலிக்கப்பட்டதால் ரூ. {amount} தவறாக எடுக்கப்பட்டது.",
    },
    "PACK_EXPIRY_BURN": {
        Language.EN: (
            "LKR {amount} of data was used from your main balance after your pack ended."
        ),
        Language.SI: "ඔබගේ පැකේජය අවසන් වූ පසු ප්‍රධාන ශේෂයෙන් රු. {amount} ක දත්ත භාවිත වී ඇත.",
        Language.TA: (
            "உங்கள் தொகுப்பு முடிந்த பிறகு பிரதான இருப்பிலிருந்து ரூ. {amount} தரவு பயன்படுத்தப்பட்டது."
        ),
    },
}

#: Outcome -> language -> what happens next.
_NEXT: dict[Outcome, dict[Language, str]] = {
    Outcome.AUTO_FIX: {
        Language.EN: "We have put it right already - no need to do anything.",
        Language.SI: "අපි දැනටමත් එය නිවැරදි කර ඇත - ඔබට කිසිවක් කිරීමට අවශ්‍ය නැත.",
        Language.TA: "நாங்கள் ஏற்கெனவே சரிசெய்துவிட்டோம் - நீங்கள் எதுவும் செய்ய வேண்டியதில்லை.",
    },
    Outcome.ONE_TAP_FIX: {
        Language.EN: "Confirm below and we will put it right straight away.",
        Language.SI: "පහතින් තහවුරු කරන්න, අපි එය වහාම නිවැරදි කරන්නෙමු.",
        Language.TA: "கீழே உறுதிப்படுத்தினால் உடனடியாக சரிசெய்வோம்.",
    },
    Outcome.STAFF_APPROVAL: {
        Language.EN: "A Hutch supervisor is checking this before anything moves.",
        Language.SI: "කිසිවක් වෙනස් වීමට පෙර Hutch අධීක්ෂකවරයෙකු මෙය පරීක්ෂා කරයි.",
        Language.TA: "எதுவும் மாறுவதற்கு முன் Hutch மேற்பார்வையாளர் இதைச் சரிபார்க்கிறார்.",
    },
    Outcome.EXPLAIN_ONLY: {
        Language.EN: "Nothing was charged wrongly, so there is nothing to refund.",
        Language.SI: "වැරදි ලෙස අය කර නැති බැවින් ආපසු ගෙවීමට කිසිවක් නැත.",
        Language.TA: "தவறாக எதுவும் வசூலிக்கப்படவில்லை, எனவே திரும்பப் பெற எதுவும் இல்லை.",
    },
    Outcome.HANDOFF: {
        Language.EN: (
            "A person will pick this up with the full trail - you will not need to repeat anything."
        ),
        Language.SI: "සම්පූර්ණ තොරතුරු සමඟ පුද්ගලයෙකු මෙය බාර ගනී - ඔබට නැවත කිසිවක් කීමට අවශ්‍ය නැත.",
        Language.TA: "முழு விவரங்களுடன் ஒருவர் இதை எடுத்துக்கொள்வார் - நீங்கள் மீண்டும் எதுவும் சொல்ல வேண்டியதில்லை.",
    },
}

_UNKNOWN: dict[Language, str] = {
    Language.EN: "We could not confirm a single cause from the records we hold.",
    Language.SI: "අප සතුව ඇති වාර්තා අනුව එක් හේතුවක් තහවුරු කළ නොහැකි විය.",
    Language.TA: "எங்களிடம் உள்ள பதிவுகளில் இருந்து ஒரு காரணத்தை உறுதிப்படுத்த முடியவில்லை.",
}


def explanation(
    *,
    rule_id: str | None,
    outcome: Outcome,
    amount: Decimal | None,
    language: Language = Language.EN,
) -> str:
    """Build an approved explanation. Costs nothing and cannot hallucinate."""
    parts: list[str] = []

    cause = _CAUSE.get(rule_id or "", {}).get(language) if rule_id else None
    if cause is None:
        parts.append(_UNKNOWN[language])
    else:
        parts.append(cause.format(amount=f"{amount:.2f}" if amount is not None else " - "))

    following = _NEXT.get(outcome, {}).get(language)
    if following:
        parts.append(following)
    return " ".join(parts)


def has_template(rule_id: str | None, language: Language) -> bool:
    return bool(rule_id) and language in _CAUSE.get(rule_id or "", {})
