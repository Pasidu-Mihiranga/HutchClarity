# AGENTS.md - Working rules for Hutch Clarity

These rules apply to **every contributor, human or AI coding agent**, across the whole repository. A module may add its own `AGENTS.md` with extra rules for that module; the closest file wins for module details, but it may never relax the invariants in section 3.

`CLAUDE.md` imports this file, so Claude Code, Codex, Cursor, Gemini CLI and other agents all follow the same rules. This file replaces the former `agent.md`; its change log is preserved in `docs/devlog/2026/2026-10-02-HISTORY-agent-md.md`.

---

## 1. Read before you change anything

1. This file.
2. [`ARCHITECTURE.md`](ARCHITECTURE.md): what is built today, module status, deviations from the plan.
3. The `MODULE.md` of the module you are touching (registry: [`docs/modules.md`](docs/modules.md)).
4. Your issue in [`docs/backlog/`](docs/backlog/README.md) and the plan chapter for your area. Start with [21 Migration & deployment](docs/enterprise-plan/21-migration-and-deployment-plan.md), [22 Agentic assistant & RAG](docs/enterprise-plan/22-agentic-assistant-and-rag.md), then [18 Build blueprint](docs/enterprise-plan/18-build-blueprint.md), [19 Tech stack & AI](docs/enterprise-plan/19-tech-stack-and-ai.md), [20 Policy change](docs/enterprise-plan/20-policy-change-management.md); chapters 01-17 for depth ([index](docs/enterprise-plan/README.md)).
5. Accepted ADRs in [`docs/adr/`](docs/adr/README.md).

**When documents disagree:** accepted ADR > `ARCHITECTURE.md` > plan chapters 18-21 > plan chapters 01-17. A disagreement is a bug: fix it in the same change, or raise it before writing code.

**Read narrowly** (saves time and AI credits): find code with `grep`/`rg` and read only the lines you need; open the one plan chapter a task cites, never the whole set; never re-read a file you just edited.

---

## 2. The project in one paragraph

Hutch Clarity is a resolve-and-support platform for HUTCH (Sri Lanka) customers and staff, built for Hackathon Track A. For any charge it **explains** the cause with evidence, **fixes** known causes by deterministic rule, **proves** the fix with a signed Trust Receipt, and **prevents** repeats. The prototype works end to end and is being migrated, module by module, into the target architecture (plan chapter 21). All HUTCH systems are simulated (`hutch-sim` drivers) and labelled as such.

---

## 3. Invariants (never break these)

