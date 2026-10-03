# plan.md - Migration to modular microservices

> **Audience:** contributors (human and AI agents) working this migration. Read [AGENTS.md](AGENTS.md) first; this plan does not relax any invariant in AGENTS.md §3.
>
> **Status:** DRAFT, not approved. No code changes until the ADR in Phase 0 is Accepted.
> **Created:** 2026-10-02
> **Supersedes:** nothing yet. Requires superseding [ADR-0002](docs/adr/0002-modular-monolith-with-satellites.md).

---

## 1. What is being asked

Move Hutch Clarity from a modular monolith (`clarity-api` plus satellites) to modular microservices: independently deployable services, each owning its data, communicating over contracts rather than Python imports.

## 2. Read this before starting

[ADR-0002](docs/adr/0002-modular-monolith-with-satellites.md) is **Accepted** and chose the modular monolith deliberately. It says:

> "Changing it requires a new ADR that supersedes this one and a plan update via `docs/enterprise-plan/CHANGES.md`."

It also pre-defines the extraction mechanism, which this plan follows:

> "A module is extracted by binding its facade to an HTTP client; callers don't change."

So this is **not a rewrite**. It is the extraction path the architecture was designed for. ADR-0002 rejected microservices for one reason only: "Network, versioning and deployment cost without benefit at prototype scale." The new ADR must state what changed to make that cost worth paying.

---

## 3. Blocking question: which codebase becomes microservices?

The repo currently holds **two** backends:

| Path | What it is | Serves traffic? |
|---|---|---|
| `src/clarity/` | Legacy prototype, feature complete, 50+ routes | **Yes** - this is `localhost:8000`, what the frontend and demos use |
| `backend/src/clarity/` | New modular monolith, 19 modules scaffolded | **No** - not wired to the frontend |

`ARCHITECTURE.md` calls `src/clarity` a "strangler", meaning `backend/src/clarity` is meant to replace it. But today the working app is the legacy one, and both define overlapping routes (`/v1/cases` exists in each).

**This matters more than the microservices question.** Extracting `backend/src/clarity/modules/*` into services would be extracting code that serves no traffic, while the app everyone actually uses stays a monolith. The migration would produce 13 deployable services and a demo that still runs on `src/clarity`.

### Options

| Option | Description | Cost | Recommendation |
|---|---|---|---|
| **A - Finish the strangler first** | Complete the `src/clarity` to `backend/src/clarity` migration so the modular monolith serves `:3000`. Then extract services from working code. | High up front, low risk | **Recommended.** Extract from code that works and has tests. |
| **B - Extract now, migrate later** | Build services from `backend/src/clarity` modules while `src/clarity` keeps serving traffic. | Looks fast, two divergent systems to reconcile | Not recommended. Doubles the surface and defers the real work. |
| **C - Microservices from `src/clarity`** | Carve services out of the legacy prototype directly. | Legacy has no module boundaries, no `public.py`, no schema-per-module | Not recommended. ADR-0002's "extraction becomes a rewrite" warning applies. |

**This plan assumes Option A** and sequences accordingly. If the decision is B or C, Phases 2 to 5 need reordering before any work starts.

---

## 4. Extraction readiness: measured, not assumed

Audited `backend/src/clarity/modules/` on 2026-10-02. The boundaries are in unusually good shape:

| Check | Result | Meaning |
|---|---|---|
| Modules with a `public.py` facade | **19 of 19** | Every extraction seam exists |
| Cross-module `public.py` calls | **2** (`case -> actions`, `reconciliation -> actions`) | Almost no inter-module coupling to convert |
| I5 violations (cross-module `domain/` imports) | **2** (`decision -> detection.domain`, `autopsy -> knowledge.domain`) | Two shared types to turn into wire schemas |
| Modules declaring their own schema | yes (`schema = "case"` in `module.py`) | ADR-0003 schema-per-module already honoured |
| Outbox present | `platform/messaging/outbox.py` | I7 foundation exists |

