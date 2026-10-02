"""How-to knowledge articles for the non-account Clarity path."""

from __future__ import annotations

from typing import Any

KNOWLEDGE_ARTICLES: list[dict[str, Any]] = [
    {
        "article_id": "KB-ESIM",
        "title": "Convert or replace a SIM with an eSIM",
        "body": (
            "You can convert a physical Hutch SIM to an eSIM, or replace a lost eSIM, "
            "from the Hutch app or at a Hutch Experience Centre.\n\n"
            "1. Sign in with the number you want to convert.\n"
            "2. Open More → SIM / eSIM → Convert to eSIM (or Replace eSIM).\n"
            "3. Confirm with the OTP sent to that number.\n"
            "4. Scan the QR code on the phone that will hold the eSIM.\n"
            "5. Keep the old SIM until the new eSIM shows Active.\n\n"
            "Your number, balance and packs move with the eSIM. Packs do not restart. "
            "If conversion fails, keep using the physical SIM and visit a Hutch centre "
            "with your NIC."
        ),
        "keywords": [
            "esim",
            "e-sim",
            "convert",
            "replace",
            "sim",
            "qr",
            "how",
            "activate esim",
        ],
        "language": "en",
    },
    {
        "article_id": "KB-ACTIVATE-PACK",
        "title": "Activate a data pack",
        "body": (
            "To activate a pack on this number:\n\n"
            "1. Open Packages in the Hutch app.\n"
            "2. Choose Anytime, Unlimited, Social, Work or Combo.\n"
            "3. Confirm the price will debit your main balance.\n"
            "4. Wait for the confirmation SMS. The pack shows under Usage.\n\n"
            "If activation fails, your balance is not kept for that attempt. Try again "
            "or ask Clarity why a pack did not activate — that is an account check, "
            "not this how-to."
        ),
        "keywords": [
            "activate",
            "pack",
            "package",
            "buy",
            "purchase",
            "data",
            "how",
            "anytime",
        ],
        "language": "en",
    },
    {
        "article_id": "KB-CHECK-BALANCE",
        "title": "Check your balance",
        "body": (
            "Your main balance is on Home. Dial *#100# or open the Hutch app. "
            "Reloads from banks can take a few minutes to credit. If money left your "
            "bank but the balance did not rise, ask Clarity — that is an account "
            "investigation, not this article."
        ),
        "keywords": ["balance", "check", "reload", "credit", "how", "main balance"],
        "language": "en",
    },
    {
        "article_id": "KB-FUP",
        "title": "What fair-use (FUP) means",
        "body": (
            "Unlimited and large data packs include a fair-use cap shown at purchase. "
            "After you use that volume, speed drops to the stated rate — data is not "
            "cut off. The cap and after-cap speed are on the pack screen before you buy. "
            "If your data is slow and you want to know whether you hit the cap on this "
            "number, ask Clarity to check your account."
        ),
        "keywords": [
            "fup",
            "fair",
            "use",
            "cap",
            "slow",
            "throttle",
            "unlimited",
            "speed",
        ],
        "language": "en",
    },
    {
        "article_id": "KB-VAS",
        "title": "Manage subscriptions (VAS)",
        "body": (
            "Paid daily or monthly services (games, news, tones) appear under "
            "Subscriptions. You can cancel any active one there. Hutch must hold OTP "
            "or second-confirmation evidence for a VAS charge. If you see a charge "
            "you never confirmed, ask Clarity to check this number — that opens an "
            "account case, not this how-to alone."
        ),
        "keywords": [
            "vas",
            "subscription",
            "cancel",
            "gamehub",
            "otp",
            "manage",
            "daily",
        ],
        "language": "en",
    },
]


def classify_intent(question: str) -> str:
    """Return account | knowledge | both for a customer question."""
    text = question.lower()
    knowledge_hints = (
        "how do i",
        "how to",
        "how can i",
        "convert",
        "esim",
        "e-sim",
        "activate a pack",
        "activate pack",
        "what is fup",
        "what does fup",
        "fair use",
        "fair-use",
        "manage subscription",
        "check balance",
        "කොහොමද",
        "எப்படி",
    )
    account_hints = (
        "why",
        "charged",
        "charge",
        "deduct",
        "missing",
        "twice",
        "duplicate",
        "slow",
        "balance change",
        "my data",
        "was i",
        "subscription charge",
        "refund",
        "ඇයි",
        "ஏன்",
        "මන්ද",
        "மெது",
    )
    is_knowledge = any(hint in text for hint in knowledge_hints)
    is_account = any(hint in text for hint in account_hints)
    if is_knowledge and is_account:
        return "both"
    if is_knowledge:
        return "knowledge"
    return "account"
