# 2026-10-04 - A4 to A8 - transcript, streaming, flow tools, chat copy, rate limiting

| Field | Value |
|---|---|
| Author(s) | Pasidu-Mihiranga; agent: Claude Opus 5 (Claude Code) |
| Work package | A4 to A8 of the demo-to-enterprise programme (plan file `quiet-gliding-nautilus`) |
| PR / commit | not committed |
| Units touched | modules.conversation, app, platform, interfaces.http, customer-web, config/policy |

## What changed

**A4 - a conversation left no record anywhere.**
- Plan 22 section 9 said "No long-term memory of conversation content" without qualification, and `state.py` cited it as the reason it keeps flow, slots and a turn counter and nothing else. The audit trail did not fill the gap: `TurnRecord` carries the masked *kinds* a message contained, never its words. So a handoff reached an agent with no context, a customer could not look back from a second device, and a dispute about what Clarity said had no document.
- New `conversation.transcripts`: one row per speaker per turn, masked text, append-only, 90-day retention applied on read, written by the orchestrator **after** the reply is composed and verified so what is stored is what the customer was actually told. Read only through `GET /v1/cases/{case_id}/transcript`, subject bound.
- **ADR-0040** records the decision and amends plan 22 section 9. The argument is that section 9 protects against content that accumulates and *steers a later answer*; a record nothing in the turn pipeline can read is not that. That argument is only worth something if it stays true, so it is a test: `tests/architecture/test_transcript_is_not_memory.py` asserts no file that decides a turn calls `for_case`, that `transcript.py` imports no deciding module, and that the write happens after verification.

**A5 - progress was animated, not reported.**
- The chat pushed a `thinking` card on a 50 ms `setTimeout` with the hardcoded English string "Checking your account...", while one request ran to completion. A hung turn looked exactly like a slow one, and the label was English whatever language the customer was using.
- `ConversationOrchestrator.handle` takes an optional `on_stage` reporter and calls it with a code from a closed `STAGES` vocabulary as each step finishes. `POST /v1/conversation/turn/stream` emits those as SSE, then one `turn` event carrying the identical payload the JSON route returns.
- **Stage events carry a code and nothing else.** That is why the orchestrator is handed a code rather than a message: a progress channel that can carry text is a second answer channel nothing verifies. A test asserts a stage event's payload is exactly `{"stage": ...}`.
- The JSON route is untouched and still what the WhatsApp gateway uses. The browser falls back to it when there is no `ReadableStream` or the stream fails before an answer.

**A6 - five of the nine flow tools were not implemented.**
- `get_case_timeline`, `get_cause_assessment`, `explain_rule`, `get_customer_safeguards` and `request_handoff` raised `ToolUnavailable`. Nothing noticed because they are only reachable through the bounded agent step, and `_planner` returns `None` with no remote provider, so no planner has ever run. The first one to run would have got `TOOL_REFUSED` for a tool its state was entitled to use.
- All five implemented over the same `MCPCaseView` the MCP server uses, returning the same shapes, because two surfaces onto one capability that disagreed about its shape would be two capabilities.
- `request_handoff` records the ask and does **not** write the desk queue. The queue is derived from the decision (`STAFF_APPROVAL` or `HANDOFF`, not yet executed), and a flow that could put a case on a staff member's screen directly would be a second, unreviewed route onto the desk.

**A7 - the chat's copy, measured instead of consolidated.**
- The chat keeps two inline catalogues outside `@clarity/i18n`: `CHAT_I18N` in `page.tsx` (61 en, 43 si, 43 ta) and `EN`/`SI`/`TA` in `ClarityMessageCard.tsx` (80 en, 13 si, 13 ta). Thirty-one keys are defined in **both**. Measured honestly: 110 unique keys, 52 with si and ta, so **58 untranslated** and the chat is 47 percent localised.
- The overlapping keys agree today, and nothing made that true or keeps it true. `frontend/apps/customer-web/test/chat-copy.test.mjs` now fails if they drift, pins the coverage baseline so a new English-only string cannot hide behind the silent fallback, and requires the A5 stage labels to exist in all three languages.
- **The 58 missing translations were not invented.** That is a translator's job, not a refactor's, and FE01 recorded that si and ta were reviewed by a native speaker. Writing 58 unreviewed customer-facing strings would quietly undo that. The consolidation into `@clarity/i18n` is still open.

