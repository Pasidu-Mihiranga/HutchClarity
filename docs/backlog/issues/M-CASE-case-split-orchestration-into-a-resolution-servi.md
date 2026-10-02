# [M-CASE] Case: split orchestration into a resolution service, case aggregate on repositories

| Field | Value |
|---|---|
| Wave | W1 Core modules on the baseline |
| Area | `case` |
| Priority | P0 |
| Depends on | [B02](B02-unit-of-work-and-repository-interfaces-per-modul.md), [B06](B06-first-event-driven-flow-receipts-issued-on-actio.md) |
| Plan | 21 §2.2 |
| Labels | `wave:w1`, `area:case`, `priority:p0`, `type:feature` |

## Context
`CaseService` is a 500-line orchestrator holding state for every step.

## Scope
- `case` keeps the aggregate and state machine; a thin `resolution` service orchestrates calls along the declared edges
- State in repositories; `case.created`, `action.failed` handling
- Public surface unchanged for interfaces

## Acceptance tests

| # | Given | When | Then | Where |
|---|---|---|---|---|
| 1 | the R0 acceptance suite | run | passes unchanged | `backend/tests/acceptance` |
| 2 | a case read twice | evaluate called again | the decision is not re-made | `backend/tests/unit/test_case_service.py` |

## Definition of Done
- [ ] Every acceptance test above exists, fails before the change and passes after it
- [ ] `make check` green: lint, format, `mypy --strict`, import contracts, module boundaries, dependency map, all tests
- [ ] R0 acceptance suite green; OpenAPI snapshot unchanged, or regenerated on purpose with a CHANGELOG entry
- [ ] New call edges or events declared (plan 21 §11.2, §11.3; `test_module_dependencies.py`)
- [ ] Docs per the AGENTS.md sync matrix: `MODULE.md`, a devlog file, `ARCHITECTURE.md` / `docs/modules.md` when structure or status changes
- [ ] No secrets, no real personal data, simulated parts labelled; no em dash; commits follow AGENTS.md §10.1
