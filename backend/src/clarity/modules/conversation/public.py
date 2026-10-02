"""Public facade for the conversation module."""

from __future__ import annotations

from clarity.modules.conversation.domain.intent_routes import (
    client_intent_for,
    follow_ups_for,
    route_for,
    routing_payload,
)
from clarity.modules.conversation.domain.intents import TOPIC_CATALOGUE, Intent, Route
from clarity.modules.conversation.domain.service import (
    IntakeResult,
    TurnResult,
    check_handoff,
    compose_reply,
    detect_language,
    extract_intake,
    handle_turn,
    suggest_for_snapshot,
)
from clarity.modules.conversation.domain.suggestions import (
    build_suggestions,
    signals_from_snapshot,
)

__all__ = [
    "TOPIC_CATALOGUE",
    "Intent",
    "IntakeResult",
    "Route",
    "TurnResult",
    "build_suggestions",
    "check_handoff",
    "client_intent_for",
    "compose_reply",
    "detect_language",
    "extract_intake",
    "follow_ups_for",
    "handle_turn",
    "route_for",
    "routing_payload",
    "signals_from_snapshot",
    "suggest_for_snapshot",
]