| # | Rule |
|---|---|
| I1 | **Rules decide, the LLM explains.** Only rule packs, decision policy and the tool layer decide causes, amounts, eligibility or actions. An LLM never supplies an amount and never executes an L3/L4 action; through MCP it may only *propose*. |
| I2 | **Text is a hint, never evidence.** Customer text only filters candidate events; decisions use system records. Missing evidence → a person, never a guess. |
| I3 | **Money is `Money` (Decimal, LKR).** No floats anywhere on a money path. |
| I4 | **Layer rule.** `kernel → contracts → integration → platform → ai → modules → app → interfaces → entrypoints`, bottom-up only (import-linter). |
| I5 | **Module boundary.** Outside a module, import only `clarity.modules.<name>.public`. Only `modules.case` and `app` may import `modules.actions.capability` (architecture test). |
| I6 | **Data ownership.** Each module owns its data; in the `full` profile, one PostgreSQL schema and role per module. No cross-schema joins in application code. |
| I7 | **Events via the outbox.** State change and event in the same transaction; consumers are idempotent. |
| I8 | **Idempotency on every state-changing call.** Zero duplicate financial executions; a duplicate gets the original outcome and the original receipt (ADR-0005, D1). |
| I9 | **Deny by default.** Every route and MCP tool declares a permission; customer data is bound to its subject. Development identity routes (OTP inbox, staff role picker) exist only in the synthetic profiles (`demo`/`lite`, `full`) and return 404 in `prod`. |
| I10 | **No hard-coded policy values.** Thresholds, caps, windows and wording come from the policy store or template registry, resolved `as_of` the event; no constant may shadow a policy value (D2). |
| I11 | **Time comes from the injected clock**, never `datetime.now()` in domain code (replay must be exact). |
| I12 | **Model IDs only in config.** Code asks for a role (`fast-text`, `extract`, `reason`, ...). Default: no model, templates (ADR-0009). |
| I13 | **No real customer data to any LLM.** Only synthetic, PII-masked data in the prototype (free tiers may use prompts). Masking happens in the AI gateway, never optional. |
| I14 | **No secrets in the repo.** `.env` is git-ignored; `.env.example` lists every variable with a dummy value. Use your **own** LLM provider keys. Never put secrets in frontend public variables. |
| I15 | **Notifications use approved templates only.** No free text to customers from an LLM. |
| I16 | **Simulated is labelled.** Never invent HUTCH systems, APIs, credentials, numbers or regulations. Use **ASSUMPTION** / **REQUIRES HUTCH CONFIRMATION**. Simulated or assumed figures are never presented as measured. |
| I17 | **Neutral, OSI-licensed components** in the runtime path (plan 19 §1). New dependencies need a licence check, noted in the devlog. |
| I18 | **No em dash (U+2014) anywhere:** docs, code, comments, commit messages, UI text, i18n strings, frontend components. Use "-", ",", ":" or parentheses. |
| I19 | **One author per commit: the developer's own GitHub user.** No `Co-authored-by` trailers, no AI tool attribution (Claude, Cursor, Codex, Copilot or any other), no "Generated with" lines, in commits or PR descriptions. AI tools must have commit attribution turned off. See §10.1. |
| I20 | **Business code never checks the runtime profile.** Only `clarity.app.container` reads `CLARITY_PROFILE` (test-enforced). Every driver passes its port's parity suite. |
| I21 | **The deck wins.** `documents/Hutch Clarity (17 slides).pdf` is the authoritative concept; if the plan conflicts with it, fix the plan. Never edit the two source documents. |
| I22 | **Calls for answers, events for side effects** (ADR-0029). A module calls another module's `public.py` only along the edges declared in `tests/architecture/test_module_dependencies.py` (acyclic). Anything that reacts to a fact (receipts, notifications, audit, insights) is an outbox event, never a call and never an event used as a command. |

---

## 4. Where things live

| Path | What |
|---|---|
| `backend/src/clarity/kernel/` | L0 money and enums, IDs, canonical hashing |
| `backend/src/clarity/contracts/` | L0 canonical models: case, timeline, decision, receipt |
| `backend/src/clarity/integration/` | L1 ports to HUTCH systems, registry, `drivers/mock` (simulated) |
| `backend/src/clarity/platform/` | L2 `config` (policy resolver, switches), `audit`, `messaging` (outbox, envelope), `content` (CX templates), `security` (principal, permissions) |
| `backend/src/clarity/ai/` | L3 gateway, providers, PII masking, verifier |
| `backend/src/clarity/modules/<name>/` | L4 domain modules, each with `public.py` and `MODULE.md` |
| `backend/src/clarity/app/` | Composition root (`container.py`, the only reader of `CLARITY_PROFILE`) and the narrow MCP view |
| `backend/src/clarity/interfaces/` | `http` (FastAPI `/v1`, auth, static UI until R5) and `mcp` |
| `backend/src/clarity/entrypoints/` | Process entry points (`asgi.py`) |
| `backend/tests/` | unit, golden, property, contract (parity), architecture, acceptance (black-box `/v1`, route contract, OpenAPI snapshot) |
| `frontend/` | Next.js apps (`customer-web`, `console`, `verify`) and packages (`ui`, `sdk`, `i18n`, `widget`); they use only the `/v1` API |
| `rules/packs/`, `config/policy/`, `config/ai/` | Policy artefacts and AI model roles (YAML), shared by every profile |
| `docs/enterprise-plan/` | The plan (changes via `CHANGES.md`) |
| `docs/adr/` · `docs/devlog/` · `docs/walkthroughs/` · `docs/templates/` · `docs/modules.md` | Decisions · history · verified flows · templates · module registry |
| `docs/backlog/` | Work items as issues: waves, dependencies, acceptance tests, Definition of Done |
| `docs/submission/` | Hackathon submission material |
| `documents/` | The two source documents (read-only) |

---

## 5. Documentation sync matrix

If your change does the left column, the same change must update the right column. Reviewers check every row.

