"""Legacy conversation package mirrors backend chat brain."""

from __future__ import annotations

from clarity.core.conversation import extract_intake, handle_turn, suggest_for_snapshot


def test_legacy_extract_balance() -> None:
    intake = extract_intake("Why was Rs 49 deducted?")
    assert intake.route == "account"
    assert intake.intent in {"UNEXPECTED_CHARGE", "BALANCE_DEDUCTION_QUERY"}


def test_legacy_suggestions_default() -> None:
    result = suggest_for_snapshot({}, language="en", limit=6)
    assert len(result["suggestions"]) <= 6
    assert result["more_topics"]


def test_legacy_turn_route_fields() -> None:
    turn = handle_turn("Why is my data slow?")
    payload = turn.to_dict()
    assert payload["route"] in {"account", "both", "knowledge"}
    assert payload["client_intent"]
    assert "follow_ups" in payload
