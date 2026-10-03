# conversation - MODULE.md

| Field | Value |
|---|---|
| Kind | module |
| Layer | L4 domain (`clarity.modules.conversation`) |
| Deployable | `clarity-api` today (modular monolith) |
| Owner | TBD |
| Status | built (`lite` and `full`); turn pipeline C01 (#19), flow registry and seven flows C02 (#21), both 2026-10-03 |
| Files | `intents.py`, `intent_routes.py`, `service.py`, `suggestions.py`, `orchestrator.py`, `state.py`, `verify.py`, `flows.py`, `router.py`, `public.py` |

## 1. Purpose
Customer chat for the immersive "Clarity chat". Two paths:

- **Stateless** (`handle_turn`): one message in, one answer out. Keeps nothing. Used where there is no case to attach a conversation to.
- **Stateful** (`ConversationOrchestrator`): the turn pipeline of plan 22 section 4, with conversation state per case. Guards the input, masks personal data, classifies intent with deterministic keyword rules, checks for handoff on every turn, steps the flow, composes from an approved template, verifies the result against FACTS, and records the turn.

No language model decides anything here. Intake is keyword rules; composition is templates. The `extract` and `fast-text` roles are optional assists behind the AI gateway (plan 19 section 4), and the `guard` role can only ever add a refusal.

## 2. Public surface (`public.py`)
`ConversationOrchestrator`, `ConversationState`, `ConversationStore`, `Turn`, `TurnRecord`, `VerifierResult`, `verify_reply`, `CONVERSATION_STATES`, `DEFAULT_TTL`, `MAX_MESSAGE_CHARS`, `REFUSALS`, `build_suggestions`, `extract_intake`, `handle_turn`, `signals_from_snapshot`, `suggest_for_snapshot`.

Flows (C02): `Flow`, `FlowState`, `FlowStatus`, `FlowRegistry`, `FlowRouter`, `FlowEngine`, `FlowOutcome`, `Condition`, `FlowError`, `FlowNotFound`, `FlowLooped`, `ToolCaller`, `ToolNotAllowed`, `load_flow`, `load_flows`.

**Note:** `FlowEngine.step` takes `(state, intake, facts)`. It took `(state, intake)` when C01 declared it with no implementation; C02 added the facts argument, because conditions are evaluated against the case's own records.

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

## 5a. Flows (C02)

Seven flows, one per journey in plan 22 section 5, each claiming a disjoint set of entry intents. All 19 intents are claimed exactly once, enforced by a test: an unclaimed intent is a customer with no journey, and two flows claiming one intent would be a tie broken by filename.

| Flow | Entry intents | May propose |
|---|---|---|
| `DISPUTE_CHARGE` | UNEXPECTED_CHARGE, BALANCE_DEDUCTION_QUERY, DOUBLE_CHARGE, RELOAD_MISSING, VAS_SUBSCRIPTIONS | yes |
| `KNOWLEDGE_QA` | FUP_QUERY, PACK_EXPIRY, ESIM_HELP, PACK_RECOMMEND, FALLBACK | no |
| `ACCOUNT_AND_POLICY` | PACK_NOT_WORKING, PACK_MISSING, PACK_ACTIVATE | no |
| `SAFEGUARD_SETUP` | PREVENT_CHARGES | yes |
| `CASE_STATUS` | CASE_STATUS, REFUND_STATUS | no |
| `NETWORK_STATUS` | NETWORK_STATUS, DATA_SLOW | no |
| `HANDOFF` | HANDOFF | no |

The DSL field for edges is `transitions`, not `on`: in YAML 1.1 a bare `on` key parses as the boolean `True`, the same trap that bites GitHub Actions workflows.

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
- A state may only use the tools its flow declares. Checked when the file loads and again at call time, because a validated list nothing consults is documentation.
- Only `DISPUTE_CHARGE` and `SAFEGUARD_SETUP` may propose. A knowledge answer or a status check reaching `propose_action` would be a path from a question to a money movement (test-enforced).
- Every flow can reach a person: `request_handoff` is in every allowlist, because a journey with no way out to a human is a trap (I2).
- Conditions are a closed vocabulary, never an expression. A flow file is content written by people not reviewing it as code.
- A flow in progress is not abandoned by a vague turn: FALLBACK is an entry intent for `KNOWLEDGE_QA`, so taking the claim at face value would drop a mid-dispute customer into a knowledge answer.
- A reply only ever quotes a figure from FACTS. `compose_reply` used to fall back to the amount in the customer's own text, which read as agreement to a number nothing decided.

## 7. Migration status (enterprise-plan 21)
Keyword rules in code. Target: intents and phrases as versioned content under the policy lifecycle (plan 20), and the `extract` role as an optional assist with the keyword rules as fallback (C04, issue #23).

The TTL is a module constant (`DEFAULT_TTL`), injectable per store. It decides how long a chat resumes, not an amount or an eligibility, so it is not a policy artefact today; if HUTCH wants it under the policy lifecycle it becomes a resolved value and the constant becomes the fallback.

Flows are policy content: versioned YAML in `config/flows/`, loaded strictly, with `flow_hash` on each so a trail can name exact logic. They are not yet published through the governance change lifecycle (plan 20, kinds K4/K6); that is the remaining half of the M-GOV dependency.

**Seams not yet filled:**
- `FlowOutcome.chunk_ids` and `citations` are carried, audited and verified but nothing produces them yet. K01-K03 (#31-#33) bring retrieval, so `KNOWLEDGE_QA` currently always takes its `offer_person` exit.
- `agentic: true` is declared and validated on two states but no planner honours it. C03 (#22) brings the bounded agent step; until then an agentic state behaves exactly like a deterministic one.
- `FlowToolAdapter` implements `propose_action`, `get_network_status` and `get_trust_receipt`. The other tools a flow names raise `ToolUnavailable` rather than returning nothing, so a state reaching for one fails loudly.
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
- `backend/tests/unit/test_flow_registry.py` - flow DSL validation (C02 acceptance 2)
- `backend/tests/acceptance/test_flows.py` - scripted conversations per flow (C02 acceptance 1)

## 10. Change history
| Date | Devlog entry | Summary |
|---|---|---|
| 2026-10-02 | `docs/devlog/2026/2026-10-02-kodee-clarity-chat.md` | Built by the team in the old layout |
| 2026-10-02 | `docs/devlog/2026/2026-10-02-R1-dev-merge.md` | Ported into `clarity.modules.conversation` with a public surface |
| 2026-10-03 | `docs/devlog/2026/2026-10-03-C01-conversation-orchestrator.md` | Stateful turn pipeline, state store with TTL, verifier, turn audit and `conversation.turn.completed@v1` |
| 2026-10-03 | `docs/devlog/2026/2026-10-03-C02-flow-registry.md` | Flow DSL as policy content, the seven flows, the router, and the tool allowlist |
