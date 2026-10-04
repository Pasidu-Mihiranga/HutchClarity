"""Public surface of the conversation module.

Other modules, the composition root and the interfaces import from here only
(enforced by tests/architecture/test_module_boundaries.py).

`handle_turn` is the stateless single-shot path and stays for the chat routes
that already use it. `ConversationOrchestrator` is the stateful pipeline added
by C01: it keeps conversation state per case, so the same case continues on any
channel, and it records every turn.
"""

from __future__ import annotations

from clarity.modules.conversation.agent import (
    MAX_TOOL_CALLS_PER_TURN,
    AgentLimits,
    AgentPlan,
    AgentTrace,
    BoundedAgent,
    Planner,
    PlannerReply,
    PlanRejected,
    RejectionCode,
    validate_plan,
)
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
from clarity.modules.conversation.intake import (
    ASSIST_BELOW,
    IntakeAssist,
    Rule,
    detect_language,
    reply_language,
)
from clarity.modules.conversation.intents import Intent, Route
from clarity.modules.conversation.orchestrator import (
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
    MAX_MESSAGE_CHARS,
    REFUSALS,
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
    "ASSIST_BELOW",
    "CONVERSATION_STATES",
    "DEFAULT_TTL",
    "MAX_MESSAGE_CHARS",
    "MAX_TOOL_CALLS_PER_TURN",
    "REFUSALS",
    "AgentLimits",
    "AgentPlan",
    "AgentTrace",
    "BoundedAgent",
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
    "IntakeAssist",
    "Intent",
    "PlanRejected",
    "Planner",
    "PlannerReply",
    "RejectionCode",
    "Route",
    "Rule",
    "ToolCaller",
    "ToolNotAllowed",
    "Turn",
    "TurnRecord",
    "VerifierResult",
    "build_suggestions",
    "detect_language",
    "extract_intake",
    "handle_turn",
    "load_flow",
    "load_flows",
    "reply_language",
    "signals_from_snapshot",
    "suggest_for_snapshot",
    "validate_plan",
    "verify_reply",
]