### Gaps found

1. **`import-linter` does not guard the new code.** The contracts in `pyproject.toml` target the legacy namespaces (`clarity.core`, `clarity.api`, `clarity.ai`, `clarity.mcp`, `clarity.schemas`). Nothing enforces I4 (layer rule) or I5 (module boundary) on `backend/src/clarity/modules/*`. **The 2 violations above were found by hand, not CI.** This must be fixed before extraction, or boundaries will erode while we work.
2. **Facades are stateless pure functions, not services.** `decision.public.decide()` takes data and returns a `Decision`. Easy to extract, but there is no per-module DB session or ownership enforced at runtime yet.
3. **One shared DB session** (`platform/db/session.py`). Each service needs its own connection, role and migration chain.
4. **No service template, no service-to-service auth, no gateway, no distributed tracing.**

---

## 5. Target architecture

19 modules do not become 19 services. Grouped by bounded context and by what actually needs independent deployment:

| Service | Modules absorbed | Owns | Why separate |
|---|---|---|---|
| `clarity-identity` | iam, customer | subscriber refs, consent, tokens | Trust boundary, holds the vault |
| `clarity-case` | case, timeline | cases, evidence snapshots | Core write path, highest traffic |
| `clarity-decision` | detection, decision | nothing (stateless) | Pure functions, scales independently, rule bundle releases |
| `clarity-actions` | actions, reconciliation | proposals, executions, ledger | **Money path.** Isolate for audit and blast radius |
| `clarity-receipts` | receipts | receipt chain | Signing keys, pairs with existing `signer` |
| `clarity-conversation` | conversation, knowledge | threads, articles | AI-facing, different scaling profile |
| `clarity-intelligence` | autopsy, foresight, proactive, insights | analytics | Batch and read-heavy, can fail without affecting money |
| `clarity-ops` | deskops, governance, content, notifications | queues, policy artefacts, templates | Staff-facing, lower availability bar |

Plus the existing satellites, unchanged: `ai-gateway`, `channel-gateway`, `hutch-sim`, `mcp`, `signer`.

**Total: 8 new services + 5 existing = 13.**

Note honestly in the ADR: ADR-0002 rejected a "~13 microservices" v1.0 plan. This lands on the same number. The ADR must justify why that is now correct rather than quietly repeating the rejected design.

### Non-negotiables that get harder

| Invariant | Monolith today | After extraction |
|---|---|---|
| I7 events via outbox, same transaction | one DB transaction | **saga + compensation**. The money path (`case -> actions -> receipts`) can no longer be one transaction. This is the single biggest correctness risk. |
| I8 idempotency on state change | in-process table | must survive retries **across the network**, per service |
| I6 no cross-schema joins | enforced by convention | enforced by physics, and queries that relied on proximity must become API calls or read models |
| I3 Money is Decimal LKR | Python type | must survive JSON serialisation without float coercion. String-encoded Decimal in every wire schema. |
| I11 time from `Clock` | injected | each service needs the same injected clock for replay to stay exact |

---

## 6. To-do list

Updated as implementation proceeds. Checkbox states are the source of truth for progress.

### Phase 0 - Decide and record (no code)

- [ ] Resolve the Section 3 blocking question (A, B or C) with the team
- [ ] Write `docs/adr/0015-modular-microservices.md`: context (what changed since ADR-0002), decision, the 8-service split, alternatives, consequences, compliance
- [ ] Set ADR-0002 status to `Superseded by 0015`
- [ ] Add ADR-0015 to `docs/adr/README.md` index
- [ ] Record the plan change in `docs/enterprise-plan/CHANGES.md`
- [ ] Add a "Deviations" entry in `ARCHITECTURE.md`
- [ ] Get ADR-0015 to `Accepted`. **No work below starts before this.**

### Phase 1 - Close the gaps found in the audit

