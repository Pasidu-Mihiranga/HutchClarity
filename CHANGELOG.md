# Changelog

Notable changes to Hutch Clarity. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [Semantic Versioning](https://semver.org/). Public-surface and `/v1` contract changes are always listed.

## [Unreleased]

### Added (K01, #31)

- The `knowledge` module, previously a scaffold. Governed knowledge content:
  one record per `(source_id, version)` with a required owner, effective
  window, audience and language, and the chunks ingestion makes of it.
  `KnowledgeRegistry`, `KnowledgeSource`, `Chunk`, `Audience`, `SourceKind`,
  `ingest`, `PublicationRefused` and `IngestionRefused` are on its public
  surface.
- Effective dating. `chunks_as_of(moment, audience=...)` returns what was in
  force at that moment, so a dispute about a March charge is answered with
  March's terms. Publishing a version whose window overlaps a sibling's is
  refused, and `supersede` closes the predecessor at the successor's start in
  one unit of work.
- Audience filtering, enforced in three places: `Audience.may_read` is
  asymmetric, `chunks_as_of` requires the audience with no default, and a
  `STAFF_SOP` cannot be published as customer audience at all.
- Structure-aware ingestion: legal text per clause so a citation identifies its
  text, a catalogue entry as one chunk whatever its length, an over-long clause
  windowed with overlap while keeping its clause reference.
- A script check against the declared language, asymmetric on purpose: Sinhala
  or Tamil script declared `en` is refused, Latin script declared `si` or `ta`
  is not, because that is Singlish.
- Collections `knowledge.sources` and `knowledge.chunks`.

The registry ships empty: the corpus is HUTCH content and inventing T&C or
Gazette text would be inventing HUTCH regulations (I16).


### Added (C03, #22)

- The bounded agent step. In a flow state marked `agentic: true`, a planner may
  return `{tool, args, reason_code}` and have it run, after validation against
  the state's tool list and a per-tool argument allowlist. `BoundedAgent`,
  `validate_plan`, `AgentTrace`, `AgentLimits`, `Planner`, `PlannerReply`,
  `PlanRejected` and `RejectionCode` are on the conversation module's public
  surface.
- Per-turn limits: 4 tool calls, 2000 planner tokens, 8 seconds wall clock.
  Hitting one ends the step with what it has; it never fails the turn.
- Arguments are deny by default. No tool schema accepts a money field or
  `case_id`: an amount comes from the decision record and the subject is bound
  by the session (I1, I9). Money-shaped argument names are additionally refused
  by name so the audit records what was reached for.
- Tool results reach the next prompt delimited, labelled as untrusted data and
  length-capped, never as instructions.
- The turn audit detail gained `agent_tools`, `agent_rejections`,
  `agent_fell_back` and `agent_tokens`. No `/v1` schema change.
- `FlowRouter` takes an optional `agent`. With no model configured, which stays
  the default (ADR-0009), an agentic state behaves exactly like a deterministic
  one.


### Fixed (messaging, follow-up to C02 #21)

- `KafkaEventBus.drain` could report `is_clear` while an event that a handler
  had failed was still undelivered. `seek` is asynchronous, so the first poll
  after a blocked partition is rewound can return nothing while the retry is in
  flight, and the drain read that as "idle". A relay would have logged all
  clear with the event outstanding. The drain now checks the partition's cached
  high watermark against how far it has read and keeps polling while a rewind is
  outstanding, bounded by `rewind_grace_seconds`; a rewind that does not land is
  reported as stalled, never as clear.
- A consumer group that subscribed to a second event type could permanently lose
  events published afterwards, measured at four losses in five. Adding a topic
  rebalances the group, and the driver pinned each partition's start offset by
  seeking after `consumer.assignment()` looked settled, which it does while a
  rebalance is still in flight: the seek was discarded with the revoked
  partition and the consumer then resolved `auto.offset.reset=latest` at fetch
  time, after the publish. Offsets are now pinned in the `on_assign` rebalance
  callback, where they survive, and a partition the driver already tracked
  resumes exactly where it was. `notifications` and `proactive` both subscribe
  per event type in a loop, so both were affected in the `full` profile.
- Subscribing a second handler for a type a group already has no longer calls
  the broker: the topic list is unchanged, so the rebalance it used to trigger
  bought nothing.

### Changed (messaging, follow-up to C02 #21)

- **`EventBus.drain`'s documented promise is narrower.** It was "returns once
  there is nothing deliverable left"; it is now "offers what has arrived", and
  how much has arrived is explicitly not part of the contract. No driver
  behaviour changed and the port's three guarantees (order per subject, at least
  once, order survives failure) are untouched, but a caller must no longer read
  one quiet drain as "the backlog is empty". The outbox relay already drains on
  a schedule and is unaffected.
