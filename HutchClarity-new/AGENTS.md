# AGENTS.md - Working rules for Hutch Clarity

These rules apply to **every contributor, human or AI coding agent**, across the whole repository. A module may add its own `AGENTS.md` with extra rules for that module; the closest file wins for module-specific details, but it may never relax the invariants in §3.

`CLAUDE.md` imports this file, so Claude Code, Codex, Cursor, Gemini CLI and other agents all follow the same rules.

---

## 1. Read before you change anything

1. This file.
2. [`ARCHITECTURE.md`](ARCHITECTURE.md): the current, living architecture and module status.
3. The `MODULE.md` of the module you are touching (registry: [`docs/modules.md`](docs/modules.md)).
4. The plan chapter for your area: [17 Build blueprint](enterprise-plan/17-build-blueprint.md), [18 Tech stack & AI](enterprise-plan/18-tech-stack-and-ai.md), [19 Policy change](enterprise-plan/19-policy-change-management.md), and for depth chapters 01–16 ([index](enterprise-plan/README.md)).
5. Accepted ADRs in [`docs/adr/`](docs/adr/README.md).

**When documents disagree:** accepted ADR > `ARCHITECTURE.md` > plan chapters 17–19 > plan chapters 01–16. A disagreement is a bug. Fix it in the same PR, or raise it before writing code.

---

## 2. The project in one paragraph

Hutch Clarity is a resolve-and-support platform for HUTCH (Sri Lanka) customers and staff, built for Hackathon Track A. For any charge it **explains** the cause with evidence, **fixes** known causes by deterministic rule, **proves** the fix with a signed Trust Receipt, and **prevents** repeats. It is built as an **enterprise-grade, deployment-agnostic prototype**: production-grade code, swappable infrastructure, all HUTCH systems simulated behind ports by `hutch-sim`.

---

## 3. Invariants (never break these)

| # | Rule |
|---|---|
| I1 | **Rules decide, the LLM explains.** Only detectors, decision tables and the tool layer decide causes, amounts, eligibility or actions. An LLM never supplies an amount and never executes an L3/L4 action. |
| I2 | **Text is a hint, never evidence.** Customer text only filters candidate events; decisions use system records. Missing evidence → handoff, never a guess. |
| I3 | **Money is `Money` (Decimal, LKR).** No floats anywhere on a money path. |
| I4 | **Layer rule.** A layer imports only from layers below it (L0 kernel → L1 integration → L2 platform → L3 AI → L4 modules → L5 identity → L6 interfaces → L7 experience). Enforced by `import-linter`. |
| I5 | **Module boundary.** Other modules may import only `public.py`. No imports of another module's `domain/` or `infrastructure/`. |
| I6 | **Data ownership.** Each module owns one Postgres schema and DB role. No cross-schema joins in application code. |
| I7 | **Events via the outbox.** State change + event in the same transaction. Consumers are idempotent. |
| I8 | **Idempotency on every state-changing call** (`Idempotency-Key`). Zero duplicate financial executions. |
| I9 | **Deny by default.** Every route, consumer and MCP tool declares a permission; OPA decides; customer data is also protected by row-level security. |
| I10 | **No hard-coded policy values.** Thresholds, caps, windows and wording come from the config resolver / template registry with `as_of` time ([19](enterprise-plan/19-policy-change-management.md)). |
| I11 | **Time comes from `Clock`**, never `datetime.now()` in domain code (replay must be exact). |
| I12 | **Model IDs only in `config/ai/models.yaml`.** Code asks for a role (`fast-text`, `extract`, `reason`, …). |
| I13 | **No real customer data to any LLM**, and only synthetic, PII-masked data in the prototype (free tiers may use prompts). Masking happens in the AI gateway, never optional. |
| I14 | **No secrets in the repo.** Use `.env` (git-ignored) locally; `.env.example` lists every variable with a dummy value. Use your **own** LLM provider keys. Never put secrets in `NEXT_PUBLIC_*` variables. |
| I15 | **Notifications use approved templates only.** No free text to customers from an LLM. |
| I16 | **Simulated is labelled.** Anything mocked (HUTCH systems, data, OTP) says so in code, UI and docs. Never invent real HUTCH APIs or present them as real. |
| I17 | **Neutral, OSI-licensed components** in the runtime path ([18 §1](enterprise-plan/18-tech-stack-and-ai.md)). New dependencies need a licence check. |
| I18 | **No em dash (U+2014) anywhere:** docs, code, comments, commit messages, UI text, i18n strings and frontend components. Use "-", ",", ":" or parentheses. |
| I20 | **Business code never checks the runtime profile.** Only the composition root reads `CLARITY_PROFILE` and binds drivers (`lite`, `full`, `prod`; [17 §2.3](enterprise-plan/17-build-blueprint.md), ADR-0014). Every driver passes its port's parity suite. |
| I19 | **One author per commit: the developer's own GitHub user.** No `Co-authored-by` trailers, no AI tool attribution (Claude, Cursor, Codex, Copilot or any other), no "Generated with" lines, in commits or PR descriptions. See §10.1. |

