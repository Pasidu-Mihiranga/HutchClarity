"""Conversation intent taxonomy and context-aware suggestions."""

from __future__ import annotations

from clarity.modules.conversation.domain.intents import Intent
from clarity.modules.conversation.domain.service import extract_intake, handle_turn
from clarity.modules.conversation.domain.suggestions import build_suggestions, signals_from_snapshot


def test_balance_phrases_same_intent_en_si() -> None:
    samples = [
        "What happened to my balance?",
        "Why did my money go?",
        "Why was Rs 49 deducted?",
        "Mage balance adu wela ai?",
        "I didn't buy anything but balance decreased.",
        "මගේ බැලන්ස් අඩු වුණේ ඇයි?",
    ]
    intents = {extract_intake(text).intent for text in samples}
    assert Intent.BALANCE_DEDUCTION_QUERY.value in intents or Intent.UNEXPECTED_CHARGE.value in intents
    # All should be account-routed money intents
    for text in samples:
        intake = extract_intake(text)
        assert intake.route in {"account", "both"}
        assert intake.client_intent in {"balance", "sub", "twice", "missing", "slow"}


def test_esim_is_knowledge() -> None:
    intake = extract_intake("How do I convert to eSIM?")
    assert intake.intent == Intent.ESIM_HELP.value
    assert intake.route == "knowledge"


def test_handoff_intent() -> None:
    turn = handle_turn("I want to speak to a human agent")
    assert turn.intake.intent == Intent.HANDOFF.value
    assert turn.handoff["handoff"] is True
    assert turn.intake.route == "handoff"


def test_suggestions_fup_and_vas() -> None:
    quiet = build_suggestions({}, limit=6)
    assert 4 <= len(quiet["suggestions"]) <= 6

    fup = build_suggestions({"fup_pct": 95}, limit=6)
    ids = {chip["id"] for chip in fup["suggestions"]}
    assert "slow" in ids or "fup" in ids

    vas = build_suggestions(
        {"unusual_vas": True, "vas_amount_lkr": "49.00", "vas_product": "GameZone Daily"},
        limit=6,
    )
    labels = " ".join(chip.get("label") or chip.get("i18n_key") or "" for chip in vas["suggestions"])
    assert "49" in labels or any(c["id"] == "unexpected" for c in vas["suggestions"])


def test_signals_from_snapshot_dilani_like() -> None:
    snapshot = {
        "pack": {"used_pct": 40},
        "subscriptions": [{"active": True, "consent": False, "name": "GameZone Daily"}],
        "activity": [{"type": "vas_charge", "amount_lkr": "49.00", "detail": "GameZone Daily"}],
    }
    signals = signals_from_snapshot(snapshot)
    assert signals.get("unusual_vas") is True
    chips = build_suggestions(signals, limit=6)
    assert any(c["id"] in {"unexpected", "vas", "balance"} for c in chips["suggestions"])


def test_turn_returns_follow_ups() -> None:
    turn = handle_turn("Why was I charged for GameZone?", intent_override=Intent.UNEXPECTED_CHARGE.value)
    assert turn.follow_ups
    assert turn.intake.client_intent == "sub"