- **`DeliveryReport.delivered` and `.failed` are documented as what the drivers
  actually count.** `delivered` was described as "handler calls that returned
  without raising"; both drivers count once per event per *group*, however many
  handlers that group has, and `failed` counts blocked subjects per group rather
  than raises. The drivers agreed with each other, so the documentation was
  wrong. No behaviour or signature change.
- `KafkaEventBus` takes an optional `rewind_grace_seconds` (default 15).

### Added (C02, #21)

- Flow DSL as policy content: versioned YAML in `config/flows/`, loaded
  strictly like a rule pack, with a `flow_hash` per flow. States declare their
  tools, their transitions and an `agentic` marker; conditions are a closed
  vocabulary, never an expression.
- The seven flows from plan 22 section 5. All 19 intents are claimed by exactly
  one flow, and only `DISPUTE_CHARGE` and `SAFEGUARD_SETUP` may propose.
- `FlowRouter`, filling the `FlowEngine` seam C01 left, and `FlowToolAdapter`,
  the tool surface a flow may reach. Built over the narrow MCP view, so a flow
  having no execute capability is a property of the surface.
- Validation refuses: a state using a tool outside its flow's allowlist, an
  unknown transition target, an unreachable state, a non-terminal exit, a flow
  with no terminal state, a duplicate condition, an unreal entry intent, and two
  flows claiming one intent.
- `CLARITY_FLOWS_DIR`.

### Changed (C02, #21)

- `FlowEngine.step` takes `(state, intake, facts)`. It took `(state, intake)`
  when C01 declared it with no implementation; conditions are evaluated against
  the case's own records, so the facts argument is required.
- `POST /v1/conversation/turn` derives a turn's facts from the case record. A
  client may now contribute only context keys (`product`, `chat_intent`,
  `safeguard`), never a figure. No `/v1` schema change: the response is an
  untyped object and gained keys.

### Fixed (C02, #21)

- `compose_reply` fell back to the amount in the customer's own text when the
  facts carried none, so "why was LKR 49 deducted" came back quoting 49 as
  Clarity's finding before anything had been evaluated. Only FACTS may supply an
  amount now (I1). The C01 turn verifier is what caught it.
- A vague follow-up pulled a customer out of their dispute: `FALLBACK` is an
  entry intent for `KNOWLEDGE_QA`, so a mid-dispute "has it been sorted?"
  switched flows. An active flow is no longer abandoned by a vague or
  low-confidence turn, while a confident switch still works.

### Added (C01, #19)

- Stateful turn pipeline `ConversationOrchestrator` (plan 22 section 4): guard,
  mask, intake, handoff check, flow step, compose, verify, record.
- Conversation state per **case** with a 24 hour TTL, through the unit of work
  so `lite` uses memory and `full` uses PostgreSQL. Holds no message history.
- Reply verifier: figures in a reply must appear in FACTS; forbidden content,
  unauthorised promises and missing citations block the reply, and an English
  fallback is recorded as a warning rather than blocking.
- `conversation.turn.completed@v1` event, and `AuditEventType.TURN_RECORDED`
  carrying flow state, tool and chunk ids, model role and verifier result.
