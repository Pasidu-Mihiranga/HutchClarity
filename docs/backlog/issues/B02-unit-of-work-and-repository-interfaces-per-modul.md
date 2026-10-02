# [B02] Unit of work and repository interfaces per module (in-memory drivers)

| Field | Value |
|---|---|
| Wave | W0 Baseline wiring |
| Area | `platform` |
| Priority | P0 |
| Depends on | none |
| Plan | 21 §11.6 R2a.2, ADR-0013 |
| Labels | `wave:w0`, `area:platform`, `priority:p0`, `type:baseline` |

## Context
Module state lives in ad-hoc dicts inside services (`CaseService`, `ToolLayer`, `ReceiptLedger`), so nothing can be persisted, rolled back or shared across replicas.

## Scope
- `platform/persistence`: `UnitOfWork` protocol (begin, commit, rollback) and a repository base
- Repositories for case, plans/actions, receipts, governance artefacts behind each module's interface
- In-memory drivers for `lite`; services take repositories by injection from `app.container`
- One parity suite per repository that every driver must pass

## Out of scope
- PostgreSQL drivers (B05)

## Acceptance tests

| # | Given | When | Then | Where |
|---|---|---|---|---|
| 1 | a case saved in a unit of work that is rolled back | the case is read | it does not exist | `backend/tests/contract/test_repository_parity.py` |
| 2 | two units of work updating the same plan | both commit | the second gets a typed conflict, not a silent overwrite | `backend/tests/contract/test_repository_parity.py` |
| 3 | the R0 acceptance suite | run on the new in-memory repositories | it passes unchanged | `backend/tests/acceptance` |

## Definition of Done
- [ ] Every acceptance test above exists, fails before the change and passes after it
- [ ] `make check` green: lint, format, `mypy --strict`, import contracts, module boundaries, dependency map, all tests
- [ ] R0 acceptance suite green; OpenAPI snapshot unchanged, or regenerated on purpose with a CHANGELOG entry
- [ ] New call edges or events declared (plan 21 §11.2, §11.3; `test_module_dependencies.py`)
- [ ] Docs per the AGENTS.md sync matrix: `MODULE.md`, a devlog file, `ARCHITECTURE.md` / `docs/modules.md` when structure or status changes
- [ ] No secrets, no real personal data, simulated parts labelled; no em dash; commits follow AGENTS.md §10.1
- [ ] No module keeps business state outside a repository (grep test)
