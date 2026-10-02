"""Public facade for the conversation module."""

from __future__ import annotations

from clarity.modules.conversation.domain.service import (
    IntakeResult,
    TurnResult,
    check_handoff,
    compose_reply,
    detect_language,
    extract_intake,
    handle_turn,
)

__all__ = [
    "IntakeResult",
    "TurnResult",
    "check_handoff",
    "compose_reply",
    "detect_language",
    "extract_intake",
    "handle_turn",
]
