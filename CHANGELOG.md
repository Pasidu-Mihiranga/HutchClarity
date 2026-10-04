# Changelog

Notable changes to Hutch Clarity. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [Semantic Versioning](https://semver.org/). Public-surface and `/v1` contract changes are always listed.

## [Unreleased]

### Changed (audit assurance Phases 2, 6 and 7, breaking for stored hashes)

- **Record hash version 3** (ADR-0033 amendment). Version 2 hashed the datetimes
  as `isoformat()` strings, which bypassed the canonical hasher and produced
  `...+00:00` while the published JSON carries `...Z`: the hash was computed over
  a form the record is never published in, so no external verifier could
  reproduce it. Version 3 passes the datetimes as datetimes. `statement_hash` for
  checkpoints had the same defect and the same fix. Found by writing the offline
  export verifier; no version 2 record was ever persisted outside a test.
- **`AuditLedger.verify` takes `since`/`since_hash`** and resumes automatically
  from an archival floor; `ChainVerification` and `CheckpointVerification` gained
  `verified_from`. `Checkpointer.verify` takes `incremental`.
- **Every audit append is screened** and refuses a raw MSISDN, NIC, card number
  or email in the payload or the detail (`platform.audit.entropy`). The keyed
  `payload_hash` the plan proposed is **not** being done, and ADR-0033 says why.
- **`SwitchBoard` takes a `clock`**, so a flip is stamped from the injected clock
  (I11) rather than the wall clock.

### Added (audit assurance Phases 6 and 7, ADR-0038 and ADR-0039)

- **New `/v1` route**: `GET /v1/audit/export`, a bundle a regulator verifies with
  `backend/scripts/verify_audit_export.py`, which imports nothing from Clarity.
  Needs `audit:export`. OpenAPI snapshot and SDK types regenerated on purpose.
- **New permission `audit:restore`** (`Permission.AUDIT_RESTORE`): in
  `AUDIT_DUTIES` and `STEP_UP_PERMISSIONS`, **not** grantable, held by
  `PLATFORM_ADMIN`. Mirrored into `config/opa/data.json`.
- **Backup and restore** (`platform.audit.backup`, `platform.audit.vault`):
  AES-256-GCM bundles, a loss report measured against a checkpoint held outside
  the bundle, and a restore that refuses a measurable loss unless the operator
  accepts it in the call.
- **Retention, legal hold and erasure** (`platform.audit.lifecycle`): archival
  into sealed segments with the chain continuous across the floor, holds by
  subject or seq range that outrank both retention and erasure, and erasure by
  crypto-shredding the pseudonym link rather than deleting records. ADR-0039
  states the limitation this leaves.
- **Sealed ports** (`integration.replay`): `SealedCommandPort` refuses every call
  and counts attempts, so zero adapter calls during a replay is a property of the
  type; `ReadOnlyCommandPort` allows `status_of` and still refuses `execute`.
- **Six more risk rules**: snooping, collusion, budget pressure, off hours, grant
  abuse, agent pressure, plus `trail_lag` for events committed but never
  published. Fourteen rules in total.
- Audit event types `data.read`, `backup.created`, `backup.read`,
  `restore.performed`, `reconciled`, `segment.sealed`, `hold.placed`,
  `hold.released`, `erasure.performed`.
- Collections `platform.audit_checkpoints` (which had never been registered, so
  the `full` profile had no table for it), `platform.audit_floor`,
  `platform.audit_segments`, `platform.audit_holds`,
  `platform.audit_pseudonyms`. 16 new policy keys and two settings
  (`CLARITY_AUDIT_BACKUP_KEY`, `CLARITY_AUDIT_BACKUP_DIR`).

### Added (audit assurance Phase 4, ADR-0037)

- **New module `clarity.modules.assurance`** (public surface: `AssuranceService`,
  `Alert`, `AlertState`, `Disposition`, `AlertRefused`, `AlertNotFound`,
  `Band`, `Finding`, `RULES`, `ALERTS`, `HEARTBEATS`, `PLAYBOOK_SWITCHES`,
  `SECOND_PERSON_BANDS`, `CHAIN_BREAK`, `CHECKPOINT_GAP`, `DETECTOR_SILENT`).
  A leaf: it calls no module and no module calls it.
- **Eight counted risk rules** over the audit trail, thresholds in
  `config/policy/audit.yaml`: structuring, self-approval, money without proof,
  switch-then-pay, break-glass used, mass audit read, denial spike, brute
  force. Plus chain break, checkpoint gap and detector silence.
- **New `/v1` routes**, all signed-in: `GET /v1/assurance/alerts` and
  `POST /v1/assurance/alerts/{alert_id}/acknowledge|investigate|dispose`.
  OpenAPI snapshot regenerated on purpose (four routes added); SDK types
  regenerated.
- Audit event types `alert.raised`, `alert.acknowledged`,
  `alert.investigating`, `alert.disposed`, `alert.escalated`.
- Collections `assurance.alerts` and `assurance.heartbeats`; 15 new policy keys
  under `assurance.*`.
- Detection and liveness run on a schedule in each API process
  (`assurance.detection.interval`, PT5M).

### Changed (audit assurance Phase 4)

- **Audit records for domain events now carry money facts** in their detail:
  `amount_lkr`, `total_amount_lkr`, `outcome`, `confirmed_by`,
  `approver_roles` and the related identifiers, where the event has them. A
  counted rule has nothing to count without them. No PII (I13).

### Added (audit assurance Phase 3, grant endings)

- Audit event types `grant.expired` and `grant.lapsed` (a missed
  recertification), each recorded once with `occurred_at` the exact moment the
  grant ended. `AuditGrants.record_endings()`; `AuditGrant.ended_at`,
  `end_reason`, `ending()`.
- A background sweep in each API process (FastAPI lifespan) on new policy key
  `audit.grant.sweep_interval` (PT1M); `Clarity.grant_sweep_interval()`.
  Every authenticated request also records endings first.
- No `/v1` contract change.

### Added (audit assurance Phase 3, ADR-0036)

- **New `/v1` routes**, all signed-in: `GET /v1/audit` (paged trail, hashes
  and masked detail only, with checkpoint verification; every read recorded),
  `GET` and `POST /v1/audit/grants`, `POST /v1/audit/grants/{grant_id}/approve`,
  `.../revoke`, `.../recertify`, and `POST /v1/audit/break-glass`. OpenAPI
  snapshot regenerated on purpose (seven routes added, nothing changed); SDK
  types regenerated.
- Permissions `audit:export`, `audit:assign` (step-up), `alert:dispose`.
  `security_admin` gains `audit:assign`; `compliance` gains `audit:export` and
  `alert:dispose`. `config/opa/data.json` and the rego policy updated to match.
- `clarity.modules.iam.public`: `AuditGrants`, `AuditGrant`, `GrantState`,
  `SubjectKind`, `GrantRefused`, `GrantNotFound`,
  `GrantAwareAuthorizationPolicy`, `is_subject`, `GRANTS`.
- `Principal.granted`; `permissions_for(roles, granted=...)`;
  `AUDIT_DUTIES`, `GRANTABLE_PERMISSIONS`.
- Policy keys `audit.grant.max_duration`, `audit.grant.review_interval`,
  `audit.grant.break_glass_duration`. Audit event types `grant.requested`,
  `grant.approved`, `grant.revoked`, `grant.recertified`, `grant.break_glass`,
  `audit.read`.

### Changed (audit assurance Phase 3)

- **Holding any audit duty now removes money permissions**, by role or grant
  (separation of duties). No existing role held both, so no current role loses
  anything; it applies to stacked roles and to grants.
- `Clarity.authorization` is wrapped in `GrantAwareAuthorizationPolicy`.

### Added (audit assurance Phase 2, ADR-0035)

- **Signed audit checkpoints.** `clarity.platform.audit.checkpoints`:
  `Checkpointer`, `Checkpoint`, `CheckpointVerification`, `statement_hash`,
  `signature_valid`, `checkpoint_document`. Signed with a key separate from the
  receipt key. Verification reports a trail cut below a checkpoint with the
  exact `seq` range lost.
- **New public route** `GET /.well-known/clarity-audit-checkpoint.json`: the
  latest checkpoint with its public key, for anyone to keep as a witness. OpenAPI
  snapshot regenerated on purpose; SDK types regenerated.
- Policy keys `audit.checkpoint.every_records` and `audit.checkpoint.max_age`
  (`config/policy/audit.yaml`). Audit event type `checkpoint.issued`.
- Setting `CLARITY_AUDIT_SIGNER_KEY_NAME`. `Clarity(audit_checkpoints=...)`;
  `reset()` carries the checkpointer with the trail.
- `AuditLedger.after_append(hook)` and `AuditLedger.open_unit`.

### Changed (audit assurance Phase 2)

- Startup verification checks the trail against its signed checkpoints, not
  only its chain, and `ledger.opened` records the result.

### Added (audit assurance W2)

- Identity and access events in the audit trail: `otp.requested` (with its
  outcome, including unknown numbers, masked), `otp.verified`, `otp.failed`,
  `staff.session_started` (roles and step-up), `token.refreshed`,
  `token.rejected` (a presented token or refresh token refused) and
  `access.denied` (every 403, with the reason). Anonymous 401s with no token
  are not recorded.
- `request.performed`: every state-changing request records who made it, the
  session, the route template, the case and the status, so an approval names
  the supervisor rather than the mode. Opt-out, with reasons, in
  `clarity.interfaces.http.trail.NOT_RECORDED_AS_REQUESTS`.
- `session_ref`, a truncated hash of the access token, links a sign-in to
  everything later done or refused with that token.
- No `/v1` contract change: responses are byte-for-byte as before; refusals
  are still answered by FastAPI's default handler after being recorded.

### Changed (audit assurance W0, ADR-0033)

- **`AuditRecord` hash version 2.** `chain_hash` now covers every field of the
  record, not only the payload hash: `seq`, `event_type`, `actor_ref`,
  `object_ref`, `case_id`, the times and the `detail` (through `detail_hash`).
  New fields `hash_version`, `actor_kind`, `session_ref`, `detail_hash`,
  `occurred_at` and `recorded_at`; `at` remains as a read-only alias of
  `recorded_at`. `AuditLedger.append` takes optional `actor_kind` and
  `session_ref`. Floats in a payload or detail are rendered with `repr` before
  hashing.

### Added (audit assurance W1, ADR-0034)

- `AuditLedger(open_unit, *, clock)`: the trail persists through the
  persistence port in collections `platform.audit` and `platform.audit_head`,
  appended in order, insert-only, retried on `ConcurrentUpdate`. New
  `AuditUnavailable`, `ActorKind`, `record_hash`, `hashable`.
- Audit event types `event.published`, `demo.reset`, `ledger.opened`.
- An `audit` consumer group records every domain event type in the trail.
- `ClarityMCPServer(cases, *, ledger=None)`: with a ledger, every MCP call is
  appended as `mcp.invoked`, actor kind `agent`, arguments hashed.
- `Clarity(audit=...)`; `Clarity.reset()` carries the trail across and records
  `demo.reset`. A broken trail at startup raises `AuditChainBroken`.
- Setting `CLARITY_AUDIT_BREAK_GLASS` (default `false`).

### Fixed (audit assurance W0 and W1)

- **An audit record's actor, type, case, time and detail could be rewritten
  without `verify()` noticing.** Only the payload hash was chained.
- **The audit trail was lost on every restart, split per process, and erased
  by a demo reset**, and decisions, executions, receipts and MCP calls were
  never recorded in it.

### Removed (FE01, #28)

- **The static UI is retired.** `clarity.interfaces.http` no longer serves
  pages: `GET /`, `/desk`, `/ops`, `/autopsy`, `/foresight`, `/verify`, `/v`
  and `/v/{receipt_id}` are gone, along with the `/static` mount and
  `interfaces/http/static/`. The three Next.js apps are the only UI. No `/v1`
  route changed and the OpenAPI snapshot is unchanged: the page routes were all
  `include_in_schema=False`.
- **`VERIFY_BASE` now points at the verify app**, `http://localhost:3002/r` by
  default rather than `http://localhost:8000/v`, because the route it used to
  name no longer exists. A receipt's `verify_url` and its QR code follow it.
  Deployments that set `VERIFY_BASE` explicitly are unaffected.

### Changed (FE01, #28)

- `@clarity/sdk` throws `ClarityApiError` (exported) instead of `Error` on a
  failed call, carrying `status`. A caller that catches `Error` still works;
  one that needs to tell "not found" from "unreachable" can now do so.
- `list_receipts` (mock store repository) takes a required `verify_base`
  keyword. It used to rebuild a restored receipt's `verify_url` from a
  hard-coded `http://localhost:8000/v/...`, which ignored the configured base.

### Fixed (FE01, #28)

- **The customer chat never read the signed-in customer's account.** The page
  held a hardcoded literal with `activity: []` and no setter, and
  `accountIntents` reads exactly those fields to decide whether a question
  reaches the rule engine. It answered `false` for `twice`, `slow`, `sub` and
  `missing` for every customer, so three of the four demo journeys rendered
  "Could not confirm" while the backend had a decision waiting: Nimal's
  duplicate reload (`AUTO_FIX`, LKR 3,500.00) and Kumar's active fair-use cap
  (`EXPLAIN_ONLY`) were both contradicted on screen. The page now fetches
  `GET /v1/me/app`, and the greeting uses the customer's own name rather than
  a constant.

- **The public verify page no longer reports an unverified receipt as valid.**
  It fell back to a "placeholder" verdict whenever the API call failed, and
  that verdict was *valid* for any id not containing the string "bad", so an
  unknown receipt number, a tampered one and an unreachable API all rendered
  "Chain valid" with "Signature OK". It now has a third outcome, "could not
  check", and shows it rather than guessing. The static page it replaces
  showed an error on a 404.
- The same page read `kid` where the API sends `key_id`, so a verified
  receipt's key id never appeared.

### Added (F02)

- Foresight exports a deterministic aggregate `ScenarioRehearsal` with a
  swappable `PersonaSimulator`, relative-band baseline comparison, seed and
  simulator version. It carries no individual records or execution capability.
- The Foresight demo includes synthetic backtest status and prominently states
  `SCENARIO, NOT CERTAINTY` and `NOT CALIBRATED ON REAL HUTCH LAUNCHES`.

### Added (AU02)

- `clarity.modules.autopsy.public` exports `BatchComplaint`; `AutopsyService`
  adds mask-first dataset `ingest` and a reviewer `workspace` with masked
  examples, language counts, synthetic trends and clustering diagnostics.
- `GET /v1/demo/autopsy` now ingests DATA01 instead of a twelve-line tuple and
  explicitly identifies `TrigramSimilarity` as non-semantic clustering.

### Added (F01, #27)

- `clarity.modules.foresight.public` exports `Backtest`, `CalibrationReport`,
  `CalibrationStatus`, `HistoricLaunch`, `ObservedOutcome`, `Provenance` and
  `MIN_REAL_LAUNCHES`. `Backtest.run(launches)` replays recorded launch
  outcomes through the statistical baseline and reports mean absolute and
  signed **band-step** error (LOW=0, MEDIUM=1, HIGH=2), an exact-band rate and
  a top-theme hit rate. Never a complaint count: bands are all the baseline
  emits.
- **A synthetic launch never moves the calibration status.** `CALIBRATED`
  requires three launches with `Provenance.REAL` (plan 02 §3.4), of which the
  prototype has none (**REQUIRES HUTCH CONFIRMATION**), so every report it can
  produce today reads `not_calibrated`. Three SIMULATED `DEMO_LAUNCHES` ship so
  the report can be run and read; the baseline scores 0.500 mean absolute band
  error against them.
- **Nothing comparable reports no error rather than a perfect one.** With zero
  overlapping (theme, segment) pairs the error fields are `None` and
  `summary()` says "not measurable", in the same shape as an `UNEVALUABLE`
  evaluation gate. An observed theme the model never predicted is reported in
  `unpredicted` instead of being scored as a LOW prediction, and a prediction
  with no recorded outcome is reported in `unobserved`, because absence of a
  record is not a LOW observation.
- `Foresight.run` takes a keyword-only `calibration=None` (source compatible),
  and `ForesightReport` gained `calibration`. `ForesightReport.backtested` is
  now derived from that calibration instead of the hard-coded `False` it
  carried before, so `is_decision_ready` opens on evidence and on nothing else.

### Added (N02, #40)

- `clarity-channel-gateway`, a separate deployable for WhatsApp, SMS and USSD
  ingress (`make channel-gateway`, port 8102). The version it replaces was
  deleted in `3cca478`: a standalone app with its own in-memory thread store
  that minted case ids like `CASE-{uuid4}`, so a WhatsApp conversation was
  backed by no case, no decision and no receipt.
- Signature-verified webhooks. `sha256=<hex>` of
  `HMAC-SHA256(secret, "<timestamp>.<raw body>")`, with six refusals: no secret
  configured, missing or malformed signature, unknown scheme, wrong signature,
  a timestamp outside a five-minute window in either direction, and a delivery
  id already seen. Constant-time comparison, verified over the **raw bytes**
  before parsing, and a rejection echoes nothing from its payload.
- **No secret configured refuses every webhook** (I9). `/health` reports
  `signing_configured`, because a gateway that accepted unsigned webhooks for
  want of a secret looks like it works.
- The 24-hour customer service window. Outside it only an approved template is
  sent (I15), the composed reply is dropped and the response says so rather
  than substituting silently. Sending never extends the window, and each
  `(channel, thread)` has its own.
- The gateway drives the real conversation: it resolves the number, finds the
  subscriber's open case or opens one, and hands the text to C01's
  orchestrator, so a WhatsApp thread is one case rather than one per message.
  An unknown number opens nothing and reveals nothing.
- **It produces `complaint.created`**, which plan 21 section 11.3 names
  channels as the producer of. AU01 wired the autopsy consumer for it with
  nothing producing it; this closes that loop, and the event still carries no
  message text.
- `POST /sim/{sms|ussd}`, the basic-phone simulator, as a separate unsigned
  path rather than a bypass flag on `/webhooks/*`. **404 in `prod`**, because
  an unsigned ingress there would undo every refusal above.
- `CLARITY_CHANNEL_WEBHOOK_SECRET`, and `clarity.interfaces.channels` added to
  the interface independence contract, which now covers three interfaces.

No `/v1` change and no OpenAPI snapshot change: the gateway is its own ASGI app
on its own port.


### Added (I01, #30)

- The `insights` module, previously a scaffold. Read models folded from the
  event log: top causes, where the assistant stops, drop-offs and refunds by
  rule. `InsightsService`, `Insights`, `apply`, `rebuild` and `PROJECTED` are
  on its public surface.
- **Replaying the log rebuilds the same numbers**, which is the property that
  makes a dashboard worth reading. Three things get it: folding an event twice
  counts it once (at-least-once, I7); joins happen at read time, so a refund
  whose `cause.detected` has not arrived is still attributed once it does; and
  anything "latest" is decided by `turn_no` in the event rather than by arrival
  order.
- The `insights` consumer group, whose subscription is derived from the
  projection's own `PROJECTED` tuple so the fold and the subscription cannot
  drift.
- Collection `insights.projections`, one row holding the read model.

### Fixed (I01, #30)

- **`GET /v1/demo/ops` read live objects**, so its numbers were whatever was in
  one process: a restart lost them and a second replica disagreed with the
  first. It now reads the stored projection.
- **That route summed money with `float`** (`money += float(stake)`). I3 allows
  no float anywhere on a money path and a dashboard is on one, because a figure
  a desk acts on has to be the figure the ledger holds. The projection keeps
  `Decimal` and serialises as a string.
- `events_folded` counted events the projection ignored, so a live fold and a
  replay of the same history reported different totals. It now counts the
  events the projection used, which is also the more useful number.

The console does not render any of this yet, so the demo route is the only
surface.


### Added (D01, #26)

- Desk operations, previously a scaffold. `DeskOps` carries a bulk fix with a
  dry run and four-eyes, merchant watch scores, a regulator pack export and a
  shift handover (plan 02 section 3.5).
- **Bulk fix.** A batch names cases and a reason; a dry run says what would
  happen to each and changes nothing; a second person approves **that dry
  run**; execution then runs each case through the ordinary single-case path,
  producing one receipt per case.
- The approval is of a dry-run **fingerprint** over the eligible cases, their
  plan ids and their amounts. Execution refuses a different one, so an
  approval cannot drift onto work nobody reviewed: without it, four-eyes
  approves a label.
- Merchant watch scores, counted from case records and carrying what they were
  counted from, so a reader can argue with the weighting rather than with the
  number. Weights are **PROPOSED TARGET - REQUIRES HUTCH VALIDATION**.
- A regulator pack keyed entirely by HMAC subscriber references, with no
  MSISDN, name or customer text (I13), and a shift handover that leads with
  what is still outstanding.
- Collection `deskops.batches`, so an approval survives the request.
- `clarity.app.desk`: the two adapters joining the desk to the case service.

Constraints worth knowing, each enforced by a test: a bulk fix executes each
case's own existing plan and cannot invent one (I1); maker is never checker at
the batch level and again per case; **`ONE_TAP_FIX` is never bulk executed**,
because that is the customer's tap and a desk cannot mint their confirmation
token (ADR-0007), so only `AUTO_FIX` and `STAFF_APPROVAL` are actionable; a
partial failure is reported and never rolled back; re-executing a batch does
nothing further (I8); and a batch over 200 cases is refused because a batch
nobody can read before approving is a batch nobody approved.

No `/v1` surface yet, so the desk is reachable from code and tests only.


### Added (AU01, #13)

- Complaint Autopsy runs as a service fed by `complaint.created`, instead of a
  batch over demo data per request. `AutopsyService` masks and keeps each
  complaint as it arrives and redraws clusters on `rerun`, which is also the
  batch entry point, so the event feed and the batch cannot drift.
- The review workflow. `ClusterReview` is an immutable record with a reviewer,
  a time and a note; a second verdict is refused rather than overwriting one,
  and `supersede` changes a verdict while keeping the one it replaced and
  requires a reason.
- `staff_view`, the only sanctioned representation of a cluster for a person.
  It always carries `hypothesis`, `status_label` and `acted_on`, so an
  unreviewed cluster cannot reach a screen without saying nobody has checked it
  (I16). A `suggested_rule_id` travels with `suggested_rule_is_a_guess`.
- Persistence: `autopsy.complaints` and `autopsy.clusters`. Only **masked**
  complaints are stored (I13), and a complaint quoting a credential is never
  stored at all. Before this a verdict died with the request that gave it.
- A `Similarity` seam for the `embed` role, defaulting to `TrigramSimilarity`,
  named for what it is so nobody reads a cluster as semantically grouped.
  There is still no embedding model in the system.

### Changed (AU01, #13)

- **Removed `ComplaintAutopsy.confirm`.** It recorded a verdict by appending
  `(reviewed by X)` to the cluster's label, which put audit data in display
  text, appended twice if it ran twice, kept no time or note, and had nowhere
  to persist. `ClusterReviews.record` replaces it.
- `GET /v1/demo/autopsy` is served by the service and returns the labelled
  staff views. The response shape changed and the OpenAPI snapshot was
  regenerated: it is a demo route behind `DESK_QUEUE_READ` with no frontend
  consumer.
- `ComplaintAutopsy.recluster` clusters already-masked complaints, which is the
  seam the event feed needs.

Nothing produces `complaint.created` yet: the producer is the channels work, so
the consumer is wired and idle.


### Fixed (C05, #24)

- **The customer chat never ran the server-side flows.** `POST
  /v1/conversation/turn` reads `case_id` from the top level of the body and
  only then takes the stateful pipeline; the client sent it inside `facts`,
  where the route never looks, so every turn took the stateless path. C01 to
  C03 and K03 all landed behind a route the UI was calling in a mode that
  skipped them. The client now sends it at the top level.
- Accessibility: the chat composer had no accessible name (a placeholder is not
  one), the sign-in labels were not bound to their inputs, and the transcript
  was not a live region so a reply arriving while focus was in the composer was
  never announced. All three fixed.
- A pre-existing type error in `apps/customer-web/app/cases/page.tsx`, invisible
  because `npm run typecheck` covers only `packages/sdk` and never the apps.

### Added (C05, #24)

- Flow artefacts rendered in the chat: the journey and its current step, a
  confirm card from the proposal, the citations K03 verified, a handoff notice
  and a refusal notice. `components/FlowCards.tsx`.
- 42 strings in en, si and ta in the shared `@clarity/i18n` package, and `t`
  now interpolates `{placeholders}`.
- `packages/i18n/test/catalogues.test.mjs`: the three catalogues must carry the
  same keys, no string may be empty or left as its own key, no language may be
  mostly copied English, and placeholders must match across languages. Uses
  `node:test`, so no new dependency.
- `frontend/e2e/dispute-charge.spec.ts` and `playwright.config.ts`: the browser
  journey for acceptance 1, plus `make e2e`, `make e2e-install` and
  `make dev-e2e`. **The suite has not been executed**: the browser binary could
  not be downloaded in the environment this change was made in. It compiles and
  its three tests are discovered; the selectors are believed correct, not known
  correct.

No `/v1` contract change and no OpenAPI snapshot change: the route already
returned everything rendered here.


### Added (C04, #23)

- `clarity.ai.language`: the Singlish lexicon, tokenising and folding, moved
  out of `modules.knowledge.terms` so intake and retrieval share one copy.
  Both import it downward; no module edge was added.
- `conversation/intake.py`: an ordered rule table with Sinhala, Tamil and
  Singlish alternations on every rule, Singlish language detection, and the
  `extract` role seam. `classify`, `detect_language`, `reply_language`, `Rule`,
  `IntakeAssist` and `ASSIST_BELOW` are on the module's public surface.
- `detect_language` returns `si-en` for Singlish, recognised by vocabulary
  because it has no script of its own. `reply_language` answers it in Sinhala.
- `IntakeResult.assisted` records whether the `extract` role was consulted.
- `intake_heldout.jsonl`, a held-out set written before the rules were extended
  and not consulted while extending them.

### Changed (C04, #23)

- **Intake intent F1 per language: en 0.688 to 1.000, si 0.559 to 1.000, ta
  0.520 to 0.930, si-en 0.305 to 0.930.** Held-out F1 is 1.000 in all four.
  Thirteen of twenty Singlish examples previously classified as FALLBACK,
  because the rules held no Singlish vocabulary at all.
- Rules are ordered and the first match wins. The previous table took the
  highest confidence matching anywhere, which made specificity depend on
  whatever number somebody typed.
- `extract_intake` takes an optional `assist`. A model is asked only below 0.70
  confidence, its answer is capped and validated against the intent catalogue,
  and an intent it invents is rejected.
- The `intake` gate still reports UNEVALUABLE: it requires 300 examples per
  language and the set holds 20. The minimum was **not** lowered.


### Added (K03, #33)

- Grounded answers. `KnowledgeService.ask` retrieves, composes, verifies and
  caches; `compose_answer` quotes the source verbatim with its citation when no
  model is configured, uses model wording when one is and it verifies, and
  refuses with "I do not know" plus a person when there is no source.
  `KnowledgeService`, `Answer`, `GroundedAnswer`, `AnswerKind`, `Composer`,
  `compose_answer` and `refuse` are on the knowledge module's public surface.
- The citation verifier. Every citation in an answer is checked against the
  retrieval behind it: retrieved, effective, audience-allowed. A citation
  attempt with no version is reported as malformed rather than passed through
  as prose. `verify_citations`, `CitationReport`, `CitationFault`,
  `citations_in` and `malformed_citations` are public.
- The answer cache, keyed by corpus fingerprint, language and audience, so a
  publication makes every earlier entry unreachable rather than merely
  invalidated. Refuses refusals, ungrounded answers and case-specific ones.
- `knowledge.published@v1`, produced by the knowledge registry through the
  outbox. Consumed by the `knowledge-cache` group, which re-indexes and drops
  cached answers from an older corpus. K01 deliberately did not declare it
  because nothing consumed it.
- The simulated help articles already served by `/v1/knowledge/search` are now
  published into the registry (`app/knowledge_seed.py`), labelled with the
  `hutch-sim` owner. Nothing new is invented (I16).
- `rag.citation_accuracy` is now measured. It **fails** at 0.931 against a gate
  of 0.980: two of 29 answered queries cite a real, effective, allowed source
  that is the wrong document. Left failing, because the cause is the missing
  embedding model and not a threshold to lower.

### Changed (K03, #33)

- **`/v1/knowledge/search` is served by `clarity.modules.knowledge`**, not the
  mock store. The response is additive: `articles` keeps its shape and place
  because two other routes and the frontend SDK read it, and `answer`,
  `citations`, `grounded` and `needs_person` are new. The OpenAPI snapshot was
  regenerated; the only change is the route's description, since the handler
  returns an untyped object.
- `KNOWLEDGE_QA` now reaches its `answered` exit. `FlowRouter` performs a
  deterministic retrieval in any state that allows `search_knowledge`, so the
  step works with no model configured (ADR-0009); before this the state was
  agentic, unplanned and therefore silent.
- A grounded knowledge answer, or the no-source refusal, now wins over the
  intent template in the turn reply, and a turn with no source routes to a
  person with reason `no_published_source`.
- `Chunk` carries its source's `title`, for display beside a citation.
- **A flow in a terminal state restarts rather than resuming.** A terminal
  state has no transitions, so a customer who asked one knowledge question
  could never ask a second. C02 handled the cross-flow case and missed this
  one.
- `GroundedAnswer.grounded` requires every claimed citation to appear in the
  report's verified set. An empty `CitationReport` means "nothing was checked"
  and `all([])` is true, so an answer carrying citations with a default report
  read as verified without anything having verified it.
- A state's own output is visible to its own transitions, so `answer_found` can
  see citations produced in the same turn.


### Added (K02, #32)

- Lexical retrieval over the knowledge corpus. `KnowledgeRetriever` filters with
  the registry, ranks with Okapi BM25, applies a deterministic rerank and cuts
  to `top_k`. `Hit`, `RetrievalTrace`, `SemanticRanker`, `QueryRewriter`,
  `RewritingRetriever`, `RetrievalConfig` and `tokens`/`query_terms` are on the
  knowledge module's public surface.
- `config/ai/retrieval.yaml` and `CLARITY_RETRIEVAL_FILE`: top-k, BM25
  constants, fusion weights and rerank bonuses out of code (I10).
- Singlish query expansion. A domain lexicon of romanised Sinhala words maps a
  query into the English the corpus uses, additively and on the query only.
- `RewritingRetriever`, the optional `extract`-role query rewrite. Both the
  original and the rewritten query run and the original wins ties, so a bad
  rewrite costs latency rather than an answer.
- The retrieval golden set, `load_rag`/`load_rag_corpus`, a `recall_at_k`
  metric, and `measure_rag` in the evaluation script. **The `rag.recall_at_5`
  release gate is now evaluable and passes at 0.967 (n=30)**, where it
  previously reported UNEVALUABLE and blocked.
- `tests/contract/test_retriever_parity.py`, the retriever port's contract. The
  pgvector hybrid driver is registered and skips.

### Changed (K02, #32)

- `config/ai/gates.yaml`: the `rag` gate's `min_per_language` raised from 0 to
  20, so a set too small for recall@5 to mean anything still blocks.
- `tests/architecture/test_module_state.py` gained a `DERIVED_INDEXES` category
  for the BM25 term frequencies: an index is a pure function of committed state
  and repopulates on a miss, so losing it costs CPU rather than a fact.

The `full` profile's pgvector hybrid is **not** implemented: there is no
embedding model in the system, so `ModelRole.EMBED` has nothing behind it and
the AI layer has no shape that can carry a vector. The seam, the fusion and the
port contract are in place; with no semantic ranker the weights renormalise onto
the lexical half (ADR-0009). See the K02 devlog.


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
