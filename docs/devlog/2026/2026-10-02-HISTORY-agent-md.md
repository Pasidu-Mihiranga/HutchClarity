# 2026-10-02 - HISTORY - Former agent.md: backlog, change log and status

| Field | Value |
|---|---|
| Author(s) | Imported by agent: Claude Code (Anthropic), working with the team lead |
| Work package | R1 (docs merge) |
| Why | `agent.md` was the team's guide and change log. Its rules now live in `AGENTS.md`, its as-built status in `ARCHITECTURE.md`, and new history goes into one devlog file per change. This file keeps the original record verbatim (headings demoted one level) so nothing is lost. |

---

### 6a. Implementation backlog (todo list)

Target for the first build: **R0 - hackathon prototype**, scoped by `01-executive-summary-problem.md` §1.9. Status: ☐ todo · ◐ in progress · ☑ done.

### P1 - Foundation
- ☑ P1.1 Monorepo skeleton (pyproject, ruff, mypy strict, pytest, uv venv, py.typed)
- ☑ P1.2 `src/clarity/schemas` - canonical Pydantic v2 models + canonical JSON/hashing
- ☑ P1.3 `src/clarity/events` - envelope, catalogue, transactional outbox with retry/DLQ and idempotent consumers

### P2 - Mock HUTCH systems and adapters
- ☑ P2.1 `src/clarity/integrations/base.py` - read/command ports, driver modes, completeness, typed errors
- ☑ P2.2 Mock read drivers for all 8 sources + stateful command adapter (idempotent)
- ☑ P2.3 Synthetic world with the 4 demo journeys (`integrations/mocks/world.py`)

### P3 - Deterministic core ("rules decide")
- ☑ P3.1 Timeline builder: 8-source join, per-source completeness, evidence snapshot hash
- ☑ P3.2 Rule engine: predicate language with backtracking, pack loader, confidence, ranking, ruled-out
- ☑ P3.3 Rule packs (6 of 16): VAS_NO_CONSENT@4, DUPLICATE_RELOAD@2, RELOAD_NOT_CREDITED@1, FUP_CAP_REACHED@3, PACK_EXPIRY_BURN@2, DUPLICATE_VAS_CHARGE@1
- ☑ P3.4 Golden tests: positive, negative, boundary, property-based (21 golden + 93 others = 114)
- ☑ P3.5 Decision policy: full outcome matrix, caps, budgets, risk signals, hashed input, rationale
- ☑ P3.6 Tool layer: action plans, single-use confirmation tokens, staff approval with four-eyes, refund budget ledger, idempotent execution, compensation on partial failure

### P4 - Trust Receipts
- ☑ P4.1 Receipt payload/envelope, canonical hashing, hash chain, supersede-not-edit
- ☑ P4.2 Ed25519 dev signing service + public key publication + `verify_signature` (public material only)
- ☑ P4.3 Verification (hash, signature, ledger, chain), public view, SMS short form, recurrence test
- ☑ P4.4 PNG/PDF rendering in si/ta/en via Playwright, escaped input, no external loads

### P5 - API and persistence
- ☐ P5.1 Persistence layer (SQLAlchemy; SQLite for demo, PostgreSQL via compose) - **deferred**, stores are in-memory
- ☑ P5.2 FastAPI `/v1` endpoints + OpenAPI + RFC 9457 problem details
- ☑ P5.2a Case service: one orchestration shared by every channel
- ☑ P5.3 Append-only hash-chained audit ledger (tamper and deletion both detected) + outbox

### P6 - AI and MCP
- ☑ P6.1 PII masking + token vault: LK phone/NIC/passport recognizers, OTP/card/CVV **refused** not masked, TTL vault, audited restores
- ☑ P6.2 AI gateway: 4-tier routing (template → cache → small → reasoning), masking enforced before any call, template fallback, token accounting
- ☑ P6.3 Output verifier: invented numbers, unauthorised promises, leaked PII, invented tokens, wrong language
- ☑ P6.4 MCP server: 8 tools across 3 profiles, subject binding, no execute path, audited denials
- ☑ P6.5 `OpenAICompatibleProvider` for any vLLM/Ollama/hosted endpoint, configured by env. **None configured by default** - the template tier is the deck's "works without the LLM" path.

