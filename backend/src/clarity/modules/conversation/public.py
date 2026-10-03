"""Public surface of the conversation module.

Other modules, the composition root and the interfaces import from here only
(enforced by tests/architecture/test_module_boundaries.py).

`handle_turn` is the stateless single-shot path and stays for the chat routes
that already use it. `ConversationOrchestrator` is the stateful pipeline added
by C01: it keeps conversation state per case, so the same case continues on any
channel, and it records every turn.
"""

from __future__ import annotations

from clarity.modules.conversation.flows import (
    Condition,
    Flow,
    FlowError,
    FlowNotFound,
    FlowRegistry,
    FlowState,
    FlowStatus,
    load_flow,
    load_flows,
)
from clarity.modules.conversation.orchestrator import (
    MAX_MESSAGE_CHARS,
    REFUSALS,
    ConversationOrchestrator,
    FlowEngine,
    FlowOutcome,
    Turn,
    TurnRecord,
)
from clarity.modules.conversation.router import (
    FlowLooped,
    FlowRouter,
    ToolCaller,
    ToolNotAllowed,
)
from clarity.modules.conversation.service import (
    extract_intake,
    handle_turn,
    suggest_for_snapshot,
)
from clarity.modules.conversation.state import (
    CONVERSATION_STATES,
    DEFAULT_TTL,
    ConversationState,
    ConversationStore,
)
from clarity.modules.conversation.suggestions import build_suggestions, signals_from_snapshot
from clarity.modules.conversation.verify import VerifierResult, verify_reply

__all__ = [
    "CONVERSATION_STATES",
    "DEFAULT_TTL",
    "MAX_MESSAGE_CHARS",
    "REFUSALS",
    "Condition",
    "ConversationOrchestrator",
    "ConversationState",
    "ConversationStore",
    "Flow",
    "FlowEngine",
    "FlowError",
    "FlowLooped",
    "FlowNotFound",
    "FlowOutcome",
    "FlowRegistry",
    "FlowRouter",
    "FlowState",
    "FlowStatus",
    "ToolCaller",
    "ToolNotAllowed",
    "Turn",
    "TurnRecord",
    "VerifierResult",
    "build_suggestions",
    "extract_intake",
    "handle_turn",
    "load_flow",
    "load_flows",
    "signals_from_snapshot",
    "suggest_for_snapshot",
    "verify_reply",
]