- [ ] Rewrite `import-linter` contracts in `pyproject.toml` to cover `backend/src/clarity`: layer contract for L0-L7 (I4), and a `forbidden` contract per module blocking `modules.*.domain` and `modules.*.infrastructure` from outside that module (I5)
- [ ] Verify the new contracts actually fail: confirm they catch the 2 known violations
- [ ] Fix `decision -> detection.domain`: move the shared `Detection` type to a contract schema
- [ ] Fix `autopsy -> knowledge.domain`: same treatment
- [ ] Add `make check` gate so CI blocks on import-linter
- [ ] Give every module a `MODULE.md` from `docs/templates/MODULE.md` (19 files, currently 0 per `docs/modules.md`)

### Phase 2 - Finish the strangler (Option A only)

- [ ] Inventory `src/clarity` routes against `backend/src/clarity` module routes, mark each: ported, missing, divergent
- [ ] Port the missing routes into their owning modules
- [ ] Point `frontend` at the modular monolith; confirm every flow in Section 9 passes
- [ ] Delete `src/clarity` (or move to `docs/adr/legacy/`) once parity is proven
- [ ] Update `ARCHITECTURE.md`: strangler complete

### Phase 3 - Platform work that must precede any service

- [ ] Publish L0 kernel as a versioned internal package (`clarity-kernel`): Money, IDs, Clock, errors. Every service depends on a pinned version.
- [ ] Service template: FastAPI app, `/health`, `/ready`, OpenTelemetry tracing, structured logs, config resolver, OPA client, error envelope
- [ ] Service-to-service auth: mTLS or signed service tokens, per I9 deny-by-default
- [ ] Per-service DB: own database and role, own Alembic chain, no shared session
- [ ] Promote the outbox to a real bus (Kafka per ADR-0004) with idempotent consumers
- [ ] Network-safe idempotency: `Idempotency-Key` honoured per service, verified under retry
- [ ] Distributed tracing across a full request, verified end to end
- [ ] Contract test harness: every service ships a fake, consumers test against it
- [ ] Decide gateway and discovery; update `deploy/helm` and `deploy/opentofu`

### Phase 4 - Extract services, lowest risk first

Each extraction follows the ADR-0002 mechanism: write the wire contract, stand the service up, then **replace the `public.py` body with an HTTP client while keeping the signature identical**. Callers do not change. Keep the in-process binding behind a profile flag (I20) so either wiring can be selected at the composition root.

- [ ] **`clarity-decision`** (detection + decision). Stateless, no DB, 1 inbound caller. Prove the pattern here.
  - [ ] `contracts/openapi/decision.yaml` + semver + `CHANGELOG.md`
  - [ ] Service scaffold from the template
  - [ ] `public.py` bound to HTTP client, signature unchanged
  - [ ] Golden tests pass identically in-process and over HTTP
  - [ ] Rule bundle release path still works (I10)
- [ ] **`clarity-conversation`** (conversation + knowledge)
- [ ] **`clarity-intelligence`** (autopsy, foresight, proactive, insights)
- [ ] **`clarity-ops`** (deskops, governance, content, notifications)
- [ ] **`clarity-identity`** (iam + customer). Vault and RLS move here; highest security review bar.
- [ ] **`clarity-case`** (case + timeline)
- [ ] **`clarity-actions`** (actions + reconciliation). **Money path.** Needs the saga below. Two approvals per AGENTS.md §10.
  - [ ] Design and document the saga for `case -> actions -> receipts`, including compensation for every step
  - [ ] Prove zero duplicate financial executions under induced network failure and retry (I8)
- [ ] **`clarity-receipts`**. Hash chain must stay intact across the service boundary; verify chain continuity after extraction.

### Phase 5 - Verify, document, close