### P7 - Experience
- ☑ P7.1 Customer **Why?** page: pick a customer, ask, see cause + evidence + ruled-out, confirm in one tap
- ☑ P7.2 Public receipt verify page (QR target) + QR SVG endpoint
- ☑ P7.3 Clarity Desk: queue sorted by money at stake, case cockpit, approvals (incl. four-eyes)
- ◐ P7.4 Sinhala/Tamil UI copy: headings, buttons and explanations translate; some API-sourced strings (headline, action list) are still English

### P8 - Intelligence and submission
- ☑ P8.1 Complaint Autopsy: mask-first, dedupe, canonical form, clustering, rule mapping, hypothesis-until-reviewed
- ☑ P8.2 Foresight: aggregates only, relative bands not counts, not decision-ready until backtested
- ☑ P8.3 `docs/submission/`: AI disclosure with **measured** numbers, known limitations, demo script, `scripts/measure_tokens.py`

### Prototype simplifications (deliberate, to be labelled in the README)
| Simplification | Production design |
|---|---|
| In-memory stores (nothing survives a restart) | PostgreSQL 16 + pgvector (§21) |
| Clarity issues its own tokens; the Desk role picker asserts roles rather than proving them | HUTCH SSO/MFA federated through Keycloak, HUTCH OTP service, OPA for the decision points (§19, ADR-0010). The permission model and the route checks do not change. |
| UI is plain HTML/JS served by FastAPI | Next.js + TypeScript + Tailwind (§21). Chosen so the prototype runs from one command with no Node toolchain; the pages only use the public `/v1` API, so swapping them changes nothing server-side. |
| In-process event bus over a PG outbox | Kafka + Schema Registry (§18.4) |
| Decision policy in Python, OPA-shaped input document | OPA/Rego bundles (§14.3) |
| Dev Ed25519 key on disk | HSM/KMS signing service (§15.2) |
| Mock HUTCH drivers only | Approved HUTCH interfaces (§9) |

### 7. Change log

