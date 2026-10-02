# [A05] Evaluation harness: per-language golden sets, metrics and release gates

| Field | Value |
|---|---|
| Wave | W2 AI foundation |
| Area | `ai` |
| Priority | P1 |
| Depends on | [A02](A02-recorded-responses-cassettes-no-live-model-calls.md) |
| Plan | 22 §10 |
| Labels | `wave:w2`, `area:ai`, `priority:p1`, `type:feature` |

## Context
No quality gates for language or answers.

## Scope
- Datasets: intake, flows, RAG, safety, language review samples
- Metrics and gates from 22 §10; nightly job when a model is configured
- Report artefact per run

## Acceptance tests

| # | Given | When | Then | Where |
|---|---|---|---|---|
| 1 | a regression below a gate | the nightly job runs | the release is blocked with the failing metric named | `CI nightly` |

## Definition of Done
- [ ] Every acceptance test above exists, fails before the change and passes after it
- [ ] `make check` green: lint, format, `mypy --strict`, import contracts, module boundaries, dependency map, all tests
- [ ] R0 acceptance suite green; OpenAPI snapshot unchanged, or regenerated on purpose with a CHANGELOG entry
- [ ] New call edges or events declared (plan 21 §11.2, §11.3; `test_module_dependencies.py`)
- [ ] Docs per the AGENTS.md sync matrix: `MODULE.md`, a devlog file, `ARCHITECTURE.md` / `docs/modules.md` when structure or status changes
- [ ] No secrets, no real personal data, simulated parts labelled; no em dash; commits follow AGENTS.md §10.1
