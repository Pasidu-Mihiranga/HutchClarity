# agent.md — Hutch Clarity project guide and change tracker

This file is the single source of truth for **what this repository is, how to work in it, and what has changed**. Any agent or contributor must read it before starting work and **update it at the end of every change** (see [Update protocol](#update-protocol)).

Last updated: 2026-10-02

---

## 0. Working economically (AI credits)

Development spends credits in the **coding agent**, not in the product. The
prototype configures no model (ADR-0009), so running it, its tests and
`make check` cost **zero tokens**. Keep it that way, and spend deliberately on
the agent.

**Read narrowly.**
- This file is long and the change log dominates it. Do not read it whole:
  `grep -n '^## ' agent.md`, then read only §0, §4, §6 and the §8/§9 status
  and next-step tables (`offset`/`limit`).
- Find code with `grep`/`rg` and read the lines you need, not whole modules.
  Never re-read a file you just edited; the edit tool errors if it failed.
- The plan in `docs/enterprise-plan/` is reference material. Open the one
  chapter a task cites, never the set.

**Verify cheaply, in this order.**
1. The single test file or `-k` expression for what you touched.
2. `make check` once, before finishing: lint, types, import contracts, all
   tests. It is free of model calls and quiet when green.
3. Browser-driven checks (Playwright) only for UI or auth-flow changes. Print a
   few result lines from the script, not page dumps or full logs.
Pipe long output through `tail`/`head`/`grep`; do not paste a full pytest run.

**Do not fan out unless asked.** No sub-agents, workflows or parallel research
for work one agent can do in-line; each one starts cold and re-reads context.
Batch independent tool calls into one turn instead.

**Match the model to the task.** Mechanical edits, renames, formatting, doc
updates and test fixes do not need the strongest model; switch with `/model`.
Keep the strongest one for design decisions, money-path code and security
review, where a wrong answer costs more than the credits saved.

**Keep records short.** Change-log rows: **3 sentences, under ~600
characters**, saying what changed and why; the detail belongs in the ADR, the
commit or the code. Do not rewrite or reflow old rows. Prefer editing one
section over regenerating a file.

**If a live model is ever configured** (the `OpenAICompatibleProvider`, P6.5):
- Develop and test against the template tier or recorded responses, never a
  live endpoint. Phase 4 of `docs/improvement-plan.md` adds cassettes for this:
  record once, replay in CI.
- Use a free tier or a small model; set a hard per-run and daily token cap.
- Run `scripts/measure_tokens.py` for real numbers rather than estimating, and
  record them in `docs/submission/AI_DISCLOSURE.md`.
- Never put a live-model call in a test that runs under `make check`.

**Stop and ask** before a task that would be expensive and open-ended (a
rewrite, a repo-wide audit, regenerating the plan). A one-line scope check is
cheaper than the wrong run.

---

## 1. Project in one paragraph

**Hutch Clarity** is a hackathon solution for HUTCH: one platform for customers and staff (website, Hutch app, WhatsApp, SMS/USSD, staff console) that **explains every rupee, fixes it by rule, and proves it won't happen again**. It has five modules: Clarity Copilot, Trust Receipt, Complaint Autopsy, Foresight and Clarity Desk.

This repository holds the two source documents, the enterprise project plan, and a **working prototype**: the deterministic core, tool layer, Trust Receipts, the `/v1` API and the three web pages all run end to end. **AI and MCP (P6) are the main thing still missing**, plus Autopsy, Foresight and the submission pack. See the backlog in §6a and the status table in §8.

## 2. Source documents (authoritative inputs)

| File | Role |
|---|---|
| `documents/Hutch Clarity (17 slides).pdf` | The authoritative project concept. Cite it as `[DECK Sx]` for slide *x*. |
| `documents/Hackathon_Final_Submission_Guidelines.docx` | Submission requirements: prototype, repo, README, technical PDF, architecture, integration feasibility, Gantt, AI/token disclosure, demo video. |

Do not edit these two files. If the deck and the plan conflict, the deck wins and the plan is fixed.

## 3. Repository layout

Legend: ☑ implemented · ☐ directory exists but is an empty placeholder.

```text
agent.md                         <- this file (guide + change log)
README.md                        <- ☑ root readme (setup, principle, limitations)
pyproject.toml                   <- ☑ Python 3.12, ruff, mypy strict, pytest
scripts/demo.py                  <- ☑ walks the 4 journeys end to end
rules/packs/*.yaml               <- ☑ 6 versioned rule packs (rules are data, not code)
tests/                           <- ☑ 387 tests (unit + golden + property + API + AI + MCP + contract parity)
src/clarity/
  schemas/                       <- ☑ domain models, money, canonical JSON + hashing
  integrations/                  <- ☑ adapter ports, registry, mock HUTCH world + drivers
  core/timeline/                 <- ☑ timeline builder (8-source join)
  core/rules/                    <- ☑ predicate language, pack loader, rule engine
  core/decision/                 <- ☑ decision policy + input assembler
  core/ids.py                    <- ☑ ULID/case/receipt identifiers
  core/tools/                    <- ☑ tool layer: plans, confirmation tokens, budget, execution
  core/receipts/                 <- ☑ signing, recurrence test, issue/verify, PNG/PDF render
  core/audit/                    <- ☑ append-only hash-chained ledger
  core/policy/                   <- ☑ resolver, switches, replay impact, governance
  core/content/                  <- ☑ CX-approved templates (si/ta/en)
  mcp/view.py                    <- ☑ narrow capability boundary for MCP
  core/cases/                    <- ☑ case service (orchestration for every channel)
  events/                        <- ☑ event envelope + catalogue + transactional outbox
  api/                           <- ☑ FastAPI /v1 (15 endpoints) + container
  ai/                            <- ☑ masking, verifier, templates, gateway, providers, autopsy, foresight
  mcp/                           <- ☑ MCP server: 8 tools, 3 profiles, policy, audit
src/clarity/api/static/          <- ☑ P7 UI: Why? page, verify page, Clarity Desk
infra/docker-compose/            <- ☐ local stack (empty)
documents/                       <- the two source documents (read-only)
docs/submission/                 <- ☑ AI disclosure, known limitations, demo script
docs/improvement-plan.md         <- comparison with the alternative design; Phases 0-2 implemented
docs/adr/                        <- ☑ 9 Architecture Decision Records
ARCHITECTURE.md                  <- ☑ as-built view (what exists vs what is planned)
Makefile                         <- ☑ make check: lint, types, import contracts, tests
config/policy/                   <- ☑ scoped, effective-dated policy artefacts
docs/enterprise-plan/            <- the Enterprise Project Plan (Markdown + Mermaid)
  README.md                      <- index, legend, reading paths, revision history, audit log
  01-executive-summary-problem.md           §1–2
  02-solution-capabilities.md               §3 (incl. 3.6 proactive, 3.7 guardian, 3.8 flow DSL)
  03-requirements-personas-journeys.md      §4–6
  04-enterprise-architecture.md             §7
  05-architecture-diagrams.md               §8 (Diagrams 1–18 + diagram index 8.1)
  06-integration-tmf.md                     §9
  07-mcp.md                                 §10–11
  08-ai-architecture.md                     §12
  09-rules-decision-receipts.md             §13–15 (incl. 14.4 financial controls)
  10-data-api-events.md                     §16–18
  11-security-privacy-audit.md              §19–20
  12-platform-devops-testing-observability.md  §21–25
  13-delivery-plan.md                       §26–32 (phases, WBS, Gantt, critical path, team, RACI, dependencies)
  14-risk-pilot-readiness-operations.md     §33–36
  15-cost-scale-failure-kpi.md              §37–40
  16-gap-submission-repo-docs.md            §41–45 (incl. 42.3–42.6 submission material)
  17-governance-compliance-change-cost.md   §46–52 (added by the v1.1 audit)
```

Current size: **52 sections, 39 Mermaid diagrams** (index in `05-architecture-diagrams.md` §8.1).

## 4. Non-negotiable design principles

Never change these without the user's explicit instruction.

1. **Rules decide. The LLM explains.** Only deterministic rules, OPA policy and the tool layer authorize or move money. The LLM handles language, retrieval, summaries, clustering labels and simulation narration.
2. **The LLM never executes L3 (financial/service-changing) or L4 (bulk/admin) actions.** Through MCP it may only *propose*. Confirmation comes from a customer tap or a staff approval, minted outside the LLM.
3. **Text is a hint, never evidence.** Evidence comes from trusted system records. Missing log → a human, never a guess.
4. **Works without the LLM.** Templates are the fallback.
5. **Preserve the deck's stack.** Change a technology only with the format *current → limitation → alternative → why* (see `04-enterprise-architecture.md` §7.2).
6. **Never invent HUTCH systems, APIs, credentials or results.** HUTCH systems are *categories* inferred from the deck. Simulated or assumed figures are never presented as measured.

## 5. Labelling conventions

| Label | Use |
|---|---|
| `[DECK Sx]` | Stated on slide *x* of the deck |
| `[PROPOSED]` | Expanded by the plan (inferred) |
| **ASSUMPTION** | Planning assumption (register: §51 in chapter 17) |
| **REQUIRES HUTCH CONFIRMATION** | Depends on a HUTCH system, policy or decision |
| **PROPOSED TARGET – REQUIRES HUTCH VALIDATION** | Numeric NFR/KPI target |
| *Illustrative* / *simulated* | Sample values, never measured |

Planning start date is the assumption **2027-01-04**. Production go-live is planned for 2027-11-22. The LLM stance is provider-agnostic: self-hosted open-weight model first, hosted tier as fallback on masked text.

## 5a. Writing conventions

- Markdown with tables; diagrams in **Mermaid** only.
- Section numbers (§N) are global across files. Cross-file references are relative links like `[§14.4](09-rules-decision-receipts.md)`.
- Every chapter starts and ends with a navigation line (previous · index · next). When adding a chapter, update the neighbours' navigation and the README document map.
- Use the `Guidelines §N` form for references to the hackathon guidelines, and `§N` for plan sections.

## 6. Update protocol

**After every change to this repository, before finishing:**

1. Append a row to the [Change log](#7-change-log) (newest first): date, what changed, files touched.
2. If the structure, counts or status changed, update sections 3, 8 and 9 of this file.
3. If a plan chapter changed, also update `docs/enterprise-plan/README.md` (revision history and, if applicable, the audit table).
4. If a diagram was added or removed: update the diagram index (`05-architecture-diagrams.md` §8.1), its count in the README text and the count in this file.
5. Run the checks in [Quality checks](#quality-checks).
5a. Follow [§0](#0-working-economically-ai-credits): targeted tests while working, one `make check` at the end, and a change-log row of 3 sentences.
6. Do **not** commit unless the user asks. When committing, follow the attribution lines the session specifies.

Claude Code loads `CLAUDE.md` / `AGENTS.md` automatically but not `agent.md`, so at the start of a session tell the agent to read this file (or add a one-line pointer file).

### Quality checks

Run these after editing the plan:

- **Mermaid:** every ` ```mermaid ` block must render. Extract blocks to `.mmd` files and run `npx -y @mermaid-js/mermaid-cli -i block.mmd -o block.svg` for each.
- **Links:** every relative link and `#anchor` in `docs/enterprise-plan/*.md` must resolve.
- **Numbering:** section headings `## N.` run 1…52 with no gaps or duplicates.
- **Counts:** the diagram count in this file and in the README matches the number of Mermaid blocks.
- **Integrity grep:** no text implies that HUTCH APIs exist, and no tool path lets the LLM execute L3/L4.

## 6a. Implementation backlog (todo list)

Target for the first build: **R0 — hackathon prototype**, scoped by `01-executive-summary-problem.md` §1.9. Status: ☐ todo · ◐ in progress · ☑ done.

### P1 — Foundation
- ☑ P1.1 Monorepo skeleton (pyproject, ruff, mypy strict, pytest, uv venv, py.typed)
- ☑ P1.2 `src/clarity/schemas` — canonical Pydantic v2 models + canonical JSON/hashing
- ☑ P1.3 `src/clarity/events` — envelope, catalogue, transactional outbox with retry/DLQ and idempotent consumers

### P2 — Mock HUTCH systems and adapters
- ☑ P2.1 `src/clarity/integrations/base.py` — read/command ports, driver modes, completeness, typed errors
- ☑ P2.2 Mock read drivers for all 8 sources + stateful command adapter (idempotent)
- ☑ P2.3 Synthetic world with the 4 demo journeys (`integrations/mocks/world.py`)

### P3 — Deterministic core ("rules decide")
- ☑ P3.1 Timeline builder: 8-source join, per-source completeness, evidence snapshot hash
- ☑ P3.2 Rule engine: predicate language with backtracking, pack loader, confidence, ranking, ruled-out
- ☑ P3.3 Rule packs (6 of 16): VAS_NO_CONSENT@4, DUPLICATE_RELOAD@2, RELOAD_NOT_CREDITED@1, FUP_CAP_REACHED@3, PACK_EXPIRY_BURN@2, DUPLICATE_VAS_CHARGE@1
- ☑ P3.4 Golden tests: positive, negative, boundary, property-based (21 golden + 93 others = 114)
- ☑ P3.5 Decision policy: full outcome matrix, caps, budgets, risk signals, hashed input, rationale
- ☑ P3.6 Tool layer: action plans, single-use confirmation tokens, staff approval with four-eyes, refund budget ledger, idempotent execution, compensation on partial failure

### P4 — Trust Receipts
- ☑ P4.1 Receipt payload/envelope, canonical hashing, hash chain, supersede-not-edit
- ☑ P4.2 Ed25519 dev signing service + public key publication + `verify_signature` (public material only)
- ☑ P4.3 Verification (hash, signature, ledger, chain), public view, SMS short form, recurrence test
- ☑ P4.4 PNG/PDF rendering in si/ta/en via Playwright, escaped input, no external loads

### P5 — API and persistence
- ☐ P5.1 Persistence layer (SQLAlchemy; SQLite for demo, PostgreSQL via compose) — **deferred**, stores are in-memory
- ☑ P5.2 FastAPI `/v1` endpoints + OpenAPI + RFC 9457 problem details
- ☑ P5.2a Case service: one orchestration shared by every channel
- ☑ P5.3 Append-only hash-chained audit ledger (tamper and deletion both detected) + outbox

### P6 — AI and MCP
- ☑ P6.1 PII masking + token vault: LK phone/NIC/passport recognizers, OTP/card/CVV **refused** not masked, TTL vault, audited restores
- ☑ P6.2 AI gateway: 4-tier routing (template → cache → small → reasoning), masking enforced before any call, template fallback, token accounting
- ☑ P6.3 Output verifier: invented numbers, unauthorised promises, leaked PII, invented tokens, wrong language
- ☑ P6.4 MCP server: 8 tools across 3 profiles, subject binding, no execute path, audited denials
- ☑ P6.5 `OpenAICompatibleProvider` for any vLLM/Ollama/hosted endpoint, configured by env. **None configured by default** — the template tier is the deck's "works without the LLM" path.

### P7 — Experience
- ☑ P7.1 Customer **Why?** page: pick a customer, ask, see cause + evidence + ruled-out, confirm in one tap
- ☑ P7.2 Public receipt verify page (QR target) + QR SVG endpoint
- ☑ P7.3 Clarity Desk: queue sorted by money at stake, case cockpit, approvals (incl. four-eyes)
- ◐ P7.4 Sinhala/Tamil UI copy: headings, buttons and explanations translate; some API-sourced strings (headline, action list) are still English

### P8 — Intelligence and submission
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

## 7. Change log

| Date | Change | Files |
|---|---|---|
| 2026-10-02 | Added §0 *Working economically (AI credits)*: read narrowly, targeted tests then one `make check`, no sub-agents unless asked, cheaper model for mechanical work, 3-sentence change-log rows, and recorded responses for any live model. The product itself already costs 0 tokens (ADR-0009). | `agent.md` |
| 2026-10-02 | **Implemented improvement plan Phase 3: identity and authorization** — the largest remaining gap, since every endpoint had been open. Added `core/iam/` (10 roles, 19 permissions, EdDSA tokens, OTP) and `api/auth.py`, where `requires(...)` is a dependency so a route cannot be mounted without declaring what it needs and `public()` is explicit rather than an omission. Customers sign in by OTP through a delivery port — the demo's port is a labelled simulated inbox, and the code never comes back from the request; staff pick roles from a labelled simulated identity provider. A customer token's subject is the `subscriber_ref` pseudonym, never the MSISDN, because tokens reach logs and proxies. **Writing the tests found four real authorization defects, all fixed:** `POST /v1/cases/{id}/proposals` had *no authentication at all*, so anyone could build an action plan — the step where amounts get attached — on any case; `approver_ref` came from the request body, so one person could approve twice under two names and satisfy four-eyes alone; `mfa_step_up` also came from the body, so the approval audit recorded whatever the client claimed; and the receipt read and render routes checked the permission but never the owner, leaving `RECEIPT_READ_ANY` as a scope-widener that was never consulted. Both body fields are now gone from `ApproveRequest` rather than left to be silently ignored, and identity facts come from the session. **Three further design errors corrected during the work:** a `CASE_READ_OWN`/`CASE_READ_ANY` split left staff without "own" (now a base `CASE_READ` plus a widener); `Clarity.reset()` signed everyone out (identity is not demo data); and `TokenIssuer.verify(now=...)` aged step-up while leaving expiry to the real clock, so an injected clock was only half honoured. Because the approver is now the token's subject, four-eyes needs two genuinely different people, so the Desk sign-in asks who you are. Verified in a real browser: OTP sign-in refuses a wrong code then accepts the right one and completes the Sinhala journey to a VERIFIED receipt; on the Desk an agent with step-up is refused the above-cap approval, a supervisor without step-up is refused, and a stepped-up supervisor completes it. 437 tests, `make check` green. | `src/clarity/core/iam/*`, `src/clarity/api/{auth,main,schemas,container}.py`, `src/clarity/api/static/*`, `tests/unit/test_iam.py`, `tests/unit/test_api.py`, `docs/adr/0010-*.md`, `docs/improvement-plan.md`, `ARCHITECTURE.md`, `docs/submission/{KNOWN_LIMITATIONS,DEMO_SCRIPT}.md` |
| 2026-10-02 | **Implemented improvement plan Phases 0-2.** **Phase 0 closed both defects:** the idempotency key is now claimed before the confirmation token is redeemed, so the reproduction went from 1,051 errors in 2,000 concurrent calls to **zero** (40 fresh, 1,960 replayed, one refund per trial); redemption and the mock adapter take locks instead of relying on the GIL; MCP now receives a narrow `MCPCaseView` with no execute capability, enforced by an AST scan of the package. **Phase 1** made policy scoped, effective-dated and guard-railed: decisions resolve `as_of` the disputed event and record a `config_snapshot_hash`, so "which caps applied when this happened" is answerable. **This corrected an earlier decision of mine:** I had raised the global auto-fix cap 1,000 -> 5,000 to make the deck's LKR 3,500 example work, loosening every rule; the global cap is back to 1,000 with a rule-scoped 3,500 for `DUPLICATE_RELOAD` under a 5,000 guardrail. Added kill switches (each degrades to staff, never to failure), a replay impact report, and maker-checker governance. **Phase 2** added 25 port parity tests, 4 import contracts, runtime profiles and 9 ADRs plus `ARCHITECTURE.md`. **Three further design problems were found while building and fixed rather than waived:** releasing an idempotency key on failure let a concurrent duplicate get a different error (outcomes are now final, ADR-0005); `with_override` appended instead of superseding, colliding with the value it replaced; and the import contracts exposed `events` importing `core.ids` (IDs are vocabulary, moved to `schemas`) and `core` importing `ai.templates` (CX content, moved to `core.content`). 387 tests, `make check` green. | `src/clarity/core/policy/*`, `src/clarity/core/tools/*`, `src/clarity/mcp/view.py`, `config/policy/`, `tests/contract/`, `docs/adr/`, `ARCHITECTURE.md`, `Makefile`, `pyproject.toml` |
| 2026-10-01 | **Compared with the alternative design in `HutchClarity-compair/`** (a friend's suggestion: a plan with 14 ADRs and no code, forked from our plan v1.0) and wrote `docs/improvement-plan.md`: adopt 14 ideas, adapt 6, skip 8, in 6 phases (~16 developer-days for the recommended Phases 0-4). Applying its checks to our code **found two real defects, not yet fixed**: (F1) under concurrency, 1,051 of 2,000 identical execute calls returned `ConfirmationInvalid`/`PlanNotPending` instead of the original result — money stayed safe, exactly one refund per trial, but single-use redemption relies on the GIL; (F2) the MCP server holds the full `CaseService`, so execute methods and `authorise_auto_fix` are reachable from MCP code — the "no execute path" test checks only tool names. Also corrected an error: the MCP server has **8** tools, not 7 as recorded earlier. No code changed. | `docs/improvement-plan.md`, `agent.md` |
| 2026-10-01 | **Closed out the deferred backlog.** P1.3 events (envelope, catalogue, transactional outbox with retry/DLQ and idempotent consumers). P5.3 append-only hash-chained audit ledger — altering *or deleting* a record is detected. P4.4 receipt rendering to PNG/PDF in si/ta/en via Playwright, with all input escaped and no external loads. P6.5 `OpenAICompatibleProvider` so any vLLM/Ollama/hosted endpoint works by env var. P7.4 Sinhala/Tamil UI copy (partial — API-sourced strings still English). P8.1 Complaint Autopsy, mask-first with clusters as hypotheses until reviewed. P8.2 Foresight on aggregates only, relative bands not counts, not decision-ready until backtested. P8.3 submission pack with **measured** token numbers. **Three real bugs found and fixed while doing it:** the receipt summary was internal English on a Sinhala receipt; the UI never passed the customer's language when opening a case, so Sinhala customers got English explanations; and an unclustered complaint vanished from the Autopsy report instead of being counted as noise. 309 tests, ruff and mypy --strict clean (58 files). | `src/clarity/events/*`, `src/clarity/core/audit/*`, `src/clarity/core/receipts/render.py`, `src/clarity/ai/{providers,autopsy,foresight}.py`, `src/clarity/api/static/*`, `docs/submission/*`, `scripts/measure_tokens.py` |
| 2026-10-01 | **P6 AI + MCP complete** (no model provider configured, P6.5). PII masking with Sri Lankan recognizers — and OTPs, card numbers and CVVs are **refused rather than masked**, with nothing from a refused message stored (deck S8). Token vault with TTL and audited restores. Deterministic output verifier that blocks invented amounts, promises the decision did not authorise, leaked PII, invented tokens and the wrong language. AI gateway with the deck's four-tier routing, masking enforced before any provider call, and a template fallback on verifier failure or provider outage. MCP server with 8 tools across 3 profiles: **no tool executes anything** — the strongest is `propose_action`, which takes no amount and creates a pending plan; subject binding stops one session reading another's case; every call and denial is audited. Explanations now appear in the UI in si/ta/en, and `/v1/ai/usage` reports measured (zero) token use. **No model is configured on purpose:** deck S7 says Clarity works without the LLM, and this is that path running for real. 260 tests (67 new), ruff and mypy --strict clean (50 files). | `src/clarity/ai/*`, `src/clarity/mcp/server.py`, `src/clarity/api/*`, `tests/unit/test_ai.py`, `tests/unit/test_mcp.py` |
| 2026-10-01 | **P7 UI complete** (si/ta copy deferred, P7.4). Driving the real UI in a browser found **a genuine bug the API tests had missed**: the Desk re-evaluates a case when opening it, which attempted an illegal state transition on an already-decided case and returned a 500. `evaluate` is now idempotent — reading a case never re-decides it, and an executed case keeps the decision its receipt cites. Also added `POST /v1/demo/reset` plus Reset buttons, since a demo has to be runnable twice in front of judges. Three pages on the existing `/v1` API: the customer **Why?** journey (pick a synthetic customer → ask → cause, evidence, ruled-out causes and policy rationale → confirm in one tap → Trust Receipt with QR), the **public verify page** the QR opens, and **Clarity Desk** (queue by money at stake, case cockpit, supervisor/finance approval incl. four-eyes). Added a QR SVG endpoint that encodes only the public verify URL. **Stack note:** plain HTML + vanilla JS served by FastAPI instead of Next.js, so the whole prototype runs from one command with no Node toolchain; recorded as a prototype simplification since the pages only consume the public API. Verified in a real browser with Playwright. | `src/clarity/api/static/*`, `src/clarity/api/main.py`, `pyproject.toml` |
| 2026-10-01 | **P5 API complete** (P5.1 persistence deferred). Added the case service — the shared orchestration every channel uses, so the money path is identical wherever the customer starts — and a FastAPI `/v1` with 15 endpoints, OpenAPI and RFC 9457 problem details. Risk signals are now **derived from evidence** (SIM swap from the identity source, repeat refunds from the ledger) instead of being passed in, so no caller can soften a risk flag. Safeguard parameters likewise come from the matched events, so a block cannot be redirected onto another merchant. Two deliberate tightenings of §17.2: confirmation tokens are minted and spent inside the request so they never reach a client, and amounts are never accepted from a client. Verified over real HTTP end to end, including QR verification. 189 tests (22 new, incl. HTTP-boundary guards), ruff and mypy --strict clean (44 files). | `src/clarity/core/cases/service.py`, `src/clarity/api/*`, `src/clarity/core/decision/assessor.py`, `tests/unit/test_api.py` |
| 2026-10-01 | **P4 Trust Receipts complete** (except PNG/PDF rendering, P4.4). Receipt payload is split from its envelope so verification is unambiguous: re-canonicalize, recompute the hash, check the Ed25519 signature against published public keys. Receipts chain to their predecessor, are never edited (corrections supersede), and cite evidence by id + hash rather than copying records. The recurrence test re-reads live state through a probe, so "PASSED" means the merchant block is genuinely in force — an unavailable probe reports UNAVAILABLE, never an optimistic pass. Added the public QR view (narrow by design) and the SMS short form. `scripts/demo.py` now ends each journey with an issued, verified receipt. 167 tests (22 new, incl. tamper/forgery/wrong-key), ruff and mypy --strict clean (40 files). | `src/clarity/schemas/receipt.py`, `src/clarity/core/receipts/*`, `src/clarity/integrations/mocks/recurrence.py`, `tests/unit/test_receipts.py`, `scripts/demo.py` |
| 2026-10-01 | **P3.6 tool layer complete.** Added `core/tools/`: action plans (one remedy = one plan, so "refund + switch off + block merchant" is one tap), single-use plan-bound confirmation tokens minted outside the AI path, staff approval with MFA step-up, maker≠checker and four-eyes above LKR 25,000, a refund budget ledger with reserve/commit/release, idempotent execution, and compensation on partial failure (a refund is never clawed back). Replaced the unused singular `Proposal` schema with `ActionPlan`/`PlanStep`/`PlanStatus`. `scripts/demo.py` now runs propose → confirm → execute for all four journeys. 145 tests (31 new), ruff and mypy --strict clean. | `src/clarity/core/tools/*`, `src/clarity/schemas/decision.py`, `tests/unit/test_tool_layer.py`, `scripts/demo.py` |
| 2026-10-01 | Corrected two stale statements in this file: §1 still said the repo contained no prototype code, and §3 listed only the docs. Both now reflect the partial prototype, and §3 marks every module as implemented or placeholder. Verified against the filesystem: P3.6 and P4–P8 directories contain only empty `__init__.py`. | `agent.md` |
| 2026-10-01 | **Implementation started: P1, P2, P3 (except the tool layer).** Built the deterministic core end to end — canonical schemas (Decimal money, pseudonymous subscriber refs, canonical JSON + hash chaining), the adapter framework with mock drivers for all 8 sources, a stateful synthetic HUTCH world covering the 4 demo journeys, the timeline builder, a declarative rule engine with 6 rule packs, and the decision policy. 114 tests pass; ruff and mypy --strict are clean. Added `scripts/demo.py`, which walks all four journeys. **Plan change:** raised the auto-fix cap from LKR 1,000 to LKR 5,000 (and the one-tap cap to LKR 10,000) because the deck's own zero-contact example is a LKR 3,500 double reload `[DECK S2, S5]`; §14.2 updated to match. | `pyproject.toml`, `README.md`, `src/clarity/**`, `rules/packs/*.yaml`, `tests/**`, `scripts/demo.py`, `docs/enterprise-plan/09-rules-decision-receipts.md` |
| 2026-10-01 | Created `agent.md` with the project guide, conventions, update protocol and change log. | `agent.md` |
| 2026-10-01 | **Plan audit (v1.1).** Found 24 gaps against the brief, the guidelines and the deck. Added: prototype scope (§1.9); proactive care engine (§3.6); personalization and guardian (§3.7); flow DSL (§3.8); FR-COP-15, FR-CH-05, FR-TR-07, FR-GOV-04/05; NFR-PERF-06, NFR-PRV-03, NFR-COST-01; shop-staff and external-verifier personas; Before/During/After (§6.7); channel constraints (§9.7); forecast disclosures (§12.9); financial controls and reconciliation (§14.4); data governance (§16.3); test data (§24.1); SLOs (§25.4); benefits measurement (§40.1); AI disclosure template, slide mapping, demo storyboard, readiness checklist (§42.3–42.6); new chapter 17 (§46–52: governance, release plan and traceability, compliance, change management, effort/TCO, assumptions register, post-production support). Diagrams 35–39 added. Gantt axis label changed to `%b %Y`. README duplicate tagline fixed. All 39 diagrams render and all links resolve. | `docs/enterprise-plan/01`–`03`, `05, 06, 08, 09, 10, 12, 15, 16`, new `17`, `README.md` |
| 2026-10-01 | **Plan v1.0 added to the repo.** The approved plan was split into 16 chapter files plus a README index, with 34 Mermaid diagrams. | `docs/enterprise-plan/*` |

## 8. Current status

| Item | Status |
|---|---|
| Enterprise plan (52 sections, 39 diagrams) | Complete, v1.1 (audited) |
| Diagram rendering | All 39 render with mermaid-cli 11 |
| Link integrity | 0 broken links |
| Git | Nothing committed. Everything is untracked on `main`. |
| Deterministic core, tool layer, Trust Receipts, API, web + Desk | **Working end to end.** `.venv/bin/uvicorn clarity.api.main:app` → `/` customer, `/desk` staff, `/v/{id}` public check |
| Tests / lint / types | **437 passing** · `make check` green: ruff, `mypy --strict` (71 files), 4 import contracts |
| AI + MCP (P6) | **Working.** Masking, verifier, gateway, provider and MCP server. **No model is configured** — explanations come from CX-approved templates, so measured token use is 0. |
| Events, audit ledger, Autopsy, Foresight, receipts PNG/PDF, submission pack | **Working** |
| Policy governance (Phase 1) | **Working.** Scoped, effective-dated caps with guardrails; kill switches; replay impact report; maker-checker approval |
| Boundaries (Phase 2) | **Working.** Port parity suites, import contracts, runtime profiles, 10 ADRs |
| Identity and authorization (Phase 3) | **Working.** EdDSA tokens, 10 roles and 19 permissions, deny-by-default routes, subject binding on cases and receipts, step-up before an above-cap approval, OTP sign-in for customers, role picker for the Desk. The permission model is production-shaped; **the issuer is ours**, so the role picker and SMS inbox are labelled as simulated (ADR-0010). |
| Remaining | P5.1 persistence (in-memory), P7.4 partial si/ta copy, RAG, real channels, voice, guardian |
| Demo video, test credentials | **Not in this repo** — team to confirm (`16-gap-submission-repo-docs.md` §42) |
| AI usage declaration | Draft. Real model names and measured token counts still need filling in (§42.3) |
| Technical PDF for submission | Not generated. The plan must be condensed to the Guidelines §8 structure. |

## 9. Open items and next steps

**The prototype is now demonstrable end to end.** `.venv/bin/uvicorn clarity.api.main:app` then open <http://localhost:8000/> for the customer journey, `/desk` for staff, `/v/TR-2027-000001` for public verification, `/docs` for the API.

**The R0 prototype backlog is complete** apart from two deliberate items:

| Item | Why it is still open |
|---|---|
| **P5.1 persistence** | In-memory stores. A restart loses all cases and receipts. Adding SQLAlchemy is additive — the services already sit behind clean interfaces — but nothing in the demo needs durability. |
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

1. Record the demo video from [`docs/submission/DEMO_SCRIPT.md`](docs/submission/DEMO_SCRIPT.md).
2. Fill the two `[Team to complete]` rows in [`docs/submission/AI_DISCLOSURE.md`](docs/submission/AI_DISCLOSURE.md) (AI coding assistants used).
3. Add team name and track to deck slide 1, and a live-demo cue slide (plan §42.4).
4. Export the plan to the technical PDF (Guidelines §8) and Diagrams 1, 2, 7, 31 as images.
5. **Have a native Sinhala and Tamil speaker review every string** before anyone shows this to a customer.

1. Fill the **AI/LLM disclosure** with the models the prototype really uses, and replace assumed token counts with measured ones (§42.3, §37).
2. Export Diagrams 1, 2, 7 and 31 (Gantt) as PNG/PDF for the technical document.
3. Condense the plan into the concise **technical PDF** (Guidelines §8).
4. Add team name and track to deck slide 1, and add a live-demo cue slide (§42.4).
5. Decide whether to commit `docs/enterprise-plan/` and `agent.md` (create a branch first; `main` is the default branch).
6. Collect **REQUIRES HUTCH CONFIRMATION** items into a question list for HUTCH (assumptions register, §51).
