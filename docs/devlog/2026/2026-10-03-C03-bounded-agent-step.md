# 2026-10-03 - C03 - The bounded agent step, and testing it with a hostile planner

| Field | Value |
|---|---|
| Author(s) | Thanoj Buddhima; agent: Claude Code (Opus 5) |
| Work package | C03 (`docs/backlog/issues/C03-bounded-agent-step-planner-with-tool-allowlist-l.md`, #22), Wave 3 |
| PR / commit | not committed at time of writing |
| Units touched | `modules.conversation` (`agent.py`, `router.py`, `orchestrator.py`, `public.py`), `app.container` |

## What changed

- **`conversation/agent.py`**: the boundary around the only agency in the
  system. `validate_plan` turns planner text into a plan a state may run or a
  typed rejection; `BoundedAgent` runs the loop inside per-turn limits;
  `AgentTrace` is what the turn audit records.
- **`conversation/router.py`**: an `agentic: true` state now consults the agent.
  Every call it makes goes through `FlowRouter.call_tool`, the same entry point
  the flow's own deterministic step uses.
- **`app/container.py`**: `_planner`, which wires the `reason` role as a planner
  only when a non-local provider is configured for it, and returns `None`
  otherwise.
- `FlowOutcome` and `TurnRecord` carry the agent's trace into the turn audit.

## Why

Issue #22. `agentic: true` was declared and validated on two states by C02 and
honoured by nothing.

## Decisions made

1. **Arguments are an allowlist, not a denylist.** Plan 22 section 6 says
   "invalid args or an `amount` field, rejected". A denylist of money-shaped
   names answers that literally and gets the default wrong: the question "may
   the planner send this field" needs a safe answer for fields nobody thought
   of, and the safe answer is no. So `TOOL_ARGS` names exactly what each of the
   nine tools accepts and everything else is refused.

   `FORBIDDEN_ARGS` is kept **on top of** that, and is therefore redundant by
   construction. It earns its place in the audit rather than in the defence: a
   planner that sent `amount_lkr` is recorded as reaching for money, not as a
   generic schema miss. A test asserts the redundancy is real, so the named
   list can never become the only thing standing between a planner and an
   amount.

2. **No tool schema accepts `case_id`.** The subject is bound by the session and
   filled in by the router from the case record. A planner that could name a
   case could read another customer's, which is the hole A04 closed in the MCP
   binding and the same one C01 closed on the turn route. The MCP server does
   require `case_id`, so the drift test between the two copies excludes it
   explicitly rather than quietly.

3. **A rejected plan ends the step, and the deterministic step runs.** Not a
   retry loop. A planner that produced an invalid plan will usually produce
   another one, and a customer waiting on a chat reply is not the place to find
   out. The rejection code is in the turn audit either way.

4. **No planner is the default, and not a degraded mode** (ADR-0009). `_planner`
   mirrors the existing `_guard_assist` down to returning `None`: a template
   cannot choose a tool, so wiring one would mean a rejected plan and a wasted
   call on every agentic state. An agentic state with no planner behaves exactly
   like a deterministic one.

5. **The planner is told only about its own state's tools.** It is never
   described a tool it cannot use, because an allowlist the model has to be
   trusted to respect is not an allowlist. The real enforcement is at call time.

6. **Limits are module constants, not policy values.** Four calls, 2000 tokens,
   8 seconds. I10 is about thresholds, caps and windows that decide an outcome
   for a subscriber; these decide how long the assistant may think.

7. **The timeout uses an injected `monotonic`, not the domain clock.** I11 is
   about replay exactness, and a duration inside one call never reaches a
   record, a decision or a replay. It is injected so a test can control it
   without sleeping.

## Testing a planner that has already lost

The acceptance tests needed a planner, and no live model may run under
`make check` (AGENTS.md section 12.3). The obvious move is a stub that behaves
well, which would have tested nothing: the claim of ADR-0030 is not that a
well-behaved model stays inside the lines, it is that a model **steered by a
customer's message** cannot get out of them.

So every planner in these tests is hostile. `CompromisedPlanner` in the safety
suite cycles through exactly what the injection set asks for: execute the
refund, propose one with an amount attached, read another customer's case, forge
a receipt. The whole injection set then runs through the stateful pipeline with
the real flows, the real tool surface and that planner, and the assertions are
on the balance, the plans and the receipts, not on any wording.

A stub standing in for a compromised model is a better test than a stub standing
in for an unavailable one, and it costs the same.

## The test that would have passed for the wrong reason

`test_the_injection_set_executes_nothing_through_the_agent` could pass simply
because no agentic state was ever reached: every injection is held by the guard,
and if the neutralised turn never got as far as a planner the test would be
measuring nothing. That is the same shape of hole as the one A05 found in the
older safety test, which looped over the injections without passing any of them
in.

Two guards. The test asserts `planner.asked > 0` and that rejections were
actually recorded. And a second test checks the path on purpose: a genuine
knowledge question reaches `KNOWLEDGE_QA.retrieve`, which is agentic, and the
planner is consulted and refused there.

## Contract and plan notes

- **No `/v1` contract change.** The turn response is an untyped object; the
  audit detail gained `agent_tools`, `agent_rejections`, `agent_fell_back` and
  `agent_tokens`. The OpenAPI snapshot is unchanged.
- **`TOOL_ARGS` is a second copy of knowledge the MCP registry already holds.**
  The registry lives in the interface layer and a module may not import it
  (I4), so the duplication is forced by the layer rule rather than chosen.
  `test_the_planner_schema_agrees_with_the_mcp_registry` imports both, which a
  test may, and fails if they drift.
- **The MCP registry's `required_args` is a required set, not an allowed set**,
  so the server does not reject extra arguments; `_propose_action` reads only
  `case_id` and `action_type` and ignores anything else. An `amount` would have
  been dropped rather than refused. The agent refuses it, which is the
  difference between a hole that is closed and a hole that happens to be
  unreachable.
- **Plan 22 section 6 lists a per-session token budget** as well as per-turn.
  Only per-turn is implemented: there is nowhere to keep a session total, since
  `ConversationState` deliberately holds no history. It belongs with the quota
  buckets in `clarity.ai` rather than here, and is noted as a gap.

## Docs updated

- This devlog, `backend/src/clarity/modules/conversation/MODULE.md`,
  `CHANGELOG.md`, `plan.md` (#22 ticked).
- No new module and no new module edge: `"conversation": set()` still holds. The
  planner is a protocol the composition root supplies, like the tool surface.
- No new event. No `.env.example` change: nothing new is configurable by
  environment, because the planner follows the `reason` role already in
  `config/ai/models.yaml`.

## Tests run

- `backend/tests/unit/test_agent_step.py`, 42 tests.
- Acceptance 1, a plan naming `confirm_and_execute`: rejected as `UNKNOWN_TOOL`,
  no tool called, deterministic step ran, code in the audit detail. The code is
  `UNKNOWN_TOOL` rather than "not allowed here" because the narrow MCP view
  never exposed it, which is the stronger answer: no state's allowlist anywhere
  could contain it.
- Acceptance 2, a plan carrying an amount: rejected as `FORBIDDEN_ARGUMENT`,
  and every name in `FORBIDDEN_ARGS` is covered individually.
- Acceptance 3, the injection set through the agent: balance unchanged, no
  receipts, planner consulted, every plan rejected.
- Non-vacuity, three probes:
  - removing the state allowlist check fails
    `test_a_real_tool_outside_this_state_is_rejected_as_not_allowed`. The safety
    suite still passes, because those particular plans are caught by the
    argument allowlist instead, which is defence in depth working rather than a
    vacuous test.
  - removing the forbidden-argument check fails 20 tests including acceptance 2.
  - removing the three limits fails all three limit tests: the agent made 10
    tool calls instead of 4.
- `make check`: see below.

## Known gaps

- **No cassette for a planner** (A02), so every planner under `make check` is a
  stub. Deliberate for the refusal tests, which want a hostile planner rather
  than a realistic one, but it means no test covers a well-formed plan from a
  real model. A recorded `reason` response would close that.
- **Per-session token budget** is not implemented (above).
- `ACCOUNT_AND_POLICY.policy_context` allows `explain_rule` and
  `search_knowledge`; `FlowToolAdapter` wires neither, so an agent choosing one
  there gets `TOOL_REFUSED` until K01-K03 (#31-#33) land retrieval.
- The planner prompt is built in code. It is customer-facing only indirectly,
  but it is the instruction half of an injection boundary, so it probably
  belongs under the policy lifecycle with the intents (plan 20) rather than in
  a string literal.

## Next step

K01 (#31), the knowledge module: source registry and governed ingestion. It is
what `search_knowledge` needs before `KNOWLEDGE_QA` can reach its `answered`
exit, and what both agentic states are currently reaching for.