- [ ] Parity suite green for every port and driver (I20)
- [ ] Walk every flow in Section 9 against the deployed services
- [ ] Chaos pass: kill each service in turn, confirm the money path either completes or compensates, never half-applies
- [ ] `ARCHITECTURE.md` rewritten: new system picture, service map, status per unit
- [ ] `docs/modules.md` updated: kind becomes `service`, new paths, owners
- [ ] Devlog entry per PR in `docs/devlog/2026/`
- [ ] Walkthroughs re-verified with date and commit
- [ ] `.env.example` and deployment docs updated for every new variable

---

## 7. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Money path loses transactional integrity | **Critical** | Saga with compensation, designed and reviewed before `clarity-actions` moves. Extract it last. |
| Two backends diverge further during migration | High | Resolve Section 3 first. Option A removes this risk. |
| Boundaries erode while we work | High | Phase 1 import-linter gate, before any extraction |
| 13 services for a prototype-scale team | High | This is exactly what ADR-0002 rejected. The ADR must justify it or the split should shrink. |
| Decimal money coerced to float over JSON | High | String-encoded Decimal in every schema; add a contract test asserting no float on a money path (I3) |
| Replay no longer exact (I11) | Medium | Same injected `Clock` contract in every service; replay test in the parity suite |
| Receipt chain breaks across boundary | Medium | Chain continuity test before and after `clarity-receipts` extraction |

## 8. Honest assessment

The module boundaries are genuinely ready: 19 facades, 2 cross-module calls, 2 boundary violations. Extraction is mechanical for 6 of the 8 services.

The hard parts are not the extraction. They are:
1. **The two-backend question** (Section 3), which is a bigger problem than the architecture style.
2. **The money-path saga**, which replaces a database transaction with a distributed protocol. That is where correctness can be lost.
3. **Justifying 13 services**, given ADR-0002 rejected that exact shape and the team has not grown.

Phases 0 to 2 deliver real value regardless of whether microservices happen: the import-linter gate, the MODULE.md files, and finishing the strangler are all overdue. Phase 3 onward is only worth it if the ADR can answer "what changed since ADR-0002".

## 9. Flows that must pass at every phase gate

1. Login with the simulated OTP code
2. Reload, buy a pack, cancel a subscription
3. Ask Clarity a question, reach a decision with evidence
4. Apply a fix, receive a signed Trust Receipt
5. Verify that receipt publicly
6. Staff handoff appears in the desk queue and can be approved

---

## 10. GitHub issue backlog - todo list

Linked to the 42 open issues in the repo. Check off each item as it is merged. Issue numbers link to GitHub. Priority: p0 = critical path, p1 = required, p2 = important, p3 = nice-to-have.

### Wave 0 - Baseline wiring (do before any other wave)

- [x] #5 `[B02]` Unit of work and repository interfaces per module (in-memory drivers) `p0`
- [x] #6 `[B05]` PostgreSQL repositories: schema and role per module, migrations, row-level security `p0`
- [x] #11 `[B03]` Event bus port: in-process driver and Kafka driver with one parity suite `p0`
- [x] #12 `[B04]` Outbox in the unit of work, relay, and consumer framework with dead-letter handling `p0`
- [x] #14 `[B06]` First event-driven flow: receipts issued on action.completed `p0`
- [x] #15 `[B07]` Typed settings and profile wiring: no environment reads outside the composition root `p1`
- [x] #16 `[B08]` Observability baseline: traces, metrics, masked logs, correlation IDs `p1`
- [x] #17 `[B09]` Frontend SDK generated from OpenAPI, checked in CI `p1`
- [x] #18 `[B10]` CI lanes: full-profile integration, blocking frontend build, secret scanning and SBOM `p1`

### Wave 1 - Core modules (money path, detection, identity)