| Date | Change | Files |
|---|---|---|
| 2026-10-02 | Added §0 *Working economically (AI credits)*: read narrowly, targeted tests then one `make check`, no sub-agents unless asked, cheaper model for mechanical work, 3-sentence change-log rows, and recorded responses for any live model. The product itself already costs 0 tokens (ADR-0009). | `agent.md` |
| 2026-10-02 | **Implemented improvement plan Phase 3: identity and authorization** - the largest remaining gap, since every endpoint had been open. Added `core/iam/` (10 roles, 19 permissions, EdDSA tokens, OTP) and `api/auth.py`, where `requires(...)` is a dependency so a route cannot be mounted without declaring what it needs and `public()` is explicit rather than an omission. Customers sign in by OTP through a delivery port - the demo's port is a labelled simulated inbox, and the code never comes back from the request; staff pick roles from a labelled simulated identity provider. A customer token's subject is the `subscriber_ref` pseudonym, never the MSISDN, because tokens reach logs and proxies. **Writing the tests found four real authorization defects, all fixed:** `POST /v1/cases/{id}/proposals` had *no authentication at all*, so anyone could build an action plan - the step where amounts get attached - on any case; `approver_ref` came from the request body, so one person could approve twice under two names and satisfy four-eyes alone; `mfa_step_up` also came from the body, so the approval audit recorded whatever the client claimed; and the receipt read and render routes checked the permission but never the owner, leaving `RECEIPT_READ_ANY` as a scope-widener that was never consulted. Both body fields are now gone from `ApproveRequest` rather than left to be silently ignored, and identity facts come from the session. **Three further design errors corrected during the work:** a `CASE_READ_OWN`/`CASE_READ_ANY` split left staff without "own" (now a base `CASE_READ` plus a widener); `Clarity.reset()` signed everyone out (identity is not demo data); and `TokenIssuer.verify(now=...)` aged step-up while leaving expiry to the real clock, so an injected clock was only half honoured. Because the approver is now the token's subject, four-eyes needs two genuinely different people, so the Desk sign-in asks who you are. Verified in a real browser: OTP sign-in refuses a wrong code then accepts the right one and completes the Sinhala journey to a VERIFIED receipt; on the Desk an agent with step-up is refused the above-cap approval, a supervisor without step-up is refused, and a stepped-up supervisor completes it. 437 tests, `make check` green. | `src/clarity/core/iam/*`, `src/clarity/api/{auth,main,schemas,container}.py`, `src/clarity/api/static/*`, `tests/unit/test_iam.py`, `tests/unit/test_api.py`, `docs/adr/0010-*.md`, `docs/improvement-plan.md`, `ARCHITECTURE.md`, `docs/submission/{KNOWN_LIMITATIONS,DEMO_SCRIPT}.md` |
| 2026-10-02 | **Implemented improvement plan Phases 0-2.** **Phase 0 closed both defects:** the idempotency key is now claimed before the confirmation token is redeemed, so the reproduction went from 1,051 errors in 2,000 concurrent calls to **zero** (40 fresh, 1,960 replayed, one refund per trial); redemption and the mock adapter take locks instead of relying on the GIL; MCP now receives a narrow `MCPCaseView` with no execute capability, enforced by an AST scan of the package. **Phase 1** made policy scoped, effective-dated and guard-railed: decisions resolve `as_of` the disputed event and record a `config_snapshot_hash`, so "which caps applied when this happened" is answerable. **This corrected an earlier decision of mine:** I had raised the global auto-fix cap 1,000 -> 5,000 to make the deck's LKR 3,500 example work, loosening every rule; the global cap is back to 1,000 with a rule-scoped 3,500 for `DUPLICATE_RELOAD` under a 5,000 guardrail. Added kill switches (each degrades to staff, never to failure), a replay impact report, and maker-checker governance. **Phase 2** added 25 port parity tests, 4 import contracts, runtime profiles and 9 ADRs plus `ARCHITECTURE.md`. **Three further design problems were found while building and fixed rather than waived:** releasing an idempotency key on failure let a concurrent duplicate get a different error (outcomes are now final, ADR-0005); `with_override` appended instead of superseding, colliding with the value it replaced; and the import contracts exposed `events` importing `core.ids` (IDs are vocabulary, moved to `schemas`) and `core` importing `ai.templates` (CX content, moved to `core.content`). 387 tests, `make check` green. | `src/clarity/core/policy/*`, `src/clarity/core/tools/*`, `src/clarity/mcp/view.py`, `config/policy/`, `tests/contract/`, `docs/adr/`, `ARCHITECTURE.md`, `Makefile`, `pyproject.toml` |
| 2026-10-01 | **Compared with the alternative design in `HutchClarity-compair/`** (a friend's suggestion: a plan with 14 ADRs and no code, forked from our plan v1.0) and wrote `docs/improvement-plan.md`: adopt 14 ideas, adapt 6, skip 8, in 6 phases (~16 developer-days for the recommended Phases 0-4). Applying its checks to our code **found two real defects, not yet fixed**: (F1) under concurrency, 1,051 of 2,000 identical execute calls returned `ConfirmationInvalid`/`PlanNotPending` instead of the original result - money stayed safe, exactly one refund per trial, but single-use redemption relies on the GIL; (F2) the MCP server holds the full `CaseService`, so execute methods and `authorise_auto_fix` are reachable from MCP code - the "no execute path" test checks only tool names. Also corrected an error: the MCP server has **8** tools, not 7 as recorded earlier. No code changed. | `docs/improvement-plan.md`, `agent.md` |
| 2026-10-01 | **Closed out the deferred backlog.** P1.3 events (envelope, catalogue, transactional outbox with retry/DLQ and idempotent consumers). P5.3 append-only hash-chained audit ledger - altering *or deleting* a record is detected. P4.4 receipt rendering to PNG/PDF in si/ta/en via Playwright, with all input escaped and no external loads. P6.5 `OpenAICompatibleProvider` so any vLLM/Ollama/hosted endpoint works by env var. P7.4 Sinhala/Tamil UI copy (partial - API-sourced strings still English). P8.1 Complaint Autopsy, mask-first with clusters as hypotheses until reviewed. P8.2 Foresight on aggregates only, relative bands not counts, not decision-ready until backtested. P8.3 submission pack with **measured** token numbers. **Three real bugs found and fixed while doing it:** the receipt summary was internal English on a Sinhala receipt; the UI never passed the customer's language when opening a case, so Sinhala customers got English explanations; and an unclustered complaint vanished from the Autopsy report instead of being counted as noise. 309 tests, ruff and mypy --strict clean (58 files). | `src/clarity/events/*`, `src/clarity/core/audit/*`, `src/clarity/core/receipts/render.py`, `src/clarity/ai/{providers,autopsy,foresight}.py`, `src/clarity/api/static/*`, `docs/submission/*`, `scripts/measure_tokens.py` |
| 2026-10-01 | **P6 AI + MCP complete** (no model provider configured, P6.5). PII masking with Sri Lankan recognizers - and OTPs, card numbers and CVVs are **refused rather than masked**, with nothing from a refused message stored (deck S8). Token vault with TTL and audited restores. Deterministic output verifier that blocks invented amounts, promises the decision did not authorise, leaked PII, invented tokens and the wrong language. AI gateway with the deck's four-tier routing, masking enforced before any provider call, and a template fallback on verifier failure or provider outage. MCP server with 8 tools across 3 profiles: **no tool executes anything** - the strongest is `propose_action`, which takes no amount and creates a pending plan; subject binding stops one session reading another's case; every call and denial is audited. Explanations now appear in the UI in si/ta/en, and `/v1/ai/usage` reports measured (zero) token use. **No model is configured on purpose:** deck S7 says Clarity works without the LLM, and this is that path running for real. 260 tests (67 new), ruff and mypy --strict clean (50 files). | `src/clarity/ai/*`, `src/clarity/mcp/server.py`, `src/clarity/api/*`, `tests/unit/test_ai.py`, `tests/unit/test_mcp.py` |
| 2026-10-01 | **P7 UI complete** (si/ta copy deferred, P7.4). Driving the real UI in a browser found **a genuine bug the API tests had missed**: the Desk re-evaluates a case when opening it, which attempted an illegal state transition on an already-decided case and returned a 500. `evaluate` is now idempotent - reading a case never re-decides it, and an executed case keeps the decision its receipt cites. Also added `POST /v1/demo/reset` plus Reset buttons, since a demo has to be runnable twice in front of judges. Three pages on the existing `/v1` API: the customer **Why?** journey (pick a synthetic customer → ask → cause, evidence, ruled-out causes and policy rationale → confirm in one tap → Trust Receipt with QR), the **public verify page** the QR opens, and **Clarity Desk** (queue by money at stake, case cockpit, supervisor/finance approval incl. four-eyes). Added a QR SVG endpoint that encodes only the public verify URL. **Stack note:** plain HTML + vanilla JS served by FastAPI instead of Next.js, so the whole prototype runs from one command with no Node toolchain; recorded as a prototype simplification since the pages only consume the public API. Verified in a real browser with Playwright. | `src/clarity/api/static/*`, `src/clarity/api/main.py`, `pyproject.toml` |
| 2026-10-01 | **P5 API complete** (P5.1 persistence deferred). Added the case service - the shared orchestration every channel uses, so the money path is identical wherever the customer starts - and a FastAPI `/v1` with 15 endpoints, OpenAPI and RFC 9457 problem details. Risk signals are now **derived from evidence** (SIM swap from the identity source, repeat refunds from the ledger) instead of being passed in, so no caller can soften a risk flag. Safeguard parameters likewise come from the matched events, so a block cannot be redirected onto another merchant. Two deliberate tightenings of §17.2: confirmation tokens are minted and spent inside the request so they never reach a client, and amounts are never accepted from a client. Verified over real HTTP end to end, including QR verification. 189 tests (22 new, incl. HTTP-boundary guards), ruff and mypy --strict clean (44 files). | `src/clarity/core/cases/service.py`, `src/clarity/api/*`, `src/clarity/core/decision/assessor.py`, `tests/unit/test_api.py` |
| 2026-10-01 | **P4 Trust Receipts complete** (except PNG/PDF rendering, P4.4). Receipt payload is split from its envelope so verification is unambiguous: re-canonicalize, recompute the hash, check the Ed25519 signature against published public keys. Receipts chain to their predecessor, are never edited (corrections supersede), and cite evidence by id + hash rather than copying records. The recurrence test re-reads live state through a probe, so "PASSED" means the merchant block is genuinely in force - an unavailable probe reports UNAVAILABLE, never an optimistic pass. Added the public QR view (narrow by design) and the SMS short form. `scripts/demo.py` now ends each journey with an issued, verified receipt. 167 tests (22 new, incl. tamper/forgery/wrong-key), ruff and mypy --strict clean (40 files). | `src/clarity/schemas/receipt.py`, `src/clarity/core/receipts/*`, `src/clarity/integrations/mocks/recurrence.py`, `tests/unit/test_receipts.py`, `scripts/demo.py` |
| 2026-10-01 | **P3.6 tool layer complete.** Added `core/tools/`: action plans (one remedy = one plan, so "refund + switch off + block merchant" is one tap), single-use plan-bound confirmation tokens minted outside the AI path, staff approval with MFA step-up, maker≠checker and four-eyes above LKR 25,000, a refund budget ledger with reserve/commit/release, idempotent execution, and compensation on partial failure (a refund is never clawed back). Replaced the unused singular `Proposal` schema with `ActionPlan`/`PlanStep`/`PlanStatus`. `scripts/demo.py` now runs propose → confirm → execute for all four journeys. 145 tests (31 new), ruff and mypy --strict clean. | `src/clarity/core/tools/*`, `src/clarity/schemas/decision.py`, `tests/unit/test_tool_layer.py`, `scripts/demo.py` |
| 2026-10-01 | Corrected two stale statements in this file: §1 still said the repo contained no prototype code, and §3 listed only the docs. Both now reflect the partial prototype, and §3 marks every module as implemented or placeholder. Verified against the filesystem: P3.6 and P4–P8 directories contain only empty `__init__.py`. | `agent.md` |
| 2026-10-01 | **Implementation started: P1, P2, P3 (except the tool layer).** Built the deterministic core end to end - canonical schemas (Decimal money, pseudonymous subscriber refs, canonical JSON + hash chaining), the adapter framework with mock drivers for all 8 sources, a stateful synthetic HUTCH world covering the 4 demo journeys, the timeline builder, a declarative rule engine with 6 rule packs, and the decision policy. 114 tests pass; ruff and mypy --strict are clean. Added `scripts/demo.py`, which walks all four journeys. **Plan change:** raised the auto-fix cap from LKR 1,000 to LKR 5,000 (and the one-tap cap to LKR 10,000) because the deck's own zero-contact example is a LKR 3,500 double reload `[DECK S2, S5]`; §14.2 updated to match. | `pyproject.toml`, `README.md`, `src/clarity/**`, `rules/packs/*.yaml`, `tests/**`, `scripts/demo.py`, `docs/enterprise-plan/09-rules-decision-receipts.md` |
| 2026-10-01 | Created `agent.md` with the project guide, conventions, update protocol and change log. | `agent.md` |
| 2026-10-01 | **Plan audit (v1.1).** Found 24 gaps against the brief, the guidelines and the deck. Added: prototype scope (§1.9); proactive care engine (§3.6); personalization and guardian (§3.7); flow DSL (§3.8); FR-COP-15, FR-CH-05, FR-TR-07, FR-GOV-04/05; NFR-PERF-06, NFR-PRV-03, NFR-COST-01; shop-staff and external-verifier personas; Before/During/After (§6.7); channel constraints (§9.7); forecast disclosures (§12.9); financial controls and reconciliation (§14.4); data governance (§16.3); test data (§24.1); SLOs (§25.4); benefits measurement (§40.1); AI disclosure template, slide mapping, demo storyboard, readiness checklist (§42.3–42.6); new chapter 17 (§46–52: governance, release plan and traceability, compliance, change management, effort/TCO, assumptions register, post-production support). Diagrams 35–39 added. Gantt axis label changed to `%b %Y`. README duplicate tagline fixed. All 39 diagrams render and all links resolve. | `docs/enterprise-plan/01`–`03`, `05, 06, 08, 09, 10, 12, 15, 16`, new `17`, `README.md` |
| 2026-10-01 | **Plan v1.0 added to the repo.** The approved plan was split into 16 chapter files plus a README index, with 34 Mermaid diagrams. | `docs/enterprise-plan/*` |

### 8. Current status

| Item | Status |
|---|---|
| Enterprise plan (52 sections, 39 diagrams) | Complete, v1.1 (audited) |
| Diagram rendering | All 39 render with mermaid-cli 11 |
| Link integrity | 0 broken links |
| Git | Nothing committed. Everything is untracked on `main`. |
| Deterministic core, tool layer, Trust Receipts, API, web + Desk | **Working end to end.** `.venv/bin/uvicorn clarity.api.main:app` → `/` customer, `/desk` staff, `/v/{id}` public check |
| Tests / lint / types | **437 passing** · `make check` green: ruff, `mypy --strict` (71 files), 4 import contracts |
| AI + MCP (P6) | **Working.** Masking, verifier, gateway, provider and MCP server. **No model is configured** - explanations come from CX-approved templates, so measured token use is 0. |
| Events, audit ledger, Autopsy, Foresight, receipts PNG/PDF, submission pack | **Working** |
| Policy governance (Phase 1) | **Working.** Scoped, effective-dated caps with guardrails; kill switches; replay impact report; maker-checker approval |
| Boundaries (Phase 2) | **Working.** Port parity suites, import contracts, runtime profiles, 10 ADRs |
| Identity and authorization (Phase 3) | **Working.** EdDSA tokens, 10 roles and 19 permissions, deny-by-default routes, subject binding on cases and receipts, step-up before an above-cap approval, OTP sign-in for customers, role picker for the Desk. The permission model is production-shaped; **the issuer is ours**, so the role picker and SMS inbox are labelled as simulated (ADR-0010). |
| Remaining | P5.1 persistence (in-memory), P7.4 partial si/ta copy, RAG, real channels, voice, guardian |
| Demo video, test credentials | **Not in this repo** - team to confirm (`16-gap-submission-repo-docs.md` §42) |
| AI usage declaration | Draft. Real model names and measured token counts still need filling in (§42.3) |
| Technical PDF for submission | Not generated. The plan must be condensed to the Guidelines §8 structure. |

### 9. Open items and next steps

**The prototype is now demonstrable end to end.** `.venv/bin/uvicorn clarity.api.main:app` then open <http://localhost:8000/> for the customer journey, `/desk` for staff, `/v/TR-2027-000001` for public verification, `/docs` for the API.

**The R0 prototype backlog is complete** apart from two deliberate items:

| Item | Why it is still open |
|---|---|
| **P5.1 persistence** | In-memory stores. A restart loses all cases and receipts. Adding SQLAlchemy is additive - the services already sit behind clean interfaces - but nothing in the demo needs durability. |
| **P7.4 si/ta UI copy (partial)** | Headings, buttons and explanations translate. Strings the API composes (the headline, the action list) are still English. |

**Next implementation step: Phase 4 of `docs/improvement-plan.md`** - AI model
roles in `config/ai/models.yaml`, recorded cassettes so an eval runs without a
live provider, a quota-aware provider, and an updated disclosure. Phase 5
(PostgreSQL, row-level security, `hutch-sim` as a service) stays optional.

**Carried from Phase 3**, worth knowing before relying on sign-in:

- The signing key is generated in memory at startup, so **a restart signs
  everyone out**, and there is no refresh, revocation list or session store.
- The four-eyes path above LKR 25,000 is covered at the tool layer but is
  **not reachable over HTTP with the demo data**, whose largest case is
  LKR 12,000. A seeded case above the threshold would exercise it end to end.
- `/v1/demo/inbox` returns the OTP code, so all three `/v1/demo/*` routes are
  now gated by a `demo_only` dependency and 404 outside the demo profile. Only
  the demo profile is constructible today, so this is a guard for later.

**Things only the team can do:**

1. Record the demo video from [`docs/submission/DEMO_SCRIPT.md`](../../submission/DEMO_SCRIPT.md).
2. Fill the two `[Team to complete]` rows in [`docs/submission/AI_DISCLOSURE.md`](../../submission/AI_DISCLOSURE.md) (AI coding assistants used).
3. Add team name and track to deck slide 1, and a live-demo cue slide (plan §42.4).
4. Export the plan to the technical PDF (Guidelines §8) and Diagrams 1, 2, 7, 31 as images.
5. **Have a native Sinhala and Tamil speaker review every string** before anyone shows this to a customer.

1. Fill the **AI/LLM disclosure** with the models the prototype really uses, and replace assumed token counts with measured ones (§42.3, §37).
2. Export Diagrams 1, 2, 7 and 31 (Gantt) as PNG/PDF for the technical document.
3. Condense the plan into the concise **technical PDF** (Guidelines §8).
4. Add team name and track to deck slide 1, and add a live-demo cue slide (§42.4).
5. Decide whether to commit `docs/enterprise-plan/` and `agent.md` (create a branch first; `main` is the default branch).
6. Collect **REQUIRES HUTCH CONFIRMATION** items into a question list for HUTCH (assumptions register, §51).