---

## 4. Where things live

| Path | What |
|---|---|
| `enterprise-plan/` | Versioned plan (changes via [`enterprise-plan/CHANGES.md`](enterprise-plan/CHANGES.md)) |
| `ARCHITECTURE.md` | Living architecture + module status (as built) |
| `docs/adr/` | Architecture Decision Records |
| `docs/modules.md` | Module registry (owner, status, links) |
| `docs/WALKTHROUGHS.md`, `docs/walkthroughs/` | Step-by-step walkthroughs of real flows |
| `docs/devlog/` | Development log, one file per change |
| `docs/templates/` | Templates for MODULE.md, ADR, devlog, walkthrough |
| `backend/src/clarity/{kernel,platform,integration,ai,modules}` | Python layers L0–L4 (after scaffolding) |
| `services/` | Separately deployed services (mcp, signer, ai-gateway, channel-gateway, hutch-sim) |
| `frontend/` | Next.js apps and shared packages |
| `contracts/` | OpenAPI, AsyncAPI, JSON Schema (source of truth for interfaces) |
| `rules/`, `config/`, `templates/` | Policy artefacts (detectors, tables, parameters, wording) |
| `deploy/` | Compose, Helm, OpenTofu reference deployments |

---

## 5. Documentation sync matrix (the core consistency rule)

If your change does the left column, the same PR must update the right column. Reviewers check every row; rows marked ⚙ are the ones most often missed.

| You change… | You must also update… |
|---|---|
| Any code or behaviour in a module/service/app ⚙ | That unit's `MODULE.md` (relevant sections) |
| Any code, contract, rule, config or deploy file ⚙ | A **new devlog entry** in `docs/devlog/` |
| A contract (`contracts/`) ⚙ | `CHANGELOG.md` (+ semver bump of the contract) and every consumer's `MODULE.md` dependency table |
| A plan chapter in `enterprise-plan/` ⚙ | `enterprise-plan/CHANGES.md` (+ an ADR if it is a decision) |
| A new ADR ⚙ | `docs/adr/README.md` index |
| A new module/service/app ⚙ | `docs/modules.md` and `ARCHITECTURE.md` module map |
| A dependency between modules (new call or event subscription) | `ARCHITECTURE.md` module map + both modules' `MODULE.md` |
| A user-visible flow, setup step or demo path | The affected walkthrough (and re-verify it) |
| An environment variable | `.env.example` and the deployment docs |
| A permission or config key | The module's `MODULE.md` tables (declared keys must match code) |
| A decision that deviates from the plan | ADR first, then `ARCHITECTURE.md` "Deviations" section, then the plan via `CHANGES.md` |

If a change genuinely needs no doc update, the PR gets the label `docs-not-needed` **and** a one-line reason in the PR description. Reviewers check it.

---

## 6. Development log (every change)

- One **new file per PR** (never edit a shared log file, so parallel developers never conflict): `docs/devlog/YYYY/YYYY-MM-DD-<work-package>-<slug>.md`, from [`docs/templates/DEVLOG.md`](docs/templates/DEVLOG.md).
- Records: who (human and/or agent), work package (e.g. `C4` from [17 §11.2](enterprise-plan/17-build-blueprint.md)), what changed, decisions, docs updated, tests run, open issues, next step.
- AI agents write the entry for their own work and state that an agent did it.

## 7. MODULE.md (every module, service and app)

Created from [`docs/templates/MODULE.md`](docs/templates/MODULE.md) when the unit is created. It must always match the code: purpose, status, owner, layer/deployable, public interface, endpoints, events, data owned, permissions, config keys, dependencies, invariants, failure modes, tests, change history.

## 8. Walkthroughs

Each important flow has a walkthrough ([`docs/WALKTHROUGHS.md`](docs/WALKTHROUGHS.md)). It shows how to run it, which UI step calls which API, module and event, what to look for in traces, and the expected output. It records **"last verified: date + commit"**; a PR that changes the flow re-verifies it.

## 9. ADRs

Any decision about architecture, technology, security, module boundaries or cross-cutting conventions gets an ADR from [`docs/templates/ADR.md`](docs/templates/ADR.md). Status: Proposed → Accepted / Rejected → Superseded by NNNN. Never delete an ADR.

---

## 10. Working method

- **Contract first:** change `contracts/`, regenerate types, then implement. Every facade and port ships a fake.
- **Branches:** `feat/<wp>-<slug>`, `fix/<module>-<slug>`, `docs/<slug>`, `adr/<nnnn>-<slug>`. Trunk-based, small PRs, feature flags for unfinished work.
- **Commits:** follow §10.1 exactly.
- **Reviews:** CODEOWNERS; money-path paths (`modules/actions`, `modules/decision`, `modules/receipts`, `rules/`, `services/signer`) need two approvals.
- **Tests:** unit + contract on every PR; golden tests for every rule version; never weaken or delete a failing test to pass CI; fix the cause or open an issue.