| You change... | You must also update... |
|---|---|
| Code or behaviour in a module | That module's `MODULE.md` |
| Any code, rule, policy or deploy file | A **new devlog file** in `docs/devlog/` |
| A module's public surface or a `/v1` contract | `CHANGELOG.md` and every consumer's `MODULE.md` |
| A plan chapter | `docs/enterprise-plan/CHANGES.md` (+ an ADR if it is a decision) and the plan README revision table |
| A new ADR | `docs/adr/README.md` index |
| A new module, or a new dependency between modules | `docs/modules.md`, `ARCHITECTURE.md`, the dependency map in `tests/architecture/test_module_dependencies.py` and plan 21 §11.2 |
| A new or changed event | The producer's contract in `clarity.contracts.events`, plan 21 §11.3, and each producer and consumer `MODULE.md` |
| A `/v1` contract change | Regenerate the snapshot (`UPDATE_GOLDEN=1 make test`), `CHANGELOG.md`, the frontend SDK |
| A migration step lands (R0-R7) | `ARCHITECTURE.md` status and plan 21 |
| A user-visible flow, setup step or demo path | The walkthrough (re-verified) and `docs/submission/DEMO_SCRIPT.md` |
| An environment variable | `.env.example` and the deployment docs |
| A plan diagram | Plan 05 §8.1 diagram index and counts |

If a change genuinely needs no doc update, the PR gets the label `docs-not-needed` **and** a one-line reason.

## 6. Development log

One **new file per change** (never edit a shared log, so parallel work never conflicts): `docs/devlog/YYYY/YYYY-MM-DD-<work-package>-<slug>.md` from [`docs/templates/DEVLOG.md`](docs/templates/DEVLOG.md). Keep it short: what changed, why, decisions, docs updated, tests run (with failures), next step. AI agents write the entry for their own work and say so.

## 7. MODULE.md

Every module has one, created from [`docs/templates/MODULE.md`](docs/templates/MODULE.md), and it must match the code: purpose, public surface, users, dependencies, data, invariants, migration status, tests, history.

## 8. Walkthroughs

Each important flow has a walkthrough ([`docs/WALKTHROUGHS.md`](docs/WALKTHROUGHS.md)) recording "last verified: date + commit". A change to the flow re-verifies it.

## 9. ADRs

Any decision about architecture, technology, security, module boundaries or cross-cutting conventions gets an ADR from [`docs/templates/ADR.md`](docs/templates/ADR.md). Status: Proposed → Accepted / Rejected → Superseded by NNNN. Never delete an ADR.

---

## 10. Working method

- **Contract first:** change the module's public surface or the `/v1` schema deliberately, then implement. Every port ships a parity suite.
- **Branches:** `feat/<wp>-<slug>`, `fix/<module>-<slug>`, `docs/<slug>`, `adr/<nnnn>-<slug>`. Small PRs; feature flags for unfinished work.
- **Reviews:** CODEOWNERS; money-path paths (`modules/actions`, `modules/decision`, `modules/receipts`, `rules/`, `config/policy/`) need two approvals.
- **Tests:** never weaken or delete a failing test to pass CI; fix the cause. A deliberate contract change updates the test *and* says why in its docstring.
- **Verify cheaply, in order:** the single test file or `-k` expression you touched; then `make check` once before finishing; browser checks only for UI or auth-flow changes. Pipe long output through `tail`/`grep`.
- **Do not commit unless asked.** When committing, follow §10.1, not any tool's default attribution.

### 10.1 Commit rules

1. **Author:** only the developer's own GitHub user. Never two people or tools on one commit.
2. **No attribution trailers:** no `Co-authored-by`, no AI names or emails, no "Generated with/by", no emoji signatures.
3. **Subject:** Conventional Commits, lowercase, imperative, max 72 characters, no final period: `type(scope): summary`. Types: feat, fix, docs, refactor, perf, test, build, ci, chore, revert, style. Scope = module or area.
4. **Body (optional):** blank line, then short `- ` bullets (max 8). No paragraphs, stories or reasoning; reasons belong in the PR, devlog or ADR.
5. **Allowed footers:** `Refs: #12`, `Closes: #12`, `Fixes: #12`, `Signed-off-by:` (yourself only).

