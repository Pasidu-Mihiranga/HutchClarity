# 2026-10-03 - C01 - The turn pipeline, conversation state, and the guard's first call site

| Field | Value |
|---|---|
| Author(s) | Thanoj Buddhima; agent: Claude Code (Opus 5) |
| Work package | C01 (`docs/backlog/issues/C01-conversation-orchestrator-and-state-store.md`, #19), Wave 3 |
| PR / commit | not committed at time of writing |
| Units touched | `modules.conversation`, `contracts.events`, `platform.audit`, `platform.persistence.schemas`, `interfaces.http`, `app.container` |

## What changed

- **`conversation/orchestrator.py`**: the turn pipeline from plan 22 section 4.
  Guard, mask, intake, handoff check, flow step, compose, verify, record.
- **`conversation/state.py`**: `ConversationState` and `ConversationStore`, keyed
  by **case id**, TTL 24 hours, through the unit of work so `lite` gets memory
  and `full` gets PostgreSQL unchanged.
- **`conversation/verify.py`**: the reply verifier. Figures in a reply must
  appear in FACTS; forbidden content, unauthorised promises and missing
  citations block; an English fallback warns.
- **`conversation.turn.completed@v1`**: new event, registered in the catalogue
  and in plan 21 section 11.3.
- **`AuditEventType.TURN_RECORDED`**: the turn audit entry.
- **`POST /v1/conversation/turn`**: with a `case_id` the turn now goes through
  the stateful pipeline. Without one, the stateless path answers as before.
- **`conversation.states` registered** in `app/collections.py`,
  `platform/persistence/schemas.py` (owner and customer-scoped), so the
  `full` profile gets its own PostgreSQL schema, role and row-level security.

## Why

Issue #19. Every chat turn was stateless, so a customer could not continue in
the app what they started on WhatsApp, and nothing recorded what the assistant
had done.

## Decisions made

1. **State is keyed by case, not by session or channel.** That is the whole
   cross-channel mechanism: the same case is the same conversation anywhere.
   Keying by session would make "carry on where I left off" a per-channel
   feature, which plan 22 section 9 rules out.
2. **An injection neutralises the turn; it does not refuse it.** When the guard
   holds the text, the message does not reach intake: intent becomes FALLBACK, a
   safe template answers, the codes are audited. Not every held message is an
   attack, and the controls that actually stop money moving are elsewhere
   (amounts from the decision record, a confirmation token minted outside this
   path, the tool layer refusing anything outside `allowed_actions`). The
   guard's job here is to stop the text *steering* the conversation.
3. **Forbidden content does refuse.** An OTP or card number must never be
   stored, so there is nothing to neutralise. One hard stop, approved wording.
4. **A failed verification is not sent.** The customer gets the approved
   fallback and the case goes to a person, because the alternative is quoting a
   figure nobody decided.
5. **Failures block, warnings do not.** A reply that fell back to English
   because no Sinhala template exists is worse than Sinhala and better than
   silence. Collapsing the two would mean either shipping bad figures or
   refusing to answer in the languages the templates do not cover yet.
6. **The verifier checks money-shaped figures, not every number.** Flagging
   "within 24 hours" would train everyone to ignore it, which is the only
   failure mode that matters for a check like this.
7. **Tool and chunk ids travel on `FlowOutcome`.** The flow is what chooses a
   tool or a retrieval, so they ride with the step that caused them rather than
   needing two more seams.
8. **`model_role` and `model` are recorded as `None`, not omitted.** A template
   composed this turn. "Which model said this" should always have an answer in
   the trail (ADR-0009).
9. **The TTL is a module constant, not a policy artefact.** It decides how long
   a chat resumes, not an amount or an eligibility; nothing about a decision
   changes when it moves. `OTP_TTL` sits here for the same reason. Injectable
   per store, and labelled ASSUMPTION.

## The hole I nearly shipped

Wiring the orchestrator into `POST /v1/conversation/turn` made the route write
case-scoped state. The route had no authorization at all, because until now it
was stateless and there was nothing to leak. Left as it was, **a case id alone
would have read and extended another customer's conversation** - the same shape
as the MCP binding hole A04 found, reintroduced on the HTTP side.

Fixed before the tests were written: the case path requires `CASE_READ` and runs
`authorize_case_access` against the case's own subscriber. Two tests pin it, and
removing the binding makes the stranger's request return 200 instead of 403.

A second, smaller one in the same edit: the route took `subscriber_ref` from the
request body and passed it to the audit as the actor. A caller could have chosen
who the trail blamed. It now comes from the case record.

## Also worth noting

**The guard finally has a call site.** A03 built `inspect` and `Guard`; A04 and
A05 both recorded that nothing in a request path called either. This is where it
got wired, and `test_a_held_injection_is_recorded_with_its_codes` fails if the
call is removed, so the wiring is not decorative.

## Contract change

`POST /v1/conversation/turn` now declares an optional `authorization` header.
Additive: existing unauthenticated calls still work and take the stateless path.
The response is a strict superset of the previous shape, checked by
`test_the_stateful_turn_keeps_every_field_the_stateless_one_had` rather than by
a hand-written list, so it keeps holding if the stateless shape gains a field.
Snapshot regenerated, SDK regenerated, `CHANGELOG.md` updated.

## Docs updated

- This devlog, `backend/src/clarity/modules/conversation/MODULE.md`,
  `CHANGELOG.md`, `ARCHITECTURE.md`, plan 21 section 11.3 (the new event),
  `plan.md` (#19 ticked).
- `contracts/openapi.json` and the frontend SDK regenerated on purpose.
- No `.env.example` change: no new variable.
- No `docs/modules.md` change: no new module and no new module edge
  (`"conversation": set()` still holds, because the flow engine is a protocol
  the composition root supplies).

## Tests run

- `make check`: **1427 passed, 527 skipped** (1384 before C01, so +43).
- `make test-full` with Postgres, Kafka, OPA, OpenBao and Keycloak running:
  **1107 passed, nothing skipped**. This is what caught the one thing I had
  missed: registering `conversation` in `OWNERS` without adding
  `conversation.states` to `ALL_COLLECTIONS`, so the module had an owner and a
  role but no schema. `test_every_module_owns_a_schema` failed on the real
  database, which the `lite` lane could not have told me.
- `make contracts-check`: SDK matches the regenerated schema.
- Acceptance 1: `test_a_conversation_started_on_whatsapp_continues_in_the_app`,
  black-box over `/v1`.
- Acceptance 2: `test_a_turn_records_flow_state_tools_chunks_model_and_verifier`.
- Non-vacuity, three probes, each failing exactly the test that should catch it:
  removing the subject binding fails the stranger test (and returns 200);
  stubbing the guard to allow everything fails the injection audit test; keying
  state by `case_id:channel` fails acceptance 1.
- Guard tests against over-broad fixes: an ordinary complaint must *not* be
  recorded as held, a promise *is* allowed once something really executed, and a
  different case must start a fresh conversation.

## Known gaps

- **No flow engine.** `FlowEngine` is a protocol with no implementation, so
  every turn stays in `none/start`. C02 (#21) fills it. The audit says `none`
  rather than guessing a flow.
- **No retrieval.** `chunk_ids` and `citations` are carried, audited and
  verified, but nothing produces them yet (K01-K03, #31-#33).
- **No model composes a reply.** Templates only, so the verifier's main job
  (checking a model's figures) is not yet under real load.
- **Rate limiting is not here.** Plan 22 section 4 step 1 lists "length and rate
  limits"; the length limit is implemented and refuses rather than truncating.
  Rate limiting belongs with the other quota work (`TokenBuckets` from A01 still
  declares no quotas) and is not in this change.
- The `/v1/clarity/route` endpoint still uses the stateless path. It takes no
  case id, so there is nothing to attach state to.

## Next step

C02 (#21): the flow registry and the seven flows, which fills the `FlowEngine`
seam and makes the flow and flow-state fields in the audit mean something.