### 10.1 Commit rules (checked in every review)

1. **Author:** only the developer's own GitHub user (`git config user.name` / `user.email` must match your GitHub account). Never two people or tools on one commit.
2. **No attribution trailers:** no `Co-authored-by`, no AI names or emails, no "Generated with/by", no emoji signatures. AI coding agents must not add them and must have attribution turned off in their settings.
3. **Subject:** Conventional Commits, lowercase, imperative, max 72 characters, no final period: `type(scope): summary`. Types: feat, fix, docs, refactor, perf, test, build, ci, chore, revert, style. Scope = module or area.
4. **Body (optional):** blank line, then short `- ` bullets (max 8). No paragraphs, no stories, no reasoning. Reasons belong in the PR description, devlog or ADR.
5. **Allowed footers:** `Refs: #12`, `Closes: #12`, `Fixes: #12`, `Signed-off-by:` (yourself only).

```text
feat(detection): add duplicate reload detector

- add DUPLICATE_RELOAD v1 manifest and detector
- add golden tests (positive, negative, boundary)
- register params in config catalogue

Refs: #42
```

## 11. Definition of done

- [ ] Code follows the invariants (§3) and layer/module rules pass
- [ ] Tests added/updated and green (unit, contract, golden where relevant)
- [ ] Contracts and generated code updated (never hand-edit generated files)
- [ ] Permissions and config keys declared; telemetry spans present
- [ ] Docs per the sync matrix (§5): `MODULE.md`, devlog entry, walkthrough, `ARCHITECTURE.md`, ADR, `CHANGELOG.md` as applicable
- [ ] No secrets, no real personal data, mocks labelled
- [ ] No em dash anywhere
- [ ] Commits follow §10.1 (single author, no attribution, short bullets)

## 12. Extra rules for AI coding agents

1. Read §1 sources before editing; state which work package you are on.
2. Stay inside the module you were asked to change. If you need a contract or another module changed, stop and propose it (ADR or contract PR); don't edit it silently.
3. Don't invent HUTCH systems, APIs, numbers or regulations. Use `hutch-sim` and label assumptions with **ASSUMPTION** / **REQUIRES HUTCH CONFIRMATION**.
4. Don't add dependencies without checking licence (I17) and recording them in the devlog.
5. Run the project checks before declaring done (commands in §13) and report failures honestly.
6. Write the devlog entry and update `MODULE.md` yourself as part of the task.
7. Keep terminology from the glossary (§14) exactly; don't introduce synonyms.

## 13. Commands

Available after scaffolding (work package A1).

| Task | Command |
|---|---|
| Run locally, `lite` profile (needs only PostgreSQL) | `make dev` *(A1)* |
| Reset local database (migrations + synthetic seed) | `make db-reset` *(A1)* |
| Generate local dev keys | `make keys` *(A1)* |
| Run the `full` profile (Kafka, Valkey, Keycloak, OPA, Grafana…) | `make up-full` *(I0)* |
| All checks (lint, types, import rules, tests) | `make check` *(A1)* |
| Regenerate contracts | `make contracts` *(A3)* |

## 14. Glossary (use these words exactly)

| Term | Meaning |
|---|---|
| **case** | One customer problem, across channels |
| **timeline** / **snapshot** | Evidence events from HUTCH sources / the immutable, hashed set used for a decision |
| **detector** | Versioned Python plugin that finds a **cause** in a snapshot (`rule_id@version`) |
| **rule bundle** | Signed release of manifests, detectors and decision tables |
| **decision** | Outcome from the decision table: AUTO_FIX, ONE_TAP_FIX, STAFF_APPROVAL, EXPLAIN_ONLY, HANDOFF |
| **proposal** / **action** | A pending, confirmable change / an executed change by the tool layer |
| **receipt** | Signed, hash-chained Trust Receipt |
| **safeguard** | Customer protection setting (spend cap, data stop, merchant block) |
| **subscriber_ref** | HMAC pseudonym of an MSISDN; raw numbers live only in the vault |
| **policy artefact** / **change class** | Any changeable policy item (K1–K8) / its risk class (C0–C4, E) |
| **model role** | Logical LLM job (`fast-text`, `extract`, `reason`, `judge`, `guard`, `embed`, `stt`, `tts`) |
| **module** / **deployable** | Code unit with its own schema and `public.py` / a running process |
| **port** / **driver** | Interface to an external capability / its implementation (mock, sandbox, hutch, aws, azure…) |
| **hutch-sim** | The simulated HUTCH systems service (always labelled as simulated) |