**A8 - nothing limited a request rate.**
- The OTP service throttles challenges per number (TH1) and `ai/buckets.py` rations provider token spend; neither counts requests. `/v1/conversation/turn` runs masking, intake, a flow step, retrieval and composition, and could be called anonymously in a loop.
- New `platform/throttle.py`: a `RateLimiter` port with a fixed-window `MemoryRateLimiter`. Middleware in `interfaces/http/throttle.py` applies it to the anonymous, expensive routes only, keyed on the verified subscriber when there is one and the client address otherwise, with a lower whole-surface ceiling for callers with no session.
- Limits come from the new `config/policy/throttle.yaml` and are resolved per request (I10), so an activated change takes effect without a restart. The window is deliberately **not** a policy key: changing it changes what the number means, and a reviewer approving "30" should not have to look up what it is 30 of.

## Why

A4 to A8 are the rest of workstream A. A4 and A6 close gaps that make other features work (a handoff with context, a planner with its tools); A5 and A8 are the two the customer and the operator feel directly.

## Decisions made

- **ADR-0040**, as above. The alternatives are in it: leaving it, keeping it client-side, putting it in the audit trail, storing unmasked, and summarising instead.
- **A separate `/stream` route rather than content negotiation.** The JSON route is used by the WhatsApp gateway and the SDK; a route that changes shape on an `Accept` header is a contract that is hard to snapshot and easy to break.
- **The limiter fails open on an unresolvable policy key**, falling back to a declared default and logging. A limiter that fails closed turns a configuration problem into an outage.
- **The limiter verifies the bearer token itself**, because `Depends` has not run in middleware. That is the same work twice per throttled request, and it is the price of counting a signed-in customer as themselves rather than as their network address. An unverifiable token is treated as anonymous, not refused: this is a limiter, not an authenticator.
- **`request_handoff` does not write the desk queue**, as above.

## Docs updated

- [x] MODULE.md of: `conversation` (transcript collection, the record-not-memory invariant, files list, change history).
- [x] CHANGELOG.md: the two new routes, the rate limiter, the flow-tool completion and the stateless-path hardening.
- [x] Plan via CHANGES.md: v1.12, amending 22 section 9, plus the plan README version and revision table.
- [x] ADR: `docs/adr/0040-conversation-transcripts-are-records-not-memory.md` and the index row.
- [x] OpenAPI snapshot regenerated on purpose (`UPDATE_GOLDEN=1`), `contracts/openapi.json` exported, SDK schema regenerated, `caseTranscript` added to the SDK client.
- [ ] ARCHITECTURE.md / modules.md: not updated. No module changed status and no new module or dependency edge was added.
- [ ] Walkthrough: WT-02 covers the chat and should be re-verified when the browser suite is next run. Not done here.
- [ ] `.env.example`: no new environment variable. The limiter is configured through the policy store, not the environment.

## Tests

Added:
- `backend/tests/architecture/test_transcript_is_not_memory.py` (3)
- `backend/tests/unit/test_flow_tool_adapter.py` (8). Confirmed to fail 8/8 against the unpatched adapter.
- `backend/tests/unit/test_throttle.py` (10)
- `backend/tests/acceptance/test_flows.py`: 4 transcript tests and 3 streaming tests, on top of A3's 4.
- `frontend/apps/customer-web/test/chat-copy.test.mjs` (4), wired into `npm run test` through the workspace script.

Run:
- `pytest`: `2440 passed, 633 skipped in 104.40s`. No failures.
- `ruff check` and `ruff format --check`: all checks passed.
- `mypy`: success, 237 source files.
- `lint-imports`: 3 contracts kept, 0 broken.
- `npx tsc -p apps/customer-web/tsconfig.json --noEmit` and `tsc -p packages/sdk`: clean.
- `npm run build -w @clarity/customer-web`: 9 routes compiled.
- `npm run test` (frontend workspaces): 4 passed.

## Open issues / next step

1. **A4 stores customer words where Clarity previously stored none.** That is the real cost of ADR-0040, and the retention figure (90 days) is an assumption HUTCH has to confirm. The `full` profile's append-only grants need extending to the second table.
2. **A7 is half done.** The 58 untranslated keys and the consolidation into `@clarity/i18n` remain. The baseline test stops it getting worse, which is not the same as fixing it.
3. **The rate limiter is per replica.** `MemoryRateLimiter` is the `lite` driver; `full` needs a shared driver behind the same port and its parity suite, or two replicas give every caller twice the budget.
4. **The streaming route has no e2e coverage.** Three backend tests cover the protocol; the browser path (including the fallback when a stream fails midway) is untested until the Playwright suite runs.
5. The dev staff identity routes are still reachable in the `full` profile, which is what the VPS runs. Unchanged from the previous devlog and still a decision rather than a patch.
