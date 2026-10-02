"""Public surface of the conversation module.

Other modules, the composition root and the interfaces import from here only
(enforced by tests/architecture/test_module_boundaries.py).
"""

from __future__ import annotations

from clarity.modules.conversation.service import (
    extract_intake,
    handle_turn,
    suggest_for_snapshot,
)
from clarity.modules.conversation.suggestions import build_suggestions, signals_from_snapshot

__all__ = [
    "build_suggestions",
    "extract_intake",
    "handle_turn",
    "signals_from_snapshot",
    "suggest_for_snapshot",
]
