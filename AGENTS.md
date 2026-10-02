# AGENTS.md - Working rules for Hutch Clarity

These rules apply to **every contributor, human or AI coding agent**, across
the whole repository. A module may add its own `MODULE.md` with extra rules;
module docs never relax the invariants below.

---

## 1. Read before you change anything

1. This file.
2. [`ARCHITECTURE.md`](ARCHITECTURE.md) (as built) and [`docs/adr/`](docs/adr/).
3. The `MODULE.md` of the module you are touching.
4. Enterprise plan chapters under [`docs/enterprise-plan/`](docs/enterprise-plan/).

When documents disagree: accepted ADR > ARCHITECTURE.md > plan chapters.

---

## 2. The project in one paragraph

Hutch Clarity explains every rupee with evidence, fixes known causes by
deterministic rule, proves the fix with a signed Trust Receipt, and prevents
repeats. It is built as an enterprise-grade prototype: production-shaped code,
swappable infrastructure, all HUTCH systems simulated behind ports.

---

## 3. Invariants (never break these)

| # | Rule |
|---|---|
| I1 | **Rules decide, the LLM explains.** Detectors, decision tables and the tool layer decide causes, amounts and actions. An LLM never executes money moves. |
| I2 | **Text is a hint, never evidence.** Missing evidence → handoff, never a guess. |
| I3 | **Money is Decimal LKR.** No floats on money paths. |
| I4 | **Layer rule.** Import only downward (kernel → integration → platform → modules → interfaces). |
| I5 | **Module boundary.** Other modules import only `public.py`. |
| I6 | **Schema per module.** No cross-schema joins in application code. |
| I7 | **Events via the outbox.** State change + event in one transaction; consumers are idempotent. |
| I8 | **Idempotency** on every state-changing call. |
| I9 | **Deny by default.** Routes / consumers / MCP tools declare permissions. |
| I10 | **No hard-coded policy values.** Use the config resolver with `as_of`. |
| I11 | **Time from `Clock`**, never `datetime.now()` in domain code. |
| I12 | **Model IDs only via role config**, not scattered literals. |
| I13 | **No real customer data to any LLM.** Synthetic / masked only. |
| I14 | **No secrets in the repo.** |
| I15 | **Notifications use approved templates only.** |
| I16 | **Simulated is labelled.** Never invent real HUTCH APIs. |
| I17 | Prefer **OSI-licensed** runtime components. |
| I18 | **No em dash (U+2014)** in docs, code, commits or UI. |
| I19 | **One author per commit** (developer GitHub user); no AI co-author trailers. |
| I20 | **Business code never checks the runtime profile.** Only the composition root binds drivers (`lite` / `full` / `prod`). |

---

## 4. Where things live

| Path | What |
|---|---|
| `backend/src/clarity/` | Modular monolith (kernel, platform, integration, modules, entrypoints) |
| `src/clarity/` | Legacy prototype package (hackathon demo still runs here) |
| `services/` | Thin satellites (e.g. MCP) |
| `deploy/` | Compose extras, OPA, Helm, OpenTofu |
| `docs/` | ADRs, enterprise plan, walkthroughs, security, submission |
| `rules/`, `config/`, `templates/` | Policy artefacts |

---

## 5. Documentation sync

If you change behaviour in a module, update that module's `MODULE.md` and
`ARCHITECTURE.md` / ADRs when the decision surface changes. Add a short
devlog under `docs/devlog/` for non-trivial work.

---

## 6. Definition of done (short)

- Lint / types / tests green for the trees you touched.
- Parity suite still passes for any driver you changed.
- Docs and CHANGELOG updated when user-visible or architectural.
- No secrets, no real PII, no em dash.