- [x] #25 `[M-ACT]` Actions: database idempotency, row locks, approval.requested, retry after transient failure `p0`
- [x] #34 `[M-CASE]` Case: split orchestration into a resolution service, case aggregate on repositories `p0`
- [x] #35 `[M-DET]` Detection: rule parameters in the policy store (D5) and four more rule packs `p0`
- [x] #7 `[M-IAM]` Identity: Keycloak for staff and MCP clients, OPA for authorization, shared OTP state `p1`
- [x] #20 `[M-GOV]` Governance: persisted policy artefacts, approvals and activations; Policy Studio API `p1`
- [x] #36 `[M-DEC]` Decision: outcome matrix as a GoRules ZEN decision table `p1`
- [x] #37 `[M-RCPT]` Receipts: signer service port with OpenBao/KMS driver, isolated rendering `p1`
- [x] #38 `[M-REC]` Reconciliation module: daily match of actions against adapter confirmations `p2`

Driver verification (all five done, 2026-10-03): each acceptance test was
re-run against the real component rather than a stand-in, and proven able to
fail first. This found 4 Kafka defects, an OPA policy that was never
evaluated, a wrong OpenBao Transit path, and a Keycloak JWKS bug that
rejected every real token. See the M-GOV, M-DEC, M-RCPT, M-REC and M-IAM
devlogs.

### Wave 2 - AI layer (gateway, safety, MCP, evaluation)

- [x] #2 `[A01]` AI gateway: model roles, config/ai/models.yaml, fallback chains, quota-aware buckets `p0`
- [x] #3 `[A02]` Recorded responses (cassettes): no live model calls in CI `p0`
- [x] #4 `[A03]` Safety: PII masking coverage per language and the guard role `p0`
- [x] #8 `[A04]` MCP server over the network: SDK, Streamable HTTP, OAuth 2.1 resource server, new tools `p0`
- [x] #9 `[A05]` Evaluation harness: per-language golden sets, metrics and release gates `p1`

### Wave 3 - Conversation and knowledge (RAG, flows, chat UI)

- [x] #19 `[C01]` Conversation orchestrator and state store `p0`
- [x] #21 `[C02]` Flow registry and the seven flows `p0`
- [x] #22 `[C03]` Bounded agent step: planner with tool allowlist, limits and fallback `p0`
- [ ] #31 `[K01]` Knowledge module: source registry and governed ingestion `p0`
- [ ] #32 `[K02]` Index and retrieval: BM25 (lite), pgvector hybrid (full), filters and rerank `p0`
- [ ] #33 `[K03]` Grounded answers: compose with citations, citation verifier, refusal, semantic cache `p0`
- [ ] #23 `[C04]` Intake: keyword rules first, extract role when unsure, Singlish support `p1`
- [ ] #24 `[C05]` Customer chat experience on flows: confirm cards, citations, handoff `p1`

### Wave 4 - Enrichment, ops, channels (parallel tracks)

- [x] #29 `[H01]` hutch-sim as an HTTP service with HTTP drivers `p1`
- [x] #39 `[N01]` Notifications module: templates, preferences, consent, dispatch, delivery status `p1`
- [x] #41 `[P01]` Proactive module: stream detectors and risk.detected `p1`
- [ ] #13 `[AU01]` Autopsy: event-fed, embeddings via the embed role, review workflow `p2`
- [ ] #26 `[D01]` Desk operations: bulk fix with four-eyes, merchant watch, regulator pack, shift handover `p2`
- [ ] #30 `[I01]` Insights: projections and console dashboards `p2`
- [ ] #40 `[N02]` Channel gateway: WhatsApp sandbox, SMS and USSD simulator, verified webhooks `p2`
- [ ] #27 `[F01]` Foresight: backtest and calibration report `p3`

### Wave 5 - Production readiness (ship gate)

- [ ] #28 `[FE01]` Frontend: verified build, static UI retired, Next.js 16, accessibility and language review `p1`
- [ ] #42 `[X01]` Security hardening: threat-model checks, DAST, dependency and licence scanning `p1`
- [ ] #44 `[X03]` Deployment artefacts: images, compose full, Helm, OpenTofu, serverless edges `p1`
- [ ] #43 `[X02]` Performance and resilience: load and chaos tests `p2`