- `FlowEngine` protocol: the seam C02 (#21) fills.

### Changed (C01, #19)

- **`/v1` contract.** `POST /v1/conversation/turn` now declares an optional
  `authorization` header. With a `case_id` the turn goes through the stateful
  pipeline and the route is subject bound (`CASE_READ` plus the case's own
  subscriber); without one the stateless path answers as before, with no
  credentials. The response is a strict superset of the previous shape, so no
  existing consumer loses a field. Snapshot and SDK regenerated.

### Fixed (C01, #19)

- The guard built in A03 had no call site: nothing in a request path inspected
  customer text. The pipeline now runs it on every turn, and a held injection
  is neutralised (intent becomes FALLBACK) rather than being allowed to steer
  the conversation.

### Added (A05, #9)

- Evaluation harness `clarity.ai.evaluation`: JSONL datasets, pure metric
  computation (macro F1, accuracy, pass-rate), release gates read from
  `config/ai/gates.yaml`, and a per-run report artefact in JSON and Markdown.
- `config/ai/gates.yaml`: the five gates from plan 22 section 10 with their
  thresholds and minimum dataset sizes. No threshold lives in code (I10).
- `make eval` and the `nightly-eval` workflow. The run exits non-zero when any
  gate fails **or could not be evaluated**, and names the failing metric.
- Intake dataset: 20 synthetic labelled utterances per language (si, ta, en,
  si-en). Deliberately includes phrasings the current keyword intake gets wrong.

### Changed (A05, #9)

- The safety corpus moved from `test_safety_set.py` into
  `tests/evaluation/datasets/safety.jsonl`, so the suite and the nightly job
  read one file. `load_safety` refuses a one-sided set.

### Fixed (A05, #9)

- `test_the_whole_injection_set_executes_nothing` never injected anything.
  `open_case` takes no text and the loop discarded it, so the test opened empty
  cases and would have passed with the injection corpus deleted. It now drives
  `handle_turn`, the one path customer text travels.
- Nothing asserted that an attacker-supplied figure stays out of the reply.
  "refund me LKR 50000" is extracted into the intake slots as a hint (I2, by
  design); a test now checks across the whole corpus that no such figure is
  quoted back.

### Added (A04, #8)

- `clarity-mcp`, a second deployable: MCP over Streamable HTTP at `/mcp`,
  stateless, run with `uvicorn clarity.entrypoints.mcp_asgi:app` or `make mcp`.
- OAuth 2.1 resource server. A scope selects the tool profile
  (`clarity.customer-assist`, `clarity.staff-assist`, `clarity.analytics`);
  exactly one is required and two are refused rather than narrowed.
- Tool listings are filtered by the token's profile, as well as refused on call.
- RFC 8693 token exchange for downstream calls. With no exchange endpoint
  configured a downstream call is refused, never made with the inbound token
  (ADR-0018 forbids passthrough).
- New MCP tools `search_knowledge` (cited from the published rule catalogue,
  with the query PII-masked) and `get_network_status` (simulated, labelled).
- MCP Apps UI cards `ui://clarity/why-card` and `ui://clarity/receipt`.
- Keycloak realm: the three profile client scopes, and a realm-roles protocol
  mapper on each client.
- Walkthrough [WT-10](docs/walkthroughs/WT-10-external-mcp-client.md), verified.

### Changed (A04, #8)

- **`MCPCaseView` gained `network_status(case_id)`.** Consumers of
  `clarity.app.mcp_view` must provide it. `ResolutionServiceMCPView` takes an
  optional network source and returns an "unknown" status without one, so an
  existing two-argument construction still works.

### Fixed (A04, #8)

- **A customer MCP session with no case binding could read every case.** The
  binding was only compared when present, so a principal with
  `profile=customer-assist` and no `case_id` passed the check entirely. In
  process the orchestrator always set it; over the network the binding comes
  from the token, so an external client could present that shape. A customer
  session is now bound or refused (`SESSION_NOT_BOUND`).

### Added (P01, #41)

- Proactive consumers for `payment.recorded@v1`,
  `usage.threshold_reached@v1` and `pack.expiring@v1`.
- Policy-backed duplicate-reload, FUP threshold and pack-end detectors publish
  idempotent `risk.detected@v1` facts through the transactional outbox.
- Duplicate reload risks enter the existing resolution path and complete one
  AUTO_FIX action and receipt without human input.
- Nested event delivery is guarded so an active queue head cannot be consumed
  recursively while its handler creates follow-on facts.

### Added (N01, #39)

- Notifications consume `receipt.issued@v1`, `risk.detected@v1` and
  `approval.requested@v1` through the existing consumer framework.
- Approved template references, exact parameter validation, recipient
  preferences, consent, quiet hours, channel fallback and delivery status.
- Idempotency per `(event, recipient, template)` and an explicit refusal
  for every free-text body.

### Changed (H01, #29)

**`/v1` contract change.** The seven development-only `/mock/*` operations were
removed from the Clarity API. The reviewed OpenAPI snapshot and generated
frontend SDK were regenerated on purpose.

- Added a separately runnable, explicitly simulated `hutch-sim` HTTP service.
- Added HTTP read and command drivers for all eight evidence sources and the
  action command port; the existing parity suites run against both transports.
- The `full` profile selects the HTTP drivers. The `lite` profile remains
  Python-only with in-process synthetic adapters.

### Added (Wave 1 core modules)

**`/v1` contract change.** Nine new operations; the reviewed OpenAPI snapshot
was regenerated on purpose (`backend/tests/acceptance/golden/openapi-contract.json`).
No existing operation changed shape, so a current client keeps working.

- Policy Studio (M-GOV, #20): `GET /v1/admin/policy/changes`, `POST /v1/admin/policy/changes`, and `review`, `approve`, `schedule`, `activate`, `rollback` on `/v1/admin/policy/changes/{change_id}`. Staff only; separation of duties is enforced by the governance gate, not the route, because a route cannot know who drafted a change.
- `POST /v1/auth/refresh` (M-IAM, #7): exchanges a refresh token for a new access token. Public, like sign-in: the refresh token is the credential.
- `GET /v1/finance/reconciliation` (M-REC, #38): the queue of executed actions with no adapter confirmation. Staff only, because it lists money that moved unmatched.

- Durable idempotency, transient-versus-final refusals, durable confirmation tokens, and `approval.requested@v1` (M-ACT, #25).
- Orchestration split out of `CaseService` into `clarity.modules.resolution`; the aggregate keeps the case and its state machine (M-CASE, #34). Method names unchanged, so the HTTP and MCP interfaces were untouched.
- Rule confidence can come from the policy store, resolved as of the disputed event, and four new rule packs: `VAS_RENEWAL_UNNOTIFIED`, `PACK_MISMATCH`, `LOAN_RECOVERY`, `OUTAGE_DURING_PACK` (M-DET, #35).
- Keycloak JWKS verification, OPA authorization parity, shared OTP state and revocable rotating sessions (M-IAM, #7).
- Persisted Policy Studio lifecycle with approvals, schedules, activations, supersession and rollback drafting (M-GOV, #20).
- GoRules ZEN-compatible outcome table with a 1,000-input reference parity suite (M-DEC, #36).
- OpenBao Transit signing, retained rotation keys, isolated stateless rendering and `receipt.issued@v1` (M-RCPT, #37).
- Daily action reconciliation and `reconciliation.mismatch@v1` (M-REC, #38).

Consumers to update: the frontend SDK is regenerated from the schema (`make contracts`), which is checked in CI.

### Added (B01, #10)
- `clarity.contracts.events`: one typed payload model per catalogued event (17, `type@v1`), a registry, `validate_payload`; a payload class cannot define a personal-data field.
- The event vocabulary moved from `platform.messaging` to `contracts.events` (`EventType` kept as an alias); `Event.of(payload, subject=...)`; `Event.caused(payload)`; `schema_version` is now an integer.
- The outbox validates every event against its schema on `append`.

### Added (R0 and interaction model)
- Acceptance suite `backend/tests/acceptance`: route contract for every route, the four journeys over HTTP, OpenAPI snapshot of the `/v1` contract (regenerate with `UPDATE_GOLDEN=1`).
- Declared module dependency map with a cycle check (`tests/architecture/test_module_dependencies.py`); ADR-0029 and plan 21 §11 (calls for answers, events for side effects, event catalogue).

### Fixed
- D7: the `/mock/*` simulated-HUTCH routes had no sign-in and no profile guard; they now return 404 in `prod`.
- D8: `/v1/me/*` routes were authorised by `case:read` for every action, including reload and pack purchase; they now declare `self:read`, `self:settings` or `self:transact` (customers only; staff get 403).

### Merged from `main` into `dev` (2026-10-02)
- Team commits `74fa3d1`, `2bd8fc9`, `429f035` ported into the R1 layout with 3-way merges: chat module (`modules.conversation`), admin and console APIs, receipt verification and UI updates, synthetic world in SQL for the `full` profile (`integration/drivers/mock/store`), new scripts (`keys`, `seed`, `token_report`, `tag_baseline`).
- Next.js apps and packages in `frontend/` kept (R5 started early).
- The parallel backend from `aeaab67` was not adopted (41 tests, missing the policy resolver and governance); it stays in git history for R2/R4/R6 reference.
- `CLARITY_PROFILE=lite` is accepted as the documented name of `demo`.
- Development identity routes follow the team's rule: allowed in synthetic profiles (`demo`, `full`), 404 in `prod`.

### Changed
- **Repository restructured (migration step R1):** backend moved to `backend/` and layered as `kernel → contracts → integration → platform → ai → modules → app → interfaces → entrypoints`; each module has a `public.py` (only import surface, test-enforced) and a `MODULE.md`; `modules.actions` split into `public` (vocabulary) and `capability` (money-moving code).
- ASGI entry point is now `clarity.entrypoints.asgi:app` (was `clarity.api.main:app`).
- **`/v1` contract:** repeating `POST /v1/cases/{id}/confirm` (or approve, auto-fix) for an executed plan now returns the original result and receipt with `200`, instead of `409 PLAN_NOT_PENDING`.
- Receipts record the roles that actually approved (for example `finance`, or `supervisor+finance` for four-eyes) instead of always `supervisor`.
- Docs merged: one plan (v1.3) with chapters 18-21, one ADR sequence (0001-0028), `AGENTS.md` replaces `agent.md`.

### Fixed
- D1: a concurrent double confirm could issue two signed receipts for one refund, or leave the plan unexecutable; a second confirm after success returned an error.
- D2: the four-eyes threshold in policy was not enforced by the tool layer (a hard-coded LKR 25,000 was used).
- D3: the development staff sign-in had no profile guard; it is now refused in `prod` like the OTP inbox (synthetic `demo` and `full` profiles keep it).
- D6: `make check` failed on a clean clone (Playwright is now an optional `render` extra).

### Added
- Plan chapter 21 (migration, runtime model: containers for the core, serverless at the edges, microservice extraction path) and ADRs 0025-0028.
- Architecture tests for module boundaries; regression tests for D1-D4.