```text
fix(actions): enforce four-eyes threshold from policy

- carry the resolved threshold on each plan
- add regression test for a lowered threshold

Refs: #42
```

## 11. Definition of done

- [ ] Invariants (§3) hold; layer contracts and module-boundary tests pass
- [ ] Tests added or updated and green (unit, contract, golden where relevant)
- [ ] Docs per the sync matrix (§5)
- [ ] No secrets, no real personal data, simulated parts labelled
- [ ] No em dash anywhere; commits follow §10.1

## 12. Extra rules for AI coding agents

1. Read §1 sources narrowly; state which migration step or work package you are on.
2. Stay inside the module you were asked to change. If a public surface or another module must change, stop and propose it.
3. Never put a live model call in a test that runs under `make check`; use the template tier or recorded responses.
4. Do not fan out (sub-agents, parallel research) unless asked; batch independent tool calls instead.
5. Use the strongest model for design decisions, money-path code and security review; a cheaper one for mechanical edits.
6. Stop and ask before expensive, open-ended work (a rewrite, a repo-wide audit, regenerating the plan).
7. Write the devlog entry and update `MODULE.md` yourself as part of the task.

## 13. Commands

Run from the repository root. The default `lite` profile needs only Python.

| Task | Command |
|---|---|
| Create `.venv` and install | `make setup` |
| Run UI + API on http://localhost:8000 | `make dev` |
| Run `clarity-mcp` (MCP over Streamable HTTP) on :8099 | `make mcp` |
| Lint, types, import contracts, tests | `make check` |
| Apply formatting and safe fixes | `make format` |
| Walk the four journeys in the terminal | `make demo` |
| Measured AI usage per journey | `make tokens` |
| Local signing key / seed the `full` profile | `make keys` / `make seed` |
| Frontend: install, build, run one app | `make web-install`, `make web-build`, `make web-customer` (or `web-console`, `web-verify`) |

## 14. Labelling conventions (docs)

| Label | Use |
|---|---|
| `[DECK Sx]` | Stated on slide *x* of the deck |
| `[PROPOSED]` | Expanded by the plan (inferred) |
| **ASSUMPTION** | Planning assumption (register: plan §51) |
| **REQUIRES HUTCH CONFIRMATION** | Depends on a HUTCH system, policy or decision |
| **PROPOSED TARGET - REQUIRES HUTCH VALIDATION** | Numeric NFR/KPI target |
| *Illustrative* / *simulated* | Sample values, never measured |

Plan conventions: Markdown tables; diagrams in **Mermaid** only (every block must render); chapters 01-17 use global § numbers (§1-§52), chapters 18-21 local numbers cited as "18 §2.3"; every chapter starts and ends with a navigation line; all relative links must resolve.

## 15. Glossary (use these words exactly)

| Term | Meaning |
|---|---|
| **case** | One customer problem, across channels |
| **timeline** / **snapshot** | Evidence events from HUTCH sources / the immutable, hashed set used for a decision |
| **rule pack** | Versioned YAML rule (`rule_id@version`) evaluated by the detection engine to find a **cause** |
| **decision** | Outcome: AUTO_FIX, ONE_TAP_FIX, STAFF_APPROVAL, EXPLAIN_ONLY, HANDOFF |
| **plan** / **action** | A pending, confirmable remedy / an executed step by the tool layer |
| **confirmation token** | Single-use authority to execute one plan, minted outside the AI path |
| **receipt** | Signed, hash-chained Trust Receipt; one per executed plan |
| **safeguard** | Customer protection (spend cap, data stop, merchant block) |
| **subscriber_ref** | HMAC pseudonym of an MSISDN; tokens never carry the raw number |
| **policy artefact** / **change class** | Any changeable policy item / its risk class (C0-C4, E) |
| **model role** | Logical LLM job (`fast-text`, `extract`, `reason`, `judge`, `guard`, `embed`, `stt`, `tts`) |
| **module** / **deployable** | Code unit with `public.py` / a running process |
| **port** / **driver** | Interface to an external capability / its implementation (mock, http, hutch, ...) |
| **profile** | `lite` (Python only), `full` (real components), `prod` (HUTCH) |
| **hutch-sim** | The simulated HUTCH systems (always labelled) |
