"""Customer chat intake, suggestions and routing (demo API)."""

from clarity.core.conversation.service import (
    extract_intake,
    handle_turn,
    suggest_for_snapshot,
)
from clarity.core.conversation.suggestions import build_suggestions, signals_from_snapshot

__all__ = [
    "build_suggestions",
    "extract_intake",
    "handle_turn",
    "signals_from_snapshot",
    "suggest_for_snapshot",
]
