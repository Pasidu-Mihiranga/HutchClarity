# 2026-10-03 - C02 - The flow DSL, the seven flows, and three things the tests caught

| Field | Value |
|---|---|
| Author(s) | Thanoj Buddhima; agent: Claude Code (Opus 5) |
| Work package | C02 (`docs/backlog/issues/C02-flow-registry-and-the-seven-flows.md`, #21), Wave 3 |
| PR / commit | not committed at time of writing |
| Units touched | `modules.conversation`, `app` (`flow_tools`, `container`, `settings`, `collections`), `interfaces.http`, `config/flows` |

## What changed

- **`conversation/flows.py`**: the flow DSL. `Flow`, `FlowState`, `Transition`,
  a closed `Condition` vocabulary, `FlowRegistry`, and `load_flow`/`load_flows`
  mirroring the rule-pack loader.
- **`config/flows/*.yaml`**: the seven flows from plan 22 section 5, as policy
  content rather than code.
- **`conversation/router.py`**: `FlowRouter`, which fills the `FlowEngine` seam
  C01 left. Evaluates the current state's transitions and moves on.
- **`app/flow_tools.py`**: `FlowToolAdapter`, the tool surface a flow may reach,
  built over the narrow MCP view.
- **`/v1/conversation/turn`**: now derives the turn's facts from the case record
  rather than trusting the request.
- `CLARITY_FLOWS_DIR`, `conversation.states` registered in `ALL_COLLECTIONS`.

## Why

Issue #21. There were no multi-step flows: C01 built the pipeline and left the
flow step as a protocol with no implementation.

## Decisions made

1. **Flows are files, validated on load.** The allowlist is the security
   surface of a flow (it is what stops a knowledge answer reaching
   `propose_action`), so a flow naming a tool outside its own allowlist is
   refused at publication, not discovered when a customer reaches that state.
2. **Conditions are a closed vocabulary, never an expression.** A flow file is
   policy content written by people who are not reviewing it as code. An
   evaluated expression in it would be both a correctness risk and an injection
   surface. An unknown condition fails the load.
3. **The allowlist is enforced twice.** Validated in the file and checked again
   in `FlowRouter.call_tool`, because a validated list nothing consults is
   documentation. C03's bounded agent step routes through the same entry point.
4. **The router proposes and cannot execute**, and that is a property of the
   surface rather than of the router's behaviour: `FlowToolAdapter` is built
   over `MCPCaseView`, which the import contract keeps away from the tool
   layer's capability modules. A future change trying to give a flow an
   execution path would have to break an import contract to do it.
5. **A refusal from the tool layer is an answer, not a fault.** A flow reaches
   a proposing state whenever its conditions hold, and the tool layer is still
   the authority on whether a plan may exist. `EXPLAIN_ONLY` has no allowed
   action and a safeguard can be chosen before a case is evaluated, so the
   adapter catches the typed refusal and the flow stays where it is. Letting it
   surface ended the customer's conversation with a 409.
6. **One intent, one flow.** The registry refuses two flows claiming the same
   entry intent, because the alternative is a tie broken by file order: which
   journey a customer gets would depend on a filename. A test asserts the other
   half, that all 19 intents are claimed.
7. **Unreachable states are refused.** Almost always a renamed transition
   target, and invisible until the journey that used to pass through it stops
   working. This caught a bug in my own `SAFEGUARD_SETUP` file (below).
8. **The DSL field is `transitions`, not `on`.** See below.

## Three things the tests caught

**1. `on:` is a YAML boolean.** The first version of the DSL used `on:` for a
state's edges. In YAML 1.1, which PyYAML implements, a bare `on` key parses as
the boolean `True`, so every state's transitions arrived under a key of `True`
and the flow had no edges at all. This is the same trap that bites GitHub
Actions workflows. `extra="forbid"` on the model turned it into a loud refusal
rather than seven flows that loaded fine and went nowhere, but the field is now
named out of the way so nobody rediscovers it. A test pins the behaviour.

**2. A vague follow-up pulled customers out of their dispute.** `FALLBACK` is an
entry intent for `KNOWLEDGE_QA` (plan 22 section 5 lists it). Mid dispute, "has
it been sorted?" classifies as FALLBACK, so the first router happily switched
the customer from `DISPUTE_CHARGE` into a knowledge answer and lost the journey.
The acceptance test for cross-channel continuity failed on it, which is the test
earning its place: the symptom was a flow name changing between two turns.

Fixed with three ordered rules: nothing running takes the claim; **an active
flow is not abandoned by a vague or low-confidence turn**; a flow already in a
terminal state does not trap anyone. A confident switch still works, which has
its own test, because "never switch" would trap someone who changed the subject.

**3. The reply quoted the customer's own figure.** `compose_reply` read
`facts.get("amount_lkr") or intake.slots.get("amount_lkr")`. The fallback meant
that before a case was evaluated, "why was LKR 49 deducted" came back as "...
(LKR 49)" with the 49 taken from the customer's own sentence and presented as
Clarity's finding. A05 flagged that an attacker-supplied amount lands in the
intake slots; this is where it surfaced. The C01 turn verifier is what caught
it, refusing the reply for carrying a figure outside FACTS, which is exactly
what it was built for. Now only FACTS can supply an amount.

## The hole in my own test

The first version of `test_a_client_supplied_figure_...` passed with the fact
filter removed, so it was proving nothing. Two reasons, both worth recording.
It used an intent whose template never appends an amount, and it ran after a
plan had been proposed, at which point the plan's real amount overwrites
anything the client sent. So the path was shielded by accident rather than by
the filter.

Retargeted to a turn before evaluation, where nothing else supplies an amount.
Confirmed by probe: with the filter removed that test now fails, along with the
forged-receipt one.

## Contract and plan notes

- **No `/v1` contract change.** `POST /v1/conversation/turn` already returned an
  untyped object and already took `case_id`; the response gained keys, which is
  additive. The OpenAPI snapshot is unchanged and `make contracts-check` passes.
- **Plan 22 section 5 names a tool that does not exist.** `get_pack_details` is
  listed for `KNOWLEDGE_QA` and is not in the MCP tool registry. The flows do
  not use it, and `test_every_tool_a_flow_names_is_a_real_mcp_tool` checks the
  flows against the real registry so an invented tool cannot creep in. Raising
  it here rather than inventing the tool: the plan should either drop it or A04
  should add it.
- **Plan 22 section 5 lists a `cancelled` exit for `SAFEGUARD_SETUP`.** Left
  out, because nothing can reach it: there is no decline signal in the system,
  so the state would be dead and the registry refuses unreachable states. The
  flow file says so. When a decline path exists the flow gains the condition.
- **Flows are not yet under the governance change lifecycle.** They are
  versioned files with a `flow_hash`, loaded strictly, but publishing them
  through `PolicyGovernance` (plan 20, kinds K4/K6) is the remaining half of the
  M-GOV dependency and is not in this change.

## Docs updated

- This devlog, `backend/src/clarity/modules/conversation/MODULE.md`,
  `CHANGELOG.md`, `ARCHITECTURE.md`, `.env.example` (`CLARITY_FLOWS_DIR`),
  `plan.md` (#21 ticked).
- No new module and no new module edge: `"conversation": set()` still holds,
  because the tool surface is a protocol the composition root supplies.
- No new event.

## Tests run

- `make check`: **1467 passed, 527 skipped** (1427 before C02, so +40).
- `make contracts-check`: snapshot and SDK unchanged.
- `make test-full` with all five services: **1106 passed, 1 failed**, and the
  failure is not mine. `test_bus_parity.py::test_a_blocked_event_clears_once_the_handler_recovers[kafka]`
  failed in two of three full runs and passed 26 of 26 times in isolation
  (two runs of the whole kafka selection). The test publishes, drains expecting
  one failure, then drains again expecting redelivery; under full-suite load
  the second drain can return before the broker has redelivered. The messaging
  bus and this test have no local changes in C01 or C02 (`git diff` over
  `platform/messaging/` is empty) and were last touched in `0081ddc`. It is a
  pre-existing flake in the Kafka driver's drain timing and it deserves its own
  issue rather than a fix smuggled into a conversation change.
- Acceptance 1: `test_the_dispute_charge_script_for_dilani_ends_with_a_verified_receipt`,
  Sinhala, no model, HTTP only, receipt verifies.
- Acceptance 2: `test_a_state_using_a_tool_outside_the_allowlist_is_refused`.
- Non-vacuity, three probes, each failing exactly the tests that should catch it:
  removing the allowlist validator fails the two acceptance-2 tests; removing
  `proposes: true` from the dispute flow fails the two that need a plan;
  removing the client fact filter fails the forged-figure and forged-receipt
  tests.
- Guards against over-broad fixes: a confident intent switch must still leave
  the flow, an explain-only case must end with no plan, and proposing twice must
  not create a second plan.

## Known gaps

- `KNOWLEDGE_QA` always takes its `offer_person` exit, because there is no
  knowledge base (K01-K03, #31-#33). Its script asserts that exit, and when
  retrieval lands the script should start reaching `answered`, which is the
  signal to extend it rather than relax it.
- `agentic: true` is declared on two states and honoured by nothing. C03 (#22).
- `FlowToolAdapter` wires three of the nine tools the flows name. The rest raise
  `ToolUnavailable` rather than returning nothing.
- `MIN_SWITCH_CONFIDENCE` is a module constant, like `check_handoff`'s existing
  threshold. It is a routing parameter, not a policy value, but if intents move
  under the policy lifecycle (C04) it should go with them.

## Next step

C03 (#22), the bounded agent step: a planner that may choose among a state's
allowed tools, with limits and a fallback. `FlowRouter.call_tool` is the entry
point it routes through, and the `agentic` markers are already in the files.
