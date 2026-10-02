# [B06] First event-driven flow: receipts issued on action.completed

| Field | Value |
|---|---|
| Wave | W0 Baseline wiring |
| Area | `receipts` |
| Priority | P0 |
| Depends on | [B01](B01-event-contracts-typed-versioned-payloads-for-eve.md), [B04](B04-outbox-in-the-unit-of-work-relay-and-consumer-fr.md) |
| Plan | 21 §11.5 |
| Labels | `wave:w0`, `area:receipts`, `priority:p0`, `type:baseline` |

## Context
Receipts are issued by a direct call from `case`; D1 is held by a per-plan lock.

## Scope
- `actions` writes `action.completed@v1` in the unit of work that completes the plan
- `receipts` consumes it and issues one receipt per plan (idempotent by plan ID)
- `case` reads the receipt for the response; per-plan lock removed
- Dependency map: drop the `case -> receipts` edge for this path

## Acceptance tests

| # | Given | When | Then | Where |
|---|---|---|---|---|
| 1 | 1,500 concurrent double confirms | executed | each gives one refund, one receipt, no error | `backend/tests/unit/test_migration_defects.py` |
| 2 | `action.completed` delivered twice | consumed | one receipt exists | `backend/tests/unit/test_receipts_consumer.py` |
| 3 | the R0 acceptance suite | run | it passes unchanged | `backend/tests/acceptance` |

## Definition of Done
- [ ] Every acceptance test above exists, fails before the change and passes after it
- [ ] `make check` green: lint, format, `mypy --strict`, import contracts, module boundaries, dependency map, all tests
- [ ] R0 acceptance suite green; OpenAPI snapshot unchanged, or regenerated on purpose with a CHANGELOG entry
- [ ] New call edges or events declared (plan 21 §11.2, §11.3; `test_module_dependencies.py`)
- [ ] Docs per the AGENTS.md sync matrix: `MODULE.md`, a devlog file, `ARCHITECTURE.md` / `docs/modules.md` when structure or status changes
- [ ] No secrets, no real personal data, simulated parts labelled; no em dash; commits follow AGENTS.md §10.1
- [ ] 21 §11.2 table updated
