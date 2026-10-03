# conversation - MODULE.md

| Field | Value |
|---|---|
| Kind | module |
| Layer | L4 domain (`clarity.modules.conversation`) |
| Deployable | `clarity-api` today (modular monolith) |
| Owner | TBD |
| Status | built (`lite` and `full`); stateful turn pipeline added by C01 (issue #19) on 2026-10-03 |
| Files | `intents.py`, `intent_routes.py`, `service.py`, `suggestions.py`, `orchestrator.py`, `state.py`, `verify.py`, `public.py` |

## 1. Purpose
Customer chat for the immersive "Clarity chat". Two paths:

- **Stateless** (`handle_turn`): one message in, one answer out. Keeps nothing. Used where there is no case to attach a conversation to.
- **Stateful** (`ConversationOrchestrator`): the turn pipeline of plan 22 section 4, with conversation state per case. Guards the input, masks personal data, classifies intent with deterministic keyword rules, checks for handoff on every turn, steps the flow, composes from an approved template, verifies the result against FACTS, and records the turn.

No language model decides anything here. Intake is keyword rules; composition is templates. The `extract` and `fast-text` roles are optional assists behind the AI gateway (plan 19 section 4), and the `guard` role can only ever add a refusal.

## 2. Public surface (`public.py`)
`ConversationOrchestrator`, `ConversationState`, `ConversationStore`, `FlowEngine`, `FlowOutcome`, `Turn`, `TurnRecord`, `VerifierResult`, `verify_reply`, `CONVERSATION_STATES`, `DEFAULT_TTL`, `MAX_MESSAGE_CHARS`, `REFUSALS`, `build_suggestions`, `extract_intake`, `handle_turn`, `signals_from_snapshot`, `suggest_for_snapshot`.

## 3. Used by
`clarity.interfaces.http` (`POST /v1/conversation/turn`, `/v1/clarity/route`, suggestions) and `clarity.app.container`, which constructs the orchestrator.

## 4. Depends on
| Package | Through |
|---|---|
| `clarity.ai` | `guard` (`inspect`, `Guard`) and `pii` (`Masker`, `find_forbidden`) |
| `clarity.platform.audit` | `AuditLedger`, `AuditEventType.TURN_RECORDED` |
| `clarity.platform.messaging` | `Event`, `outbox_in` |
| `clarity.platform.persistence` | `Repository`, `UnitOfWorkFactory`, `MemoryStore` |
| `clarity.contracts.events` | `ConversationTurnCompletedV1` |

No synchronous call to another module (`"conversation": set()` in `tests/architecture/test_module_dependencies.py`). The flow engine is a protocol the composition root supplies, so adding flows in C02 does not add a module edge.

## 5. Data owned
`conversation.states`: short-term state per **case**, TTL 24 hours. One PostgreSQL schema and role in the `full` profile (`conversation`), in-memory in `lite`.

Holds flow, state, slots, language, last proposal id, turn counter and the channels the conversation has been held on. Holds **no message history and no reply text**: plan 22 section 9 allows no long-term memory of conversation content, and there is deliberately nowhere in `ConversationState` to put a transcript (asserted by `test_state_carries_no_message_text_by_shape`).

## 6. Invariants
- Customer text is a hint, never evidence (I2). Intake selects a route and fills slots; causes and amounts still come from rule packs and the decision policy.
- Handoff keywords always win, so a customer asking for a person is never kept in automation.
- Nothing unmasked is stored. The masker runs before intake, so slots and state hold masked text only.
- An OTP, card number, CVV or PIN **refuses** the turn. Nothing of that message is stored.
- An injection **neutralises** the turn rather than refusing it: the held text does not get to choose an intent, a safe template answers, and the codes are audited. The controls that stop money moving are elsewhere (I1, ADR-0007).
- A reply that fails verification is not sent. The customer gets the approved fallback and the case goes to a person.
- Conversation state is case scoped, so the route that writes it is subject bound (I9).
- `last_proposal_id` is a pointer, not a permission. Executing still needs a confirmation token minted outside this path (ADR-0007).
- Time comes from the injected clock (I11): every entry point takes `now`.

## 7. Migration status (enterprise-plan 21)
Keyword rules in code. Target: intents and phrases as versioned content under the policy lifecycle (plan 20), and the `extract` role as an optional assist with the keyword rules as fallback (C04, issue #23).

The TTL is a module constant (`DEFAULT_TTL`), injectable per store. It decides how long a chat resumes, not an amount or an eligibility, so it is not a policy artefact today; if HUTCH wants it under the policy lifecycle it becomes a resolved value and the constant becomes the fallback.

**Seams not yet filled:**
- `FlowEngine` is a protocol with no implementation. C02 (#21) brings the flow registry and the seven flows; until then every turn stays in `none/start` and the audit says so.
- `FlowOutcome.chunk_ids` and `citations` are carried and audited but nothing produces them yet. K01-K03 (#31-#33) bring retrieval.
- No model composes a reply yet, so `model_role` and `model` are recorded as `None` rather than omitted.

## 8. Events
| Event | Direction | Notes |
|---|---|---|
| `conversation.turn.completed@v1` | produced | One finished turn. Carries what the assistant did, never what was said: no message text, no reply. Consumers: insights, audit (plan 21 section 11.3). |

## 9. Tests
- `backend/tests/unit/test_conversation_chat.py` - intake, routing, suggestions
- `backend/tests/unit/test_conversation_audit.py` - the turn audit (C01 acceptance 2), guard wiring, refusals, the published event
- `backend/tests/unit/test_conversation_state.py` - TTL behaviour and the reply verifier
- `backend/tests/acceptance/test_assistant.py` - cross-channel continuity (C01 acceptance 1) and subject binding

## 10. Change history
| Date | Devlog entry | Summary |
|---|---|---|
| 2026-10-02 | `docs/devlog/2026/2026-10-02-kodee-clarity-chat.md` | Built by the team in the old layout |
| 2026-10-02 | `docs/devlog/2026/2026-10-02-R1-dev-merge.md` | Ported into `clarity.modules.conversation` with a public surface |
| 2026-10-03 | `docs/devlog/2026/2026-10-03-C01-conversation-orchestrator.md` | Stateful turn pipeline, state store with TTL, verifier, turn audit and `conversation.turn.completed@v1` |
